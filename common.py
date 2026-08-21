"""
Shared helpers for the NYC indie theater showtime scraper.

Every scraper module (see scrapers/) returns a list of Showtime objects.
main.py collects them all, sorts them, and writes out JSON + an HTML page.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import re
from pathlib import Path
from typing import Optional


@dataclasses.dataclass
class Showtime:
    theater: str          # e.g. "Metrograph"
    film: str              # e.g. "In the Mood for Love"
    start: dt.datetime     # local NYC time, naive is fine
    url: Optional[str] = None       # link to buy tickets / film page
    format: Optional[str] = None    # "35mm", "DCP", "4K", etc.
    note: Optional[str] = None      # "Q&A with director X", etc.

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["start"] = self.start.isoformat()
        return d


class ScrapeError(Exception):
    """Raised (and caught) when a single theater's scrape fails.

    Scrapers should catch their own internal errors and raise this with a
    clear message so main.py can report "Metrograph failed: ..." without
    the whole run dying.
    """


MONTHS = {
    m.lower(): i
    for i, m in enumerate(
        [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ],
        start=1,
    )
}
MONTHS.update({m.lower()[:3]: i for m, i in list(MONTHS.items())})

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def parse_time_ampm(time_str: str, on_date: dt.date) -> dt.datetime:
    """Parse '7:15pm' / '7:15 PM' / '10:35am' into a datetime on `on_date`."""
    time_str = time_str.strip().lower().replace(" ", "")
    m = re.match(r"^(\d{1,2}):(\d{2})(am|pm)$", time_str)
    if not m:
        raise ValueError(f"Unrecognized time format: {time_str!r}")
    hour, minute, ampm = int(m.group(1)), int(m.group(2)), m.group(3)
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    return dt.datetime.combine(on_date, dt.time(hour, minute))


def next_weekday_on_or_after(start: dt.date, weekday_abbr: str) -> dt.date:
    """Given 'thu', return the next date on/after `start` that's a Thursday."""
    target = WEEKDAYS.index(weekday_abbr.lower()[:3])
    delta = (target - start.weekday()) % 7
    return start + dt.timedelta(days=delta)


TIME_LEAF_RE = re.compile(r"^\d{1,2}:\d{2}\s*(am|pm|AM|PM)$")
DATE_HEADER_RE = re.compile(
    r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\.?,?\s+"
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})",
    re.IGNORECASE,
)


def generic_heuristic_parse(html: str, theater_name: str, base_url: str = "") -> list[Showtime]:
    """Best-effort parser for sites whose exact markup we can't verify
    ahead of time (used for JS-rendered booking widgets like Vista/Next.js
    apps). This has NO knowledge of the site's real CSS classes — it just
    walks the rendered DOM in order and uses a few generic heuristics:

      - Any element whose *entire* text is a bare date like "Fri Aug 21"
        updates the "current date".
      - Any element whose entire text matches "H:MM am/pm" is treated as a
        showtime, associated with the nearest preceding short/title-like
        text (assumed to be the film title) and the current date.

    This is meaningfully less reliable than the URL-pattern-based scrapers
    used for the other theaters, and is the first thing to inspect/rewrite
    if a scraper is producing garbage — see README.md.
    """
    from bs4 import BeautifulSoup  # local import to keep this optional

    soup = BeautifulSoup(html, "html.parser")
    today = dt.date.today()
    current_date = today
    current_year = today.year
    last_month = today.month
    current_title: Optional[str] = None
    results: list[Showtime] = []

    for el in soup.find_all(True):
        if el.find(True):
            # not a leaf — only leaves carry the actual visible text we want
            continue
        text = el.get_text(" ", strip=True)
        if not text:
            continue

        dm = DATE_HEADER_RE.match(text)
        if dm and len(text) < 25:
            month = MONTHS.get(dm.group(2).lower()[:3])
            if month:
                if month < last_month:
                    current_year += 1
                last_month = month
                current_date = dt.date(current_year, month, int(dm.group(3)))
            continue

        if TIME_LEAF_RE.match(text):
            if current_title:
                try:
                    start = parse_time_ampm(text, current_date)
                except ValueError:
                    continue
                results.append(Showtime(theater=theater_name, film=current_title, start=start))
            continue

        # Plausible title: has a letter, reasonably short, not mostly digits
        if 2 <= len(text) <= 90 and re.search(r"[A-Za-z]{3,}", text) and not text.isdigit():
            current_title = text

    return results


