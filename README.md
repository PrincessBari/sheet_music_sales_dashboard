# Sheet Music Sales Dashboard

An interactive dashboard tracking sales of my sheet music arrangements, published through
ArrangeMe and sold on Sheet Music Plus, Sheet Music Direct, the Sheet Music Direct app, and
MuseScore. New sales reports are downloaded and published automatically on a schedule.

**Live dashboard:** https://sheetmusicsalesdashboard.streamlit.app/

Built with **Streamlit**, **pandas**, **Plotly** and **Playwright**.

## What's in the dashboard

**Sidebar filters** (apply to every chart and table)
- Date Sold range
- Transaction Type: Purchase (download) and/or View (subscription)
- Artist(s), with an "All" toggle
- Title(s), narrowed to the selected artists

**Overview tab**
- Summary cards: titles sold, total sales, estimated commissions (with averages by transaction
  type), unique artists, and unique titles (active vs. deactivated)
- Units sold and estimated commissions by artist and by title
- A full title table with sheet music cover previews (click a row to enlarge)
- A world map of purchases by country (location is only recorded for purchases, not views)

**Artist / Title Deep Dive tab**
- Titles sold, sales and commissions over time
- Titles sold by channel
- Titles by publish date
- Purchase vs. View breakdown, including commission per unit sold

## How the data works

1. **Download:** `download_report.py` logs into ArrangeMe with a headless browser (Playwright)
   and saves the latest sales report to `data/raw/sales_report_latest.csv`.
2. **Publish:** `update_and_push.py` runs the download, then commits and pushes the new report
   to GitHub. On macOS, `sheetmusic.plist` schedules it to run automatically with launchd.
3. **Cleaning:** `dashboard.py` corrects titles and adds artist and publish-date information
   by AME ID.
4. **Cover images:** preview images are downloaded from the URLs in `THUMBNAIL_URLS` and
   re-checked weekly, so updated covers replace old ones.

The public dashboard never logs in anywhere. It reads the latest report committed to this
repo, so no account credentials are stored in the cloud.

## Folder structure

```
├── download_report.py
├── dashboard.py
├── update_and_push.py
├── sheetmusic.plist
├── requirements.txt
├── .gitignore
└── data/
    ├── raw/
    │   └── sales_report_latest.csv
    └── thumbnails/          (created automatically)
```

## Run locally

```bash
pip install -r requirements.txt
streamlit run dashboard.py
```

To enable automatic report downloads, also install Playwright and add your ArrangeMe login:

```bash
pip install playwright
playwright install chromium --with-deps
```

```toml
# .streamlit/secrets.toml  (never commit this file)
SITE_USERNAME = "your-email"
SITE_PASSWORD = "your-password"
```

Then run:

```bash
python download_report.py
```

## Updating the public dashboard

Updates are automatic. To schedule them on macOS, edit the paths in `sheetmusic.plist` to match
your machine, then load it:

```bash
cp sheetmusic.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/sheetmusic.plist
```

To update manually instead:

```bash
python update_and_push.py
```

Streamlit Community Cloud redeploys automatically after each push.
