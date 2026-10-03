"""
download_report.py

Uses Playwright to drive a real (headless) browser: logs into ArrangeMe,
clicks through to Download All Sales, and saves the resulting CSV.

SETUP REQUIRED:
  1. pip install playwright
  2. playwright install chromium --with-deps   (downloads the browser binary — one-time setup)
  3. Fill in the CSS selectors below (see instructions further down).
  4. Store credentials as environment variables or Streamlit secrets (never hardcode them).
"""

import os
from datetime import datetime
from pathlib import Path
import tomllib

PROJECT_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# CONFIG — replace these placeholders with real values from your site
# ---------------------------------------------------------------------------

LOGIN_PAGE_URL = "https://www.arrangeme.com/account/signin"
DASHBOARD_URL = "https://www.arrangeme.com/account/dashboard"
VIEW_REPORTS_SELECTOR = "a.widgetLink[href='#commissions']"  # scoped to avoid matching the dropdown item

# CSS selectors — find these via right-click > Inspect on each element (see instructions below)
USERNAME_SELECTOR = "input[name='email']"        # confirmed via Inspect
PASSWORD_SELECTOR = "input[name='password']"     # confirmed via Inspect
LOGIN_BUTTON_SELECTOR = "button[type='submit']"  # adjust if the login button differs
DOWNLOAD_BUTTON_SELECTOR = "a.downloadSales:visible"  # :visible filters out hidden duplicates

DATA_DIR = PROJECT_DIR / "data" / "raw"
RAW_LATEST_PATH = DATA_DIR / "sales_report_latest.csv"


def get_credentials():
    """Env vars first, then .streamlit/secrets.toml. Works with or without Streamlit."""
    username = os.environ.get("SITE_USERNAME")
    password = os.environ.get("SITE_PASSWORD")
    if username and password:
        return username, password

    secrets_file = PROJECT_DIR / ".streamlit" / "secrets.toml"
    if secrets_file.exists():
        with open(secrets_file, "rb") as f:
            secrets = tomllib.load(f)
        return secrets["SITE_USERNAME"], secrets["SITE_PASSWORD"]

    raise RuntimeError(
        "Missing credentials. Set SITE_USERNAME and SITE_PASSWORD "
        "as environment variables, or in .streamlit/secrets.toml"
    )

def download_csv() -> Path:
    """Logs in via a real browser and downloads the CSV using Playwright."""
    from playwright.sync_api import sync_playwright
    username, password = get_credentials()
    _timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    archive_path = DATA_DIR / f"sales_report_{_timestamp}.csv"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # --- Step 1: log in ---
        page.goto(LOGIN_PAGE_URL)
        # Use type() instead of fill() — some sites only enable the submit
        # button once real keystroke events fire (fill() sets the value
        # directly and can skip the events the site's JS is listening for).
        page.type(USERNAME_SELECTOR, username)
        page.type(PASSWORD_SELECTOR, password)
        page.click(LOGIN_BUTTON_SELECTOR)

        # Wait for navigation to the dashboard (or wherever login redirects to)
        page.wait_for_url("**/account/dashboard**", timeout=15000)

        print(f"[DEBUG] Logged in — current URL: {page.url}")

        # --- Step 2: navigate to the reports/download page and trigger the download ---
        page.goto(DASHBOARD_URL)

        # "View Reports" runs JS to switch tabs and load the Commissions section —
        # visiting the #commissions URL directly does NOT trigger this render.
        page.click(VIEW_REPORTS_SELECTOR)
        page.wait_for_selector(DOWNLOAD_BUTTON_SELECTOR, timeout=15000)

        # The download link opens in a NEW TAB (target="_blank"). We listen for
        # both the new-page event AND the download event at the context level,
        # wrapping the click itself so neither event can be missed.
        with page.context.expect_page() as new_page_info, \
             page.context.expect_event("download") as download_info:
            page.click(DOWNLOAD_BUTTON_SELECTOR)

        download = download_info.value

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        download.save_as(archive_path)
        download.save_as(RAW_LATEST_PATH)

        browser.close()

    return RAW_LATEST_PATH


if __name__ == "__main__":
    path = download_csv()
    print(f"Downloaded CSV to: {path}")