def write_outputs(showtimes: list[Showtime], out_dir: str = "docs", errors: dict[str, str] | None = None) -> None:
    """Write showtimes.json and index.html into `out_dir`."""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    errors = errors or {}

    showtimes = sorted(showtimes, key=lambda s: s.start)

    # ---- JSON ----
    json_path = out_path / "showtimes.json"
    json_path.write_text(
        json.dumps([s.to_dict() for s in showtimes], indent=2),
        encoding="utf-8",
    )

    # ---- HTML ----
    now = dt.datetime.now()
    by_date: dict[dt.date, list[Showtime]] = {}
    for s in showtimes:
        by_date.setdefault(s.start.date(), []).append(s)

    theaters = sorted({s.theater for s in showtimes})
    theater_filter_html = "".join(
        f'<button class="chip" data-theater="{t}">{t}</button>' for t in theaters
    )

    day_blocks = []
    for date in sorted(by_date.keys()):
        rows = []
        for s in sorted(by_date[date], key=lambda s: (s.start.time(), s.theater)):
            note_html = f'<div class="note">{escape(s.note)}</div>' if s.note else ""
            fmt_html = f'<span class="fmt">{escape(s.format)}</span>' if s.format else ""
            link_open = f'<a href="{escape(s.url)}" target="_blank" rel="noopener">' if s.url else ""
            link_close = "</a>" if s.url else ""
            rows.append(f"""
            <div class="row" data-theater="{escape(s.theater)}">
              <div class="time">{s.start.strftime('%-I:%M %p')}</div>
              <div class="info">
                {link_open}<span class="film">{escape(s.film)}</span>{link_close}
                {fmt_html}
                <div class="theater">{escape(s.theater)}</div>
                {note_html}
              </div>
            </div>""")
        day_blocks.append(f"""
        <section class="day">
          <h2>{date.strftime('%A, %B %-d')}</h2>
          {''.join(rows)}
        </section>""")

    error_html = ""
    if errors:
        items = "".join(f"<li><strong>{escape(k)}:</strong> {escape(v)}</li>" for k, v in errors.items())
        error_html = f"""
        <details class="errors">
          <summary>{len(errors)} theater(s) failed to scrape this run</summary>
          <ul>{items}</ul>
        </details>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NYC Indie Showtimes</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    max-width: 720px; margin: 0 auto; padding: 16px 16px 60px;
    background: #fafaf8; color: #1a1a1a;
  }}
  h1 {{ font-size: 1.4rem; margin-bottom: 2px; }}
  .updated {{ color: #777; font-size: 0.8rem; margin-bottom: 16px; }}
  .chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 20px; }}
  .chip {{
    border: 1px solid #ccc; background: white; border-radius: 999px;
    padding: 5px 12px; font-size: 0.8rem; cursor: pointer;
  }}
  .chip.active {{ background: #1a1a1a; color: white; border-color: #1a1a1a; }}
  .day h2 {{
    font-size: 1rem; text-transform: uppercase; letter-spacing: 0.04em;
    color: #555; border-bottom: 1px solid #ddd; padding-bottom: 6px; margin-top: 28px;
  }}
  .row {{ display: flex; gap: 12px; padding: 10px 0; border-bottom: 1px solid #eee; }}
  .time {{ width: 72px; flex-shrink: 0; font-variant-numeric: tabular-nums; color: #333; font-size: 0.9rem; }}
  .film {{ font-weight: 600; color: #111; text-decoration: none; }}
  a .film {{ color: #111; }}
  .fmt {{ font-size: 0.7rem; color: #888; margin-left: 6px; border: 1px solid #ddd; border-radius: 4px; padding: 1px 5px; }}
  .theater {{ font-size: 0.8rem; color: #777; margin-top: 2px; }}
  .note {{ font-size: 0.78rem; color: #a15c00; margin-top: 2px; }}
  .errors {{ margin-top: 24px; font-size: 0.85rem; color: #a00; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #111; color: #eee; }}
    .chip {{ background: #222; border-color: #444; color: #eee; }}
    .chip.active {{ background: #eee; color: #111; }}
    .row {{ border-color: #2a2a2a; }}
    .day h2 {{ border-color: #333; color: #aaa; }}
    .film, a .film {{ color: #fff; }}
  }}
</style>
</head>
<body>
  <h1>NYC Indie Showtimes</h1>
  <div class="updated">Updated {now.strftime('%A, %B %-d at %-I:%M %p')}</div>
  <div class="chips" id="chips">
    <button class="chip active" data-theater="all">All</button>
    {theater_filter_html}
  </div>
  {''.join(day_blocks) if day_blocks else '<p>No showtimes found. Something may have broken — see errors below.</p>'}
  {error_html}

<script>
  const chips = document.querySelectorAll('.chip');
  chips.forEach(chip => chip.addEventListener('click', () => {{
    chips.forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    const theater = chip.dataset.theater;
    document.querySelectorAll('.row').forEach(row => {{
      row.style.display = (theater === 'all' || row.dataset.theater === theater) ? 'flex' : 'none';
    }});
    document.querySelectorAll('.day').forEach(day => {{
      const visible = [...day.querySelectorAll('.row')].some(r => r.style.display !== 'none');
      day.style.display = visible ? 'block' : 'none';
    }});
  }}));
</script>
</body>
</html>"""

    (out_path / "index.html").write_text(html, encoding="utf-8")


def escape(s: Optional[str]) -> str:
    if s is None:
        return ""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
