"""
Run every theater scraper, combine the results, and write:
  docs/showtimes.json
  docs/index.html

Usage:
    python main.py

Individual theater failures don't crash the whole run — each scraper is
called independently and its errors are collected and shown at the bottom
of the generated page, so one broken scraper never takes down the rest.
"""

from __future__ import annotations

import sys

from common import ScrapeError, Showtime, write_outputs

# Import order = display order when everything succeeds.
SCRAPERS = [
    ("Metrograph", "scrapers.metrograph"),
    ("Film Forum", "scrapers.filmforum"),
    ("IFC Center", "scrapers.ifc"),
    ("Roxy Cinema", "scrapers.roxy"),
    ("Angelika Film Center", "scrapers.angelika"),
    ("Paris Theater", "scrapers.paris"),
]


def main() -> int:
    import importlib

    all_showtimes: list[Showtime] = []
    errors: dict[str, str] = {}

    for name, module_path in SCRAPERS:
        print(f"Scraping {name}...", file=sys.stderr)
        try:
            module = importlib.import_module(module_path)
            showtimes = module.scrape()
            print(f"  -> {len(showtimes)} showtimes", file=sys.stderr)
            all_showtimes.extend(showtimes)
        except ScrapeError as e:
            print(f"  -> FAILED: {e}", file=sys.stderr)
            errors[name] = str(e)
        except Exception as e:  # noqa: BLE001 - never let one theater kill the run
            print(f"  -> FAILED (unexpected): {e}", file=sys.stderr)
            errors[name] = f"unexpected error: {e}"

    write_outputs(all_showtimes, out_dir="docs", errors=errors)
    print(f"\nWrote {len(all_showtimes)} total showtimes to docs/index.html", file=sys.stderr)
    if errors:
        print(f"{len(errors)} theater(s) failed: {', '.join(errors)}", file=sys.stderr)

    # Exit non-zero only if EVERYTHING failed (so CI flags a fully-broken run
    # without failing every time one fragile scraper has a bad day).
    return 1 if (errors and len(errors) == len(SCRAPERS)) else 0


if __name__ == "__main__":
    sys.exit(main())
