"""
Scraper for Film Forum (https://filmforum.org/now_playing).

Film Forum shows a week-ahead, day-tabbed schedule ("Playing This Week")
as plain server-rendered HTML: elements with id="tabs-0" through
"tabs-6", where tabs-0 is today and each subsequent tab is +1 day.
Each film within a tab is a link to https://filmforum.org/film/<slug>
followed by its times as plain text (e.g. "12:20 2:15 4:10 6:10 8:10",
sometimes with an "(OC)" open-caption marker on one showing).

This only covers ~1 week out. Film Forum also publishes a full
season calendar as a PDF, which is out of scope for this scraper.

If this stops finding results, check that filmforum.org/now_playing still
has elements with id starting "tabs-" and that film links still point at
"filmforum.org/film/".
"""

from __future__ import annotations

import datetime as dt
import re

import requests
from bs4 import BeautifulSoup

from common import Showtime, ScrapeError, parse_time_ampm

URL = "https://filmforum.org/now_playing"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NYCIndieShowtimesBot/1.0)"}

TIME_RE = re.compile(r"\d{1,2}:\d{2}")
TAB_ID_RE = re.compile(r"^tabs-(\d+)$")


def scrape() -> list[Showtime]:
    try:
        resp = requests.get(URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        raise ScrapeError(f"could not fetch {URL}: {e}") from e

    soup = BeautifulSoup(resp.text, "html.parser")
    today = dt.date.today()
    results: list[Showtime] = []

    tab_containers = [el for el in soup.find_all(True, id=TAB_ID_RE)]
    if not tab_containers:
        raise ScrapeError("no #tabs-N day containers found — page layout may have changed")

    for container in tab_containers:
        m = TAB_ID_RE.match(container.get("id", ""))
        offset = int(m.group(1))
        the_date = today + dt.timedelta(days=offset)

        for a in container.find_all("a", href=True):
            if "filmforum.org/film/" not in a["href"]:
                continue
            title = a.get_text(strip=True)
            if not title:
                continue
            # The times usually live as plain text in the same parent
            # element as the title link, e.g. <p><b><a>TITLE</a></b> times</p>
            parent = a.find_parent(["p", "li", "div"]) or a.parent
            block_text = parent.get_text(" ", strip=True) if parent else ""
            times = TIME_RE.findall(block_text)
            for t in times:
                try:
                    start = parse_time_ampm(_guess_ampm(t), the_date)
                except ValueError:
                    continue
                results.append(
                    Showtime(
                        theater="Film Forum",
                        film=title,
                        start=start,
                        url=a["href"],
                    )
                )

    if not results:
        raise ScrapeError("page fetched OK but no showtimes were parsed out of it — selectors may be stale")

    return results


def _guess_ampm(time_str: str) -> str:
    """Film Forum times have no am/pm marker (e.g. '2:15'). Guess based on
    typical cinema hours: before noon-ish hour values (1-9 with no context)
    are ambiguous, but Film Forum's earliest show is generally ~11am and
    latest is ~11pm, so we treat anything from 11:00-11:59 as ambiguous
    (default am for 11, pm otherwise) and everything else consistently:
    12 -> pm, 1-10 -> pm (matinees are rare before noon at Film Forum).
    """
    hour_str, _, _ = time_str.partition(":")
    hour = int(hour_str)
    if hour == 12:
        return f"{time_str}pm"
    if hour == 11:
        # 11:xx could be an 11am matinee or 11pm late show; Film Forum runs
        # very few 11pm shows, so default to am. Adjust here if wrong.
        return f"{time_str}am"
    return f"{time_str}pm"


if __name__ == "__main__":
    for s in scrape():
        print(s.start, s.film)
