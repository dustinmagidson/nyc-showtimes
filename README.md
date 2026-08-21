# NYC Indie Showtimes

Scrapes showtimes from six NYC indie theaters — **Metrograph, Film Forum,
IFC Center, Roxy Cinema (Tribeca), Angelika Film Center, and Paris
Theater** — into one combined, mobile-friendly list, updated automatically
every day for free using GitHub Actions + GitHub Pages.

**No notification/matching yet** — this just builds the combined list, per
your request. That can be added later.

Reliability by theater:
| Theater | Method | Reliability |
|---|---|---|
| Metrograph | static HTML | Good |
| Film Forum | static HTML | Good (only ~1 week ahead) |
| IFC Center | static HTML | Good |
| Roxy Cinema | static HTML | Good |
| Angelika Film Center | headless browser, best-effort | **Fragile — see below** |
| Paris Theater | headless browser, best-effort | **Fragile — see below** |

Angelika and Paris Theater both run JavaScript-only booking widgets, so I
couldn't verify their exact page structure the way I could for the other
four (see "If a scraper breaks" below for what to do about it).

---

## 1. One-time setup (about 10 minutes)

### Step 1: Create a GitHub account (skip if you have one)
Go to [github.com/signup](https://github.com/signup) — it's free.

### Step 2: Create a new repository
1. Go to [github.com/new](https://github.com/new)
2. Name it something like `nyc-showtimes`
3. Set it to **Public** (required for free GitHub Actions minutes and free
   GitHub Pages — private repos also get free Actions minutes but Pages
   requires GitHub Pro for private repos)
4. Don't check any of the "initialize with" boxes
5. Click **Create repository**

### Step 3: Upload these files
On the empty repo's page, click **uploading an existing file**, then drag
in this entire folder's contents (keeping the folder structure — `common.py`
and `main.py` at the root, `scrapers/` and `.github/` as subfolders). Or, if
you're comfortable with git on the command line:

```bash
cd nyc_showtimes
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/nyc-showtimes.git
git push -u origin main
```

### Step 4: Turn on GitHub Pages
1. In your repo, go to **Settings -> Pages**
2. Under "Build and deployment" -> "Source", choose **Deploy from a branch**
3. Under "Branch", choose **main** and folder **/docs**, then **Save**
4. GitHub will give you a URL like `https://YOUR-USERNAME.github.io/nyc-showtimes/`
   — bookmark this on your phone, it's your showtimes list

### Step 5: Run the scraper for the first time
1. Go to the **Actions** tab in your repo
2. Click **"Scrape NYC indie showtimes"** on the left
3. Click **Run workflow -> Run workflow** (this triggers it manually instead
   of waiting for the daily schedule)
4. Wait ~1-2 minutes, refresh, and you should see a green checkmark
5. Visit your GitHub Pages URL from Step 4 — you should see today's showtimes

That's it. From now on, it re-runs automatically every day at 11:00 UTC
(6am or 7am Eastern depending on daylight saving) and updates the page.
You can also click "Run workflow" any time you want a fresh pull.

---

## 2. Running it locally (optional, useful for testing)

```bash
cd nyc_showtimes
python3 -m venv .venv
source .venv/bin/activate       # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium     # only needed for Angelika/Paris
python main.py
```

This writes `docs/index.html` and `docs/showtimes.json` — open
`docs/index.html` in a browser to see the result. Errors for any theater
that failed print to the terminal and also show up in a collapsible
"errors" section at the bottom of the generated page.

You can also run any single scraper directly to debug it in isolation:
```bash
python -m scrapers.metrograph
```

---

## 3. If a scraper breaks

Theater websites redesign occasionally, which will break a scraper (you'll
see it show up in the "errors" section on the page, or a red X on the
GitHub Action). To fix it:

1. Open the theater's showtimes page in a normal browser
2. Right-click a showtime -> **Inspect** (or **View Page Source** for a
   quick check) to see the current HTML
3. Compare it to what the scraper expects — each scraper file
   (`scrapers/*.py`) has a docstring at the top explaining exactly what
   URL patterns / text patterns it's looking for
4. Update the pattern, or paste the new HTML into a chat with Claude and
   ask it to fix the relevant scraper file

**Angelika and Paris Theater specifically:** these use JavaScript booking
widgets I could not inspect the rendered markup of ahead of time, so their
scrapers (`scrapers/angelika.py`, `scrapers/paris.py`) use a generic
"guess the title and time from text patterns" heuristic instead of precise
selectors. If these are producing nothing, or garbage, that's expected —
they're the two most likely to need hands-on tuning. If you want a more
reliable fix, open one of those sites in a browser, inspect a showtime
element, and share the HTML in a chat with Claude to get a precise scraper
written for it (the same way the other four were built).

---

## 4. What's not included (yet)

- **The "notify me about specific movies" matcher** — you asked to skip
  this for now. When you're ready, the next step would be a small
  `watchlist.py` that checks each new `Showtime` against a list of
  titles/directors/genres you care about and sends an email or push
  notification (e.g. via a free [ntfy.sh](https://ntfy.sh) topic, which
  needs no account and no API key).
- Any theaters beyond the six above.
- Historical data — each run overwrites the previous showtimes list rather
  than keeping an archive.

---

## File structure

```
nyc_showtimes/
├── main.py                    # runs every scraper, writes docs/
├── common.py                  # shared Showtime model + HTML/JSON writer
├── requirements.txt
├── scrapers/
│   ├── metrograph.py
│   ├── filmforum.py
│   ├── ifc.py
│   ├── roxy.py
│   ├── angelika.py            # fragile — see "If a scraper breaks"
│   └── paris.py                # fragile — see "If a scraper breaks"
├── docs/                      # generated output, served by GitHub Pages
│   ├── index.html
│   └── showtimes.json
└── .github/workflows/scrape.yml   # daily automation
```
