"""
Sheet Music Sales Dashboard
===========================

Single-file Streamlit app that:
  1. Downloads the latest sales report CSV from ArrangeMe via a headless
     browser (Playwright), but only if the cached copy is more than
     REFRESH_INTERVAL old (default: 7 days) and login details are
     available. The public cloud version skips this and reads the CSV
     pushed to the repo: no ArrangeMe login is stored there on
     purpose, so visitors can never trigger a login to the account, and
     the cloud host doesn't provide the browser Playwright needs.
  1b. Downloads cover-art thumbnails via plain HTTP from THUMBNAIL_URLS
     below (cached on disk by AME ID, and re-checked weekly so updated
     covers replace old ones). THUMBNAIL_URLS is filled in by hand — see
     the comment above it for why this isn't scraped automatically.
  2. Cleans/reshapes the raw data (fixes titles, adds Artist / Date Published,
     reorders columns) — logic ported from explore.ipynb.
  3. Renders the Streamlit dashboard.

SETUP REQUIRED (same as the old download_report.py):
  1. pip install playwright requests
  2. playwright install chromium --with-deps   (one-time browser download)
  3. Store credentials as environment variables (SITE_USERNAME / SITE_PASSWORD)
     or in .streamlit/secrets.toml — never hardcode them.
"""

import base64
from datetime import timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from download_report import download_csv, get_credentials, RAW_LATEST_PATH

# ----------------------------------------------------------------------------
# Page config
# ----------------------------------------------------------------------------
st.set_page_config(page_title="Sheet Music Sales Dashboard", layout="wide")

# ----------------------------------------------------------------------------
# Data source config (from download_report.py)
# ----------------------------------------------------------------------------
THUMBNAIL_DIR = Path("data/thumbnails")

# Only download a fresh report if the cached one is older than this.
REFRESH_INTERVAL = timedelta(days=7)

# AME ID -> cover-art preview image URL. Filled in BY HAND — automating this
# via Playwright turned out not to be worth it: the arrangeme.com title page
# tries to embed the actual PDF score live using Chrome's built-in PDF
# plugin, which headless Chromium doesn't have; the real cover image instead
# lives on the separate Sheet Music Direct storefront listing, and fetching
# that page via automation kept timing out (most likely bot detection on
# that storefront). Since these S3 URLs are public and don't expire, a
# one-time manual copy is more reliable than fighting that.
#
# To add one: on your ArrangeMe title management page
# (arrangeme.com/title/{ame_id}), click "Sheet Music Direct" under
# "Published To". On that page, right-click the cover preview image ->
# "Copy Image Address", and paste the result below.
THUMBNAIL_URLS = { # "<ame_id>": "<image url>",
    "683603": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_7db5297900107885.png",  # I Don't Blame You
    "827483": "https://www.sheetmusicplus.com/dw/image/v2/BJFX_PRD/on/demandware.static/-/Sites-smp-main/default/dwf19135e7/images/2959/22502959_cover-large_file.png?sw=900&sh=1200&sm=fit",
    # Piano Joint (This Kind of Love)
    "655513": "https://www.sheetmusicplus.com/dw/image/v2/BJFX_PRD/on/demandware.static/-/Sites-smp-main/default/dw04a8bbdc/images/4426/22304426_cover-large_file.png?sw=900&sh=1200&sm=fit", 
    # It Means Beautiful
    "520999": "",  # Winning (deactivated due to incorrect metadata assignment by website) - no image
    "521008": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_f804e66e000df6af.png",  # Help, I'm Alive (acoustic)
    "715828": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_c3506c450010ff4b.png",  # Breathing Underwater (acoustic)
    "646069": "",  # Rabbit in Your Headlights (deactivated due to incorrect metadata assignment by website) - no image
    "1177658": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_a3a8c84d00188822.png",  # Paris, Texas (instrumental)
    "1140815": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_29f1c6db0017efd0.png",  # Alone in Kyoto
    "749218": "https://www.sheetmusicplus.com/dw/image/v2/BJFX_PRD/on/demandware.static/-/Sites-smp-main/default/dw77890f2b/images/2965/22412965_cover-large_file.png?sw=900&sh=1200&sm=fit", 
    # Echoes of Silence
    "646071": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_e57f3f26000fe3b3.png",  # Calculation Theme
    "521007": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_128b9d79000df6ae.png",  # Five String Serenade
    "521006": "",  # Doctor Blind (deactivated due to incorrect metadata assignment by website) - no image
    "521005": "",  # Crowd Surf Off a Cliff (deactivated due to incorrect metadata assignment by website) - no image
    "697606": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_778c60aa0010afa6.png",  # Rolling Stone
    "706331": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_468245f40010d49e.png",  # Gold Guns Girls (acoustic)
    "1118988": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_15327f1c00179927.png",  # Friend Of The Night
    "975844": "https://www.sheetmusicplus.com/dw/image/v2/BJFX_PRD/on/demandware.static/-/Sites-smp-main/default/dwb40c8ee3/images/9409/22709409_cover-large_file.png?sw=900&sh=1200&sm=fit",  
    # 1 Ghosts I
    "982187": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_027f2cd80015587f.png",  # 13 Ghosts II
    "521003": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_6a862796000df6aa.png",  # Twice
    "521002": "",  # Rabbit in Your Headlights (deactivated due to incorrect metadata assignment by website) - no image
    "521004": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_2b3bc98b000df6ab.png",  # Leaving A Voicemail
    "761510": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_a84665340011b7dc.png",  # Twilight Galaxy (acoustic)
    "1131653": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_559419b10017cb82.png",  # Intro
    "1175089": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_85de51c400187d0a.png",  # Piano Joint (This Kind of Love) (instrumental)
    "1186453": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_6733363e0018ad4b.png",  # Twice (instrumental)
    "520997": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_fe277454000df6a6.png",  # Too Raging To Cheers
    "1136775": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_ead8953e0017e01a.png",  # I'm Jim Morrison, I'm Dead
    "771371": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_3aa4258b0011de5a.png",  # London Halflife
    "897533": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_7e21083c0013f687.png",  # Sick Muse (acoustic)
    "1213044": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_ddac6f2b00191dfc.png",  # Take Me Somewhere Nice	
    "1469119": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_de3d4cff001d29c0.png",  # Everything In Its Right Place		
    "799066": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_cd8005fc00125087.png",  # Dark Saturday (acoustic)    
    "1470063": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_633bc22d001d2d54.png",  # Fade Into You
    "1162012": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_53558048001845cf.png",  # Rabbit In Your Headlights (Instrumental)
    "1199783": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_595d8d120018e4e3.png",  # Mad World
    "1454279": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_03051846001ceda8.png",  # Highschool Lover
    "933843": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_5159cf55001495ee.png",  # Focus
    "1152225": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_bd2147d000181ee8.png",  # London Halflife (instrumental)
    "1454287": "https://www.sheetmusicplus.com/smp-cdn-assets/items/23740553/cover_images/cover-large_file.png",  # The Greatest (instrumental)
    "1454286": "https://www.sheetmusicplus.com/smp-cdn-assets/items/23740551/cover_images/cover-large_file.png@900",  # Doctor Blind (instrumental)
    "1454285": "https://www.sheetmusicplus.com/smp-cdn-assets/items/23740552/cover_images/cover-large_file.png@900",  # Doctor Blind
    "1454283": "https://s3.amazonaws.com/halleonard-pagepreviews/UG_010c93f8001cedab.png",  # Winning
}

