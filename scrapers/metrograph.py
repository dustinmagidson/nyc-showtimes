"""
Scraper for Metrograph (https://metrograph.com/nyc/).

Metrograph's showtimes page is plain server-rendered HTML (good — no
headless browser needed) covering several weeks on one page. We don't rely
on CSS class names (which can change silently on a redesign); instead we
key off two very stable signals:

  - Film title links contain "vista_film_id=" in their href.
  - Ticket/time links point at "t.metrograph.com/Ticketing".
  - Date headers are plain text like "Tuesday August 25" with no link.

If Metrograph redesigns their site and this stops finding results, the
first thing to check is whether those two URL patterns still show up in
the page source (view-source:https://metrograph.com/nyc/).
"""

from __future__ import annotations

import datetime as dt
import re

import requests
from bs4 import BeautifulSoup

from common import MONTHS, Showtime, ScrapeError, parse_time_ampm

URL = "https://metrograph.com/nyc/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NYCIndieShowtimesBot/1.0)"}

DATE_RE = re.compile(
    r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+"
    r"([A-Za-z]+)\s+(\d{1,2})$"
)


def scrape() -> list[Showtime]:
    try:
        resp = requests.get(URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        raise ScrapeError(f"could not fetch {URL}: {e}") from e

    soup = BeautifulSoup(resp.text, "html.parser")

    today = dt.date.today()
    current_date = today
    current_year = today.year
    last_month = today.month

    current_title: str | None = None
    results: list[Showtime] = []

    for el in soup.find_all(True):
        # --- date header? ---
        is_heading_like = (el.name or "").startswith("h") or el.name in ("p", "div", "span", "strong")
        if is_heading_like:
            text = el.get_text(" ", strip=True)
            m = DATE_RE.match(text)
            if m and not el.find("a"):
                month_name = m.group(2).lower()
                month = MONTHS.get(month_name)
                if month:
                    if month < last_month:
                        current_year += 1
                    last_month = month
                    current_date = dt.date(current_year, month, int(m.group(3)))
                continue

        # --- title or time link? ---
        if el.name == "a" and el.get("href"):
            href = el["href"]
            if "vista_film_id=" in href:
                title_text = el.get_text(strip=True)
                if title_text:
                    current_title = title_text
                continue
            if "t.metrograph.com/Ticketing" in href:
                time_text = el.get_text(strip=True)
                if current_title and time_text:
                    try:
                        start = parse_time_ampm(time_text, current_date)
                    except ValueError:
                        continue
                    results.append(
                        Showtime(
                            theater="Metrograph",
                            film=current_title,
                            start=start,
                            url=href,
                        )
                    )

    if not results:
        raise ScrapeError("page fetched OK but no showtimes were parsed out of it — selectors may be stale")

    return results


if __name__ == "__main__":
    for s in scrape():
        print(s.start, s.film)
