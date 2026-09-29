# Sheet Music Sales Dashboard

An interactive dashboard tracking sales of my sheet music arrangements, published through
ArrangeMe and sold on Sheet Music Plus, Sheet Music Direct, Sheet Music Direct App, and MuseScore.

Built with **Streamlit**, **pandas** and **Plotly**.

**Live dashboard:** https://sheetmusicsalesdashboard.streamlit.app/

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

1. **Download:** when run locally, the app logs into ArrangeMe with a headless browser
   (Playwright) and downloads the latest sales report, at most once every 7 days.
2. **Cleaning:** titles are corrected and artist and publish-date information is added by
   AME ID.
3. **Cover images:** preview images are downloaded from the URLs in `THUMBNAIL_URLS` and
   re-checked weekly, so updated covers replace old ones.

The public version doesn't log in anywhere. It reads the latest report committed to this
repo, so no account credentials are stored in the cloud.

## Folder structure

```
├── dashboard.py
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

## Updating the public dashboard

Run the app locally to download a fresh report, then push it:

```bash
git add data/raw/sales_report_latest.csv
git commit -m "Update sales report"
git push
```

Streamlit Community Cloud redeploys automatically.