@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)  # re-check covers at most once a day
def sync_thumbnails(thumbnail_urls):  # URLs passed in, so editing one triggers a fresh check
    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
    changed = False

    for ame_id, url in thumbnail_urls.items():  # uses the passed-in URLs
        if not url:  # deactivated titles
            continue
        path = THUMBNAIL_DIR / f"{ame_id}.jpg"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"Thumbnail download failed for {ame_id}: {e}")
            continue

        # Save if it's new, or if the image on the website differs from the saved one
        if not path.exists() or path.read_bytes() != resp.content:
            path.write_bytes(resp.content)
            changed = True
            print(f"Updated thumbnail for {ame_id}")

    if changed:
        clean_data.clear()  # make the table rebuild with the new images

    return changed


def has_credentials() -> bool:
    try:
        get_credentials()
        return True
    except RuntimeError:
        return False


@st.cache_resource(show_spinner="Downloading latest sales report...")
def download_once_per_run() -> bool:
    """Runs once each time you start the app, not on every click."""
    download_csv()
    return True


def ensure_fresh_data() -> Path:
    """At home (login available), downloads a fresh report each time the
    app starts. On the cloud (no login), just reads the CSV in the repo."""
    if has_credentials():
        try:
            download_once_per_run()
        except Exception as e:
            if RAW_LATEST_PATH.exists():
                st.warning(f"Couldn't download a new report, showing the saved one. ({e})")
            else:
                raise
    return RAW_LATEST_PATH


# ----------------------------------------------------------------------------
# Cleaning (ported from explore.ipynb)
# ----------------------------------------------------------------------------

# AME ID -> corrected Title / Artist / Date Published.
# NOTE: as new AME IDs show up in future reports, they won't have an entry
# here yet, so their Title will pass through unchanged and Artist / Date
# Published will be blank until you add them below.
AME_ID_INFO = {
    "1140815": {"Title": "Alone In Kyoto", "Artist": "Air", "Date Published": "2025-01-05"},
    "715828": {"Title": "Breathing Underwater", "Artist": "Metric", "Date Published": "2022-10-02"},
    "646071": {"Title": "Calculation Theme", "Artist": "Metric", "Date Published": "2022-05-28"},
    "799066": {"Title": "Dark Saturday", "Artist": "Metric", "Date Published": "2023-03-15"},
    "1454285": {"Title": "Doctor Blind", "Artist": "Emily Haines & The Soft Skeleton", "Date Published": "2026-05-16"},
    "1454286": {"Title": "Doctor Blind (instrumental)", "Artist": "Emily Haines & The Soft Skeleton", "Date Published": "2026-05-16"},
    "749218": {"Title": "Echoes Of Silence", "Artist": "The Weeknd", "Date Published": "2022-12-22"},
    "1469119": {"Title": "Everything In Its Right Place (instrumental)", "Artist": "Radiohead", "Date Published": "2026-06-05"},
    "1470063": {"Title": "Fade Into You (instrumental)", "Artist": "Mazzy Star", "Date Published": "2026-06-07"},
    "521007": {"Title": "Five String Serenade (Cover by Mazzy Star)", "Artist": "Arthur Lee", "Date Published": "2022-04-28"},
    "933843": {"Title": "Focus (acoustic)", "Artist": "Ariana Grande", "Date Published": "2023-12-28"},
    "1118988": {"Title": "Friend of The Night", "Artist": "Mogwai", "Date Published": "2024-11-22"},
    "975844": {"Title": "1 Ghosts I", "Artist": "Nine Inch Nails", "Date Published": "2024-02-29"},
    "982187": {"Title": "13 Ghosts II", "Artist": "Nine Inch Nails", "Date Published": "2024-03-10"},
    "521008": {"Title": "Help, I'm Alive (acoustic)", "Artist": "Metric", "Date Published": "2022-04-28"},
    "1454279": {"Title": "Highschool Lover", "Artist": "Air", "Date Published": "2026-05-16"},
    "683603": {"Title": "I Don't Blame You", "Artist": "Cat Power", "Date Published": "2022-07-08"},
    "1136775": {"Title": "I'm Jim Morrison, I'm Dead", "Artist": "Mogwai", "Date Published": "2024-12-27"},
    "1131653": {"Title": "Intro (instrumental)", "Artist": "The XX", "Date Published": "2024-12-14"},
    "655513": {"Title": "It Means Beautiful", "Artist": "Dan Gillespie Sells", "Date Published": "2022-06-22"},
    "521004": {"Title": "Leaving A Voicemail", "Artist": "Dustin O' Halloran", "Date Published": "2022-04-28"},
    "1152225": {"Title": "London Halflife (instrumental)", "Artist": "Metric", "Date Published": "2025-01-23"},
    "771371": {"Title": "London Halflife", "Artist": "Metric", "Date Published": "2023-01-31"},
    "1199783": {"Title": "Mad World (instrumental)", "Artist": "Michael Andrews Feat. Gary Jules", "Date Published": "2025-04-17"},
    "520997": {"Title": "Too Raging To Cheers", "Artist": "Mogwai", "Date Published": "2022-04-28"},
    "1177658": {"Title": "Paris, Texas", "Artist": "Lana Del Rey", "Date Published": "2025-03-06"},
    "1175089": {"Title": "Piano Joint (This Kind Of Love) (instrumental)", "Artist": "Michael Kiwanuka", "Date Published": "2025-03-02"},
    "827483": {"Title": "Piano Joint (This Kind Of Love)", "Artist": "Michael Kiwanuka", "Date Published": "2023-05-13"},
    "1162012": {"Title": "Rabbit In Your Headlights (instrumental)", "Artist": "Unkle", "Date Published": "2025-02-07"},
    "646069": {"Title": "Rabbit In Your Headlights (instrumental) (deactivated)", "Artist": "Unkle", "Date Published": "2022-05-28"},
    "697606": {"Title": "Rolling Stone", "Artist": "The Weeknd", "Date Published": "2022-08-12"},
    "897533": {"Title": "Sick Muse (acoustic)", "Artist": "Metric", "Date Published": "2023-10-20"},
    "1213044": {"Title": "Take Me Somewhere Nice", "Artist": "Mogwai", "Date Published": "2025-05-17"},
    "1454287": {"Title": "The Greatest (instrumental)", "Artist": "Cat Power", "Date Published": "2026-05-16"},
    "520999": {"Title": "Winning (deactivated)", "Artist": "Emily Haines & The Soft Skeleton", "Date Published": "2022-04-28"},
    "521005": {"Title": "Crowd Surf Off a Cliff (deactivated)", "Artist": "Emily Haines & The Soft Skeleton", "Date Published": "2022-04-28"},
    "521006": {"Title": "Doctor Blind (deactivated)", "Artist": "Emily Haines & The Soft Skeleton", "Date Published": "2022-04-28"},
    "706331": {"Title": "Gold Guns Girls", "Artist": "Metric", "Date Published": "2022-09-07"},
    "1186453": {"Title": "Twice (instrumental)", "Artist": "Little Dragon", "Date Published": "2025-03-22"},
    "521003": {"Title": "Twice", "Artist": "Little Dragon", "Date Published": "2022-04-28"},
    "761510": {"Title": "Twilight Galaxy (acoustic)", "Artist": "Metric", "Date Published": "2023-01-14"},
    "521002": {"Title": "Rabbit In Your Headlights (deactivated)", "Artist": "Unkle", "Date Published": "2022-04-28"},
    "1454283": {"Title": "Winning", "Artist": "Emily Haines & The Soft Skeleton", "Date Published": "2026-05-16"},
}


@st.cache_data
def clean_data(raw_path: str, _raw_mtime: float) -> pd.DataFrame:
    """Clean/reshape the raw CSV. `_raw_mtime` is only used as a cache key so
    this reruns automatically whenever a fresh CSV is downloaded, but not on
    every ordinary Streamlit rerun in between."""
    df = pd.read_csv(raw_path)

    # AME ID as string (it's an identifier, not a number)
    df["AME ID"] = df["AME ID"].astype(str)

    # Sales / Est. Commissions: strip "$" and "," then convert to float
    for col in ["Sales", "Est. Commissions"]:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.strip()
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Fix titles (e.g. mark "instrumental"/"deactivated" versions) and add
    # Artist + Date Published, looked up by AME ID
    df["Title"] = df["AME ID"].map(lambda x: AME_ID_INFO.get(x, {}).get("Title")).fillna(df["Title"])
    df["Artist"] = df["AME ID"].map(lambda x: AME_ID_INFO.get(x, {}).get("Artist"))
    df["Date Published"] = df["AME ID"].map(lambda x: AME_ID_INFO.get(x, {}).get("Date Published"))
    df["Date Published"] = pd.to_datetime(df["Date Published"])

    # Local thumbnail path, if one has been cached for this AME ID (see
    # sync_thumbnails() / THUMBNAIL_URLS). None if not yet in THUMBNAIL_URLS
    # or not downloaded yet — kept as a plain lookup column, never used as a
    # groupby key, so a missing thumbnail can't cause rows to be dropped out
    # of any aggregation.
    def _thumb_data_uri(ame_id):
        path = THUMBNAIL_DIR / f"{ame_id}.jpg"
        if not path.exists():
            return None
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{b64}"

    df["Thumbnail"] = df["AME ID"].map(_thumb_data_uri)

    # Rename + parse the sale date
    df = df.rename(columns={"Date": "Date Sold"})
    df["Date Sold"] = pd.to_datetime(df["Date Sold"], format="%m-%d-%Y")

    # Reorder columns
    df = df[
        [
            "Date Sold",
            "AME ID",
            "Artist",
            "Title",
            "Thumbnail",
            "Format",
            "Asset Type",
            "Channel",
            "Location",
            "Transaction Type",
            "Quantity",
            "Sales",
            "Est. Commissions",
            "Date Published",
        ]
    ]

    return df

@st.dialog("Cover preview")
def show_cover(title, img):
    st.image(img)
    st.caption(title)

# ----------------------------------------------------------------------------
# Design tokens
# ----------------------------------------------------------------------------
BG_MAIN = "#F6F3EC"
BG_SURFACE = "#FFFFFF"
TEXT_PRIMARY = "#2A2420"
TEXT_SECONDARY = "#7A7267"
BORDER = "#E4DECE"
ACCENT = "#7B2D3B"        # oxblood — primary series / primary interactive
ACCENT_SOFT = "#C98A96"   # lighter tint of accent, for hover states
SECONDARY = "#3B5249"     # deep forest green — secondary series

CHOROPLETH_SCALE = [
    [0.0, "#F2EBDD"],
    [0.5, "#C98A96"],
    [1.0, "#7B2D3B"],
]

FONT_HEAD = "Fraunces, serif"
FONT_BODY = "Inter, -apple-system, sans-serif"

# Plotly config for the choropleth maps: turns off scroll-to-zoom (so scrolling
# the page past the map doesn't accidentally zoom it) while keeping the
# hover toolbar's zoom/pan/reset-view icons for anyone who wants to interact.
MAP_CONFIG = {
    "scrollZoom": False,
    "displayModeBar": True,    # always show the icon toolbar (not just on hover)
    "displaylogo": False,      # hide the Plotly logo icon
    "modeBarButtonsToRemove": [
        "select2d", "lasso2d", "hoverClosestGeo", "toImage",
    ],
}

# Plotly config for the simple bar charts: no toolbar at all.
STATIC_CHART_CONFIG = {"displayModeBar": False}


def lock_fig(fig):
    """Turn off zoom/pan so an accidental swipe on mobile can't resize the chart."""
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig

# ----------------------------------------------------------------------------
# Custom CSS
# ----------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Inter:wght@400;500;600&display=swap');

    html, body, [class*="css"] {{
        font-family: {FONT_BODY};
        color: {TEXT_PRIMARY};
    }}

    .stApp {{
        background-color: {BG_MAIN};
    }}

    h1 {{
        font-family: {FONT_HEAD} !important;
        font-weight: 500 !important;
        font-size: 2.4rem !important;
        letter-spacing: -0.01em;
        color: {TEXT_PRIMARY} !important;
        padding-bottom: 0.3rem;
        border-bottom: 1px solid {BORDER};
        margin-bottom: 1.4rem !important;
    }}

    h2, h3 {{
        font-family: {FONT_HEAD} !important;
        font-weight: 500 !important;
        color: {TEXT_PRIMARY} !important;
    }}

    [data-testid="stCaptionContainer"], .stCaption {{
        color: {TEXT_SECONDARY} !important;
        font-size: 0.86rem;
    }}
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{
        margin-bottom: 0 !important;
    }}
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
        gap: 0.3rem;
    }}

    /* Metric cards */
    [data-testid="stMetric"] {{
        background-color: {BG_SURFACE};
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 1rem 1.1rem 0.8rem 1.1rem;
    }}
    [data-testid="stMetricLabel"] {{
        color: {TEXT_SECONDARY} !important;
        font-size: 0.82rem;
        font-weight: 500;
        text-transform: none;
    }}
    [data-testid="stMetricValue"] {{
        color: {TEXT_PRIMARY} !important;
        font-family: {FONT_BODY};
        font-weight: 600;
        letter-spacing: -0.02em;
        font-variant-numeric: tabular-nums;
    }}

    /* Tabs */
    [data-testid="stTabs"] button {{
        font-family: {FONT_BODY};
        font-weight: 500;
        font-size: 1.05rem;
        color: {TEXT_SECONDARY};
    }}
    [data-testid="stTabs"] button p {{
        font-size: 1.05rem;
    }}
    [data-testid="stTabs"] button[aria-selected="true"] {{
        color: {ACCENT} !important;
    }}
    [data-testid="stTabs"] [data-baseweb="tab-highlight"] {{
        background-color: {ACCENT} !important;
    }}
    [data-testid="stTabs"] [data-baseweb="tab-border"] {{
        background-color: {BORDER} !important;
    }}

    /* Sidebar */
    [data-testid="stSidebar"] {{
        background-color: {BG_SURFACE};
        border-right: 1px solid {BORDER};
    }}
    [data-testid="stSidebar"] h2 {{
        font-size: 1.2rem !important;
    }}
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li {{
        color: {TEXT_PRIMARY} !important;
    }}
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] label p {{
        color: {TEXT_PRIMARY} !important;
        font-size: 0.98rem !important;
    }}
    /* Hide mobile-only items on devices with a mouse (laptops/desktops) */
    @media (hover: hover) and (pointer: fine) {{
        .mobile-only {{
            display: none;
        }}
    }}
    /* "Filters" label next to the sidebar icon (mobile only) */
    .filters-label {{
        position: fixed;
        top: 0.9rem;
        left: 3.1rem;
        z-index: 999990;
        color: #F6F3EC;
        font-size: 1.2rem;
        font-weight: 600;
        pointer-events: none;
    }}
    /* Make the sidebar's « close button dark enough to see */
    [data-testid="stSidebarHeader"] button,
    [data-testid="stSidebarHeader"] button *,
    [data-testid="stSidebarCollapseButton"] button,
    [data-testid="stSidebarCollapseButton"] button * {{
        color: {TEXT_PRIMARY} !important;
        fill: {TEXT_PRIMARY} !important;
        opacity: 1 !important;
    }}
    /* Always show the « close button on touch devices (it's hover-only by default) */
    @media (hover: none) {{
        [data-testid="stSidebarHeader"],
        [data-testid="stSidebarHeader"] *,
        [data-testid="stSidebarCollapseButton"],
        [data-testid="stSidebarCollapseButton"] * {{
            visibility: visible !important;
            opacity: 1 !important;
        }}
        [data-testid="stSidebarCollapseButton"] {{
            display: block !important;
        }}
    }}

    /* Dataframes */
    [data-testid="stDataFrame"] {{
        border: 1px solid {BORDER};
        border-radius: 4px;
    }}

    /* Expanders */
    [data-testid="stExpander"] summary {{
        color: {TEXT_PRIMARY} !important;
        background-color: {BG_SURFACE} !important;
        border-radius: 4px;
    }}
    [data-testid="stExpander"] summary:hover {{
    background-color: {BG_SURFACE} !important;
    }}
    [data-testid="stExpander"] summary:focus {{
        background-color: {BG_SURFACE} !important;
        box-shadow: none !important;
    }}
    [data-testid="stExpander"] details {{
        background-color: {BG_SURFACE} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 4px;
    }}

    hr {{
        border-color: {BORDER} !important;
        margin: 1.6rem 0 !important;
    }}
    [data-testid="stSidebar"] hr {{
        margin: 0.15rem 0 1rem 0 !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


def style_fig(fig, dual_series: bool = False):
    """Apply the shared visual template to every Plotly chart."""
    fig.update_layout(
        font=dict(family=FONT_BODY, color=TEXT_PRIMARY, size=13),
        title=dict(text=fig.layout.title.text or "", font=dict(family=FONT_HEAD, size=17, color=TEXT_PRIMARY)),
        plot_bgcolor=BG_SURFACE,
        paper_bgcolor="rgba(0,0,0,0)",
        colorway=[ACCENT, SECONDARY],
        margin=dict(t=70, l=10, r=10, b=10),
        legend=dict(
            title="",
            font=dict(size=12, color=TEXT_PRIMARY),
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        hoverlabel=dict(
            bgcolor=BG_SURFACE,
            font_family=FONT_BODY,
            font_color=TEXT_PRIMARY,
            font_size=13,
            bordercolor=BORDER,
        ),
        coloraxis_colorbar=dict(
            title_font_color=TEXT_PRIMARY,
            tickfont=dict(color=TEXT_PRIMARY, size=12),
        ),
    )
    fig.update_xaxes(
        showgrid=False,
        linecolor=BORDER,
        tickfont=dict(color=TEXT_PRIMARY, size=12),
        title_font=dict(color=TEXT_PRIMARY, size=13, family=FONT_BODY),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=BORDER,
        zeroline=False,
        tickfont=dict(color=TEXT_PRIMARY, size=12),
        title_font=dict(color=TEXT_PRIMARY, size=13, family=FONT_BODY),
    )
    return fig


def metric_card(label: str, value: str, subtext: str | None = None):
    """Render a metric as a single bordered card, optionally with a breakdown line
    underneath the value, inside the same box (unlike st.metric + st.caption, which
    render as two separate, visually disconnected elements)."""
    subtext_html = (
        f'<div style="color:{TEXT_SECONDARY}; font-size:0.8rem; margin-top:0.45rem;">{subtext}</div>'
        if subtext
        else ""
    )
    st.markdown(
        f"""
        <div style="background-color:{BG_SURFACE}; border:1px solid {BORDER}; border-radius:4px;
                    padding:1rem 1.1rem 0.9rem 1.1rem; min-height:150px;
                    display:flex; flex-direction:column; justify-content:flex-start;">
            <div style="color:{TEXT_SECONDARY}; font-size:0.82rem; font-weight:500;">{label}</div>
            <div style="color:{TEXT_PRIMARY}; font-family:{FONT_BODY}; font-weight:600; font-size:1.9rem;
                        letter-spacing:-0.02em; font-variant-numeric:tabular-nums; margin-top:0.15rem;">
                {value}
            </div>
            {subtext_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------------
# Data loading: download (if stale) -> clean
# ----------------------------------------------------------------------------
raw_path = ensure_fresh_data()
sync_thumbnails(THUMBNAIL_URLS)
df = clean_data(str(raw_path), raw_path.stat().st_mtime)

st.title("Sheet Music Sales Dashboard")
st.markdown('<div class="mobile-only filters-label">Filters</div>', unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Sidebar filters (Artist -> Title cascade)
# ----------------------------------------------------------------------------
st.sidebar.header("Filters")

# ---- Date Sold range (applies to both tabs) ----
min_date_sold = df["Date Sold"].min().date()
max_date_sold = df["Date Sold"].max().date()
st.sidebar.markdown(
    f'<p style="color:{TEXT_PRIMARY}; font-size:1.05rem; font-weight:600; margin-bottom:0.4rem;">Date Sold</p>',
    unsafe_allow_html=True,
)
col_ds1, col_ds2 = st.sidebar.columns(2)
with col_ds1:
    st.markdown(
        f'<p style="color:{TEXT_SECONDARY}; font-size:0.78rem; font-weight:500; margin-bottom:0.35rem; text-align:center;">Start</p>',
        unsafe_allow_html=True,
    )
    start_sold = st.date_input(
        "Start", value=min_date_sold, min_value=min_date_sold, max_value=max_date_sold,
        key="date_sold_start", label_visibility="collapsed",
    )
with col_ds2:
    st.markdown(
        f'<p style="color:{TEXT_SECONDARY}; font-size:0.78rem; font-weight:500; margin-bottom:0.35rem; text-align:center;">End</p>',
        unsafe_allow_html=True,
    )
    end_sold = st.date_input(
        "End", value=max_date_sold, min_value=min_date_sold, max_value=max_date_sold,
        key="date_sold_end", label_visibility="collapsed",
    )

# Apply the Date Sold filter to the base dataframe used everywhere (Overview + Deep Dive)
if start_sold > end_sold:
    st.sidebar.error("Date Sold: Start must be before End.")
    df_base = df.iloc[0:0].copy()
else:
    df_base = df[
        (df["Date Sold"].dt.date >= start_sold) & (df["Date Sold"].dt.date <= end_sold)
    ].copy()

st.sidebar.markdown("---")

# ---- Transaction Type filter ----
st.sidebar.markdown(
    f'<p style="color:{TEXT_PRIMARY}; font-size:1.05rem; font-weight:600; margin-bottom:.6rem;">Transaction Type</p>',
    unsafe_allow_html=True,
)
show_purchase = st.sidebar.checkbox("Purchase (download)", value=True, key="tx_purchase")
show_view = st.sidebar.checkbox("View (subscription)", value=True, key="tx_view")

selected_tx_types = []
if show_purchase:
    selected_tx_types.append("Purchase")
if show_view:
    selected_tx_types.append("View")

st.sidebar.markdown("---")


# ---- ALL_ARTISTS_LABEL / artist_options / selected_artists lines ----
st.sidebar.markdown(
    f'<p style="color:{TEXT_PRIMARY}; font-size:1.05rem; font-weight:600; margin-bottom:.6rem;">Artist(s)</p>',
    unsafe_allow_html=True,
)

all_artists = sorted(df_base["Artist"].unique())

for a in all_artists:
    if f"artist_cb_{a}" not in st.session_state:
        st.session_state[f"artist_cb_{a}"] = True

def _toggle_all_artists():
    new_val = st.session_state["artist_all"]
    for a in all_artists:
        st.session_state[f"artist_cb_{a}"] = new_val

st.sidebar.checkbox(
    "All", value=True, key="artist_all", on_change=_toggle_all_artists
)

st.markdown(
    f"""
    <style>
    [data-testid="stSidebar"] div[data-testid="stVerticalBlock"][data-test-scroll-behavior="normal"] {{
        margin-top: -0.2rem !important;
        margin-bottom: 0.75rem !important;
        padding: 0.5rem 0.5rem 0.5rem 0.5rem !important;
        border: 1px solid {BORDER} !important;
        border-radius: 4px;
    }}
    [data-testid="stSidebar"] div[data-testid="stVerticalBlock"][data-test-scroll-behavior="normal"]::-webkit-scrollbar {{
        width: 12px !important;
    }}
    [data-testid="stSidebar"] div[data-testid="stVerticalBlock"][data-test-scroll-behavior="normal"]::-webkit-scrollbar-thumb {{
        background-color: {BORDER} !important;
        border-radius: 3px !important;
    }}
    [data-testid="stSidebar"] div[data-testid="stVerticalBlock"][data-test-scroll-behavior="normal"]::-webkit-scrollbar-track {{
        background-color: transparent !important;
    }}
    [data-testid="stSidebar"] .st-key-artist_all {{
        margin-left: 0.5rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar.container(height=350):
    for a in all_artists:
        st.checkbox(a, key=f"artist_cb_{a}")

selected_artists = [a for a in all_artists if st.session_state[f"artist_cb_{a}"]]

# Empty selection = no filter applied (treat as "All Artists")
if selected_artists:
    title_pool = df_base.loc[df_base["Artist"].isin(selected_artists), "Title"]
else:
    title_pool = df_base["Title"]

title_options = sorted(title_pool.unique())

st.sidebar.markdown(
    f'<p style="color:{TEXT_PRIMARY}; font-size:1.05rem; font-weight:600; margin-bottom:1rem;">Title(s)</p>',
    unsafe_allow_html=True,
)

for t in title_options:
    if f"title_cb_{t}" not in st.session_state:
        st.session_state[f"title_cb_{t}"] = True

with st.sidebar.container(height=350):
    for t in title_options:
        st.checkbox(t, key=f"title_cb_{t}")

selected_titles = [t for t in title_options if st.session_state.get(f"title_cb_{t}", True)]

# Filtered dataframe used throughout the "deep dive" tab
filtered = df_base.copy()
if selected_artists:
    filtered = filtered[filtered["Artist"].isin(selected_artists)]
if selected_titles:
    filtered = filtered[filtered["Title"].isin(selected_titles)]
else:
    filtered = filtered.iloc[0:0]  # nothing selected -> empty
if selected_tx_types:
    filtered = filtered[filtered["Transaction Type"].isin(selected_tx_types)]
else:
    filtered = filtered.iloc[0:0]  # nothing selected -> empty

st.sidebar.markdown("---")
st.sidebar.caption(
    f"Showing {filtered.shape[0]:,} of {df.shape[0]:,} rows based on current filters."
)

# ----------------------------------------------------------------------------
# Tabs
# ----------------------------------------------------------------------------
tab_overview, tab_deep_dive = st.tabs(["Overview", "Artist / Title Deep Dive"])

# ============================================================================
# TAB 1: OVERVIEW  (reflects all sidebar filters: Date Sold + Artist/Title(s))
# ============================================================================
with tab_overview:
    st.caption(
        "Totals reflect all filters currently selected in the sidebar."
    )

    total_qty = filtered["Quantity"].sum()
    total_sales = filtered["Sales"].sum()
    total_comm = filtered["Est. Commissions"].sum()

    qty_by_type = filtered.groupby("Transaction Type")["Quantity"].sum()
    qty_purchase = qty_by_type.get("Purchase", 0)
    qty_view = qty_by_type.get("View", 0)

    sales_by_type = filtered.groupby("Transaction Type")["Sales"].sum()
    sales_purchase = sales_by_type.get("Purchase", 0)
    sales_view = sales_by_type.get("View", 0)

    comm_by_type = filtered.groupby("Transaction Type")["Est. Commissions"].sum()
    comm_purchase = comm_by_type.get("Purchase", 0)
    comm_view = comm_by_type.get("View", 0)

    avg_comm_purchase = comm_purchase / qty_purchase if qty_purchase else 0
    avg_comm_view = comm_view / qty_view if qty_view else 0

    m1, m2, m3 = st.columns(3)
    with m1:
        metric_card(
            "Total Titles Sold",
            f"{total_qty:,}",
            subtext=f"By Transaction Type:<br> Purchase (download): {qty_purchase:,} · View (subscription): {qty_view:,}",
        )
    with m2:
        metric_card(
            "Total Sales",
            f"${total_sales:,.2f}",
            subtext=f"By Transaction Type:<br> Purchase (download): ${sales_purchase:,.2f} · View (subscription): ${sales_view:,.2f}",
        )
    with m3:
        metric_card(
            "Total Est. Commissions",
            value=f'${total_comm:,.2f}',
            subtext=
                f"Avg. Commission by Transaction Type:<br> Purchase (download): ${avg_comm_purchase:,.2f} · View (subscription): ${avg_comm_view:,.2f}",
        )

    unique_artist_count = filtered["Artist"].nunique()
    unique_title_count = filtered["Title"].nunique()
    unique_titles = filtered["Title"].drop_duplicates()
    deactivated_count = unique_titles.str.contains("(deactivated)", regex=False).sum()
    active_count = unique_title_count - deactivated_count

    m4, m5 = st.columns(2)
    with m4:
        metric_card("Unique Artists", f"{unique_artist_count:,}")
    with m5:
        metric_card(
            "Unique Titles",
            f"{unique_title_count:,}",
            subtext=f"Active: {active_count:,} · Deactivated: {deactivated_count:,}",
        )

    # ---- Monthly averages ----
    if filtered.empty:
        monthly = pd.DataFrame(columns=["Quantity", "Sales", "Est. Commissions"])
    else:
        # Every month in the selected Date Sold range, so months with no
        # sales count as 0 instead of being skipped (which would inflate the averages)
        all_months = pd.period_range(start_sold, end_sold, freq="M")
        monthly = (
            filtered.groupby(filtered["Date Sold"].dt.to_period("M"))[
                ["Quantity", "Sales", "Est. Commissions"]
            ]
            .sum()
            .reindex(all_months, fill_value=0)
        )

    def fmt_units(v):
        return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.1f}"

    def fmt_money(v):
        return f"${v:,.2f}"

    def monthly_card(label, col, fmt):
        s = monthly[col]
        if s.empty:
            metric_card(label, "—")
            return
        lo, hi = s.idxmin(), s.idxmax()
        metric_card(
            label,
            fmt(s.mean()),
            subtext=(
                f"Min: {fmt(s.min())} ({lo.strftime('%b %Y')})<br>"
                f"Median: {fmt(s.median())}<br>"
                f"Max: {fmt(s.max())} ({hi.strftime('%b %Y')})"
            ),
        )

    a1, a2, a3 = st.columns(3)
    with a1:
        monthly_card("Avg. Titles Sold per Month", "Quantity", fmt_units)
    with a2:
        monthly_card("Avg. Sales per Month", "Sales", fmt_money)
    with a3:
        monthly_card("Avg. Est. Commissions per Month", "Est. Commissions", fmt_money)

    if not monthly.empty:
        st.caption(
            f"Monthly averages cover {len(monthly)} months "
            f"({monthly.index[0].strftime('%b %Y')} – {monthly.index[-1].strftime('%b %Y')}). "
            "The first and last month may be partial. Months with no sales count as 0."
        )

    st.markdown("---")



    # ---- Artists by Units Sold ----
    st.subheader("Artists by Units Sold, Est. Commissions")
    artist_summary = (
        filtered.groupby("Artist")
        .agg(
            Quantity=("Quantity", "sum"),
            Sales=("Sales", "sum"),
            Est_Commissions=("Est. Commissions", "sum"),
        )
        .reset_index()
        .sort_values("Quantity", ascending=False)
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        top_n_artists = artist_summary.sort_values("Quantity")
        fig_artists = px.bar(
            top_n_artists,
            x="Quantity",
            y="Artist",
            orientation="h",
            title="Units Sold by Artist",
            labels={"Artist": "", "Quantity": "Units (Downloads + Views)"},
        )
        fig_artists.update_traces(
            marker_color=ACCENT, hovertemplate="Units: %{x}<extra></extra>"
        )
        fig_artists.update_layout(height=max(400, 28 * len(top_n_artists)))
        st.plotly_chart(lock_fig(style_fig(fig_artists)), use_container_width=True, config=STATIC_CHART_CONFIG)
    with col2:
        top_n_artists_money = artist_summary.sort_values("Est_Commissions")
        fig_artists_money = px.bar(
            top_n_artists_money,
            x="Est_Commissions",
            y="Artist",
            orientation="h",
            title="Est. Commissions by Artist",
            labels={"Est_Commissions": "Est. Commissions ($)", "Artist": ""},
        )
        fig_artists_money.update_traces(
            marker_color=SECONDARY, hovertemplate="Est. Commissions: $%{x:,.2f}<extra></extra>"
        )
        fig_artists_money.update_layout(height=max(400, 28 * len(top_n_artists_money)))
        st.plotly_chart(lock_fig(style_fig(fig_artists_money)), use_container_width=True, config=STATIC_CHART_CONFIG)

    with st.expander(f"View all {artist_summary.shape[0]} artists"):
        st.dataframe(
            artist_summary.rename(
                columns={"Quantity": "Titles Sold", "Est_Commissions": "Est. Commissions"}
            ).style.format({"Sales": "${:,.2f}", "Est. Commissions": "${:,.2f}"}),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("---")

    # ---- Top Titles ----
    st.subheader("Titles by Units Sold, Est. Commissions")
    title_summary = (
        filtered.groupby(["Artist", "Title"])
        .agg(
            Quantity=("Quantity", "sum"),
            Sales=("Sales", "sum"),
            Est_Commissions=("Est. Commissions", "sum"),
        )
        .reset_index()
        .sort_values("Quantity", ascending=False)
    )
    title_summary["Artist - Title"] = title_summary["Artist"] + " - " + title_summary["Title"]

    # Map each Title to its cached thumbnail path (if any), as a lookup —
    # not part of the groupby, so a missing thumbnail can never drop a
    # title out of the summary or the charts below.
    thumb_lookup = filtered[["Title", "Thumbnail"]].dropna(subset=["Thumbnail"]).drop_duplicates(subset=["Title"])
    thumb_lookup = dict(zip(thumb_lookup["Title"], thumb_lookup["Thumbnail"]))
    title_summary["Preview"] = title_summary["Title"].map(thumb_lookup)

    col3, col4 = st.columns([1, 1])
    with col3:
        top_n_titles = title_summary.sort_values("Quantity")
        fig_titles = px.bar(
            top_n_titles,
            x="Quantity",
            y="Artist - Title",
            orientation="h",
            title="Units Sold by Title",
            labels={"Artist - Title": ""},
        )
        fig_titles.update_traces(
            marker_color=ACCENT,
            hovertemplate="Quantity: %{x}<extra></extra>",
        )
        fig_titles.update_layout(height=max(400, 28 * len(top_n_titles)))
        st.plotly_chart(lock_fig(style_fig(fig_titles)), use_container_width=True, config=STATIC_CHART_CONFIG)
    with col4:
        top_n_titles_money = title_summary.sort_values("Est_Commissions")
        fig_titles_money = px.bar(
            top_n_titles_money,
            x="Est_Commissions",
            y="Artist - Title",
            orientation="h",
            title="Est. Commissions by Title",
            labels={"Est_Commissions": "Est. Commissions ($)", "Artist - Title": ""},
        )
        fig_titles_money.update_traces(
            marker_color=SECONDARY,
            hovertemplate="Est. Commissions: $%{x:,.2f}<extra></extra>",
        )
        fig_titles_money.update_layout(height=max(400, 28 * len(top_n_titles_money)))
        st.plotly_chart(lock_fig(style_fig(fig_titles_money)), use_container_width=True, config=STATIC_CHART_CONFIG)

    with st.expander(f"View all {title_summary.shape[0]} titles with sheet music previews"):
        display_cols = ["Preview", "Artist", "Title", "Quantity", "Sales", "Est_Commissions"]
        st.caption("Select a row to see sheet music preview")
        event = st.dataframe(
            title_summary[display_cols].rename(
                columns={"Quantity": "Titles Sold", "Est_Commissions": "Est. Commissions"}
            ),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Preview": st.column_config.ImageColumn("Preview", width="small"),
                "Sales": st.column_config.NumberColumn("Sales", format="$%.2f"),
                "Est. Commissions": st.column_config.NumberColumn("Est. Commissions", format="$%.2f"),
            },
            on_select="rerun",             
            selection_mode="single-row",   
            key="titles_table",            
        )

        # NEW: open the popup when a row is clicked
        rows = event.selection.rows
        if rows and st.session_state.get("last_cover_row") != rows[0]:
            st.session_state["last_cover_row"] = rows[0]
            row = title_summary.iloc[rows[0]]
            img = row["Preview"]
            if isinstance(img, str) and img:
                show_cover(row["Title"], img)
        elif not rows:
            st.session_state["last_cover_row"] = None

    st.markdown("---")

    # ---- Map: Purchases by Location ----
    st.subheader("Purchases by Location")
    st.caption(
        "Location data is available only for **Purchase** (download) - not **View** (subscription) - transactions."
    )
    purchases = filtered[filtered["Transaction Type"] == "Purchase"].dropna(subset=["Location"])

    if purchases.empty:
        st.info("No purchase transactions with a recorded location for this selection.")
    else:
        location_summary = (
            purchases.groupby("Location")
            .agg(Quantity=("Quantity", "sum"), Sales=("Sales", "sum"))
            .reset_index()
            .sort_values("Quantity", ascending=False)
        )

        # Starts at a visible rose tint (not beige) so low-selling countries
        # stand out clearly from countries with no sales (land = BG_MAIN)
        MAP_SCALE = [
            [0.0, "#E2B4BD"],
            [0.5, "#A9506A"],
            [1.0, "#5A1C29"],
        ]

        fig_map = px.choropleth(
            location_summary,
            locations="Location",
            locationmode="country names",
            color="Quantity",
            hover_data={"Sales": ":$,.2f"},
            color_continuous_scale=MAP_SCALE,
        )
        fig_map.update_geos(
            bgcolor="rgba(0,0,0,0)", landcolor=BG_MAIN, showcountries=True, countrycolor=BORDER,
            projection_type="mercator",
            lataxis_range=[-58, 85],
        )

        # Rough phone detection from the browser's user agent
        user_agent = st.context.headers.get("User-Agent", "")
        is_mobile = "Mobi" in user_agent or "Android" in user_agent

        style_fig(fig_map)  # apply the shared style first...
        # ...then override the parts that don't suit a map (must come AFTER style_fig)
        fig_map.update_layout(
            height=360 if is_mobile else 550,
            margin=dict(t=45, l=0, r=0, b=10),   # room at the top for the zoom/pan toolbar
            coloraxis_colorbar=dict(
                orientation="h",                 # horizontal key under the map
                x=0.5, xanchor="center",
                y=-0.02, yanchor="top",
                len=0.6 if is_mobile else 0.4,
                thickness=12,
                title=dict(text="Units sold", side="top"),
            ),
        )

        if is_mobile:
            st.plotly_chart(fig_map, use_container_width=True, config=MAP_CONFIG)
        else:
            map_col_left, map_col_center, map_col_right = st.columns([1, 6, 1])
            with map_col_center:
                st.plotly_chart(fig_map, use_container_width=True, config=MAP_CONFIG)

        with st.expander("View full location breakdown"):
            st.dataframe(
                location_summary.style.format({"Sales": "${:,.2f}"}),
                use_container_width=True,
                hide_index=True,
            )

# ============================================================================
# TAB 2: ARTIST / TITLE DEEP DIVE  (respects sidebar filters)
# ============================================================================
with tab_deep_dive:
    if not selected_artists:
        header_label = "All Artists"
    elif len(selected_artists) == 1:
        header_label = selected_artists[0]
    else:
        header_label = f"{len(selected_artists)} Artists Selected"
    st.subheader(f"Details for: {header_label}")

    if filtered.empty:
        st.warning("No data matches the current filters. Adjust the Artist/Title selection in the sidebar.")
    else:
        # ---- Quantity sold over time ----
        time_qty = (
            filtered.groupby("Date Sold").agg(Quantity=("Quantity", "sum")).reset_index()
        )
        fig_qty_time = px.line(
            time_qty,
            x="Date Sold",
            y="Quantity",
            markers=True,
            title="Titles Sold Over Time",
        )
        fig_qty_time.update_traces(line_color=ACCENT, marker_color=ACCENT)
        st.plotly_chart(lock_fig(style_fig(fig_qty_time)), use_container_width=True, config=STATIC_CHART_CONFIG)

        # ---- Sales & Est. Commissions over time ----
        time_money = (
            filtered.groupby("Date Sold")
            .agg(Sales=("Sales", "sum"), Est_Commissions=("Est. Commissions", "sum"))
            .reset_index()
            .rename(columns={"Est_Commissions": "Est. Commissions"})
        )
        fig_money_time = px.line(
            time_money,
            x="Date Sold",
            y=["Sales", "Est. Commissions"],
            markers=True,
            title="Sales & Est. Commissions Over Time",
            labels={"value": "Amount ($)", "variable": ""},
        )
        st.plotly_chart(lock_fig(style_fig(fig_money_time)), use_container_width=True, config=STATIC_CHART_CONFIG)

        # ---- Channel breakdown ----
        col5, col6 = st.columns([1, 1])
        with col5:
            channel_summary = (
                filtered.groupby("Channel")
                .agg(Quantity=("Quantity", "sum"))
                .reset_index()
                .sort_values("Quantity", ascending=False)
            )
            fig_channel = px.bar(
                channel_summary,
                x="Channel",
                y="Quantity",
                title="Titles Sold by Channel",
            )
            fig_channel.update_traces(marker_color=ACCENT)
            st.plotly_chart(lock_fig(style_fig(fig_channel)), use_container_width=True, config=STATIC_CHART_CONFIG)

        with col6:
            # ---- Published dates for the selected title(s) ----
            pub_dates = (
                filtered[["Artist", "Title", "Date Published"]]
                .drop_duplicates()
                .sort_values("Date Published")
            )
            pub_dates["Date Published"] = pub_dates["Date Published"].dt.date
            st.markdown("**Title(s) by Publish Date**")
            st.dataframe(pub_dates, use_container_width=True, hide_index=True)

        st.markdown("---")

        # ---- Transaction Type split (Purchase vs. View) ----
        st.subheader("Purchase vs. View")
        tx_summary = (
            filtered.groupby("Transaction Type")
            .agg(
                Quantity=("Quantity", "sum"),
                Sales=("Sales", "sum"),
                Est_Commissions=("Est. Commissions", "sum"),
            )
            .reset_index()
            .rename(columns={"Est_Commissions": "Est. Commissions"})
        )
        col7, col8 = st.columns([1, 2])
        with col7:
            st.dataframe(
                tx_summary.style.format({"Sales": "${:,.2f}", "Est. Commissions": "${:,.2f}"}),
                use_container_width=True,
                hide_index=True,
            )
        with col8:
            fig_tx = px.bar(
                tx_summary,
                x="Transaction Type",
                y="Est. Commissions",
                title="Est. Commissions by Transaction Type",
                labels={"Est. Commissions": "Est. Commissions ($)"},
            )
            fig_tx.update_traces(
                marker_color=SECONDARY,
                texttemplate="$%{y:,.2f}",
                textposition="outside",
                hoverinfo="skip",
                hovertemplate=None,
            )
            st.plotly_chart(lock_fig(style_fig(fig_tx)), use_container_width=True, config=STATIC_CHART_CONFIG)

        st.markdown("Spread of **Est. Commissions** per Unit Sold, by Transaction Type")
        per_unit = filtered.copy()
        per_unit["Est. Commissions per Unit"] = per_unit["Est. Commissions"] / per_unit["Quantity"]
        tx_stats = (
            per_unit.groupby("Transaction Type")["Est. Commissions per Unit"]
            .agg(Min="min", Median="median", Mean="mean", Max="max")
            .reset_index()
        )
        st.dataframe(
            tx_stats.style.format(
                {"Min": "${:,.2f}", "Median": "${:,.2f}", "Mean": "${:,.2f}", "Max": "${:,.2f}"}
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("---")
