"""Downloads a fresh ArrangeMe report and pushes it to GitHub if it changed.
Run weekly by launchd, and at sign-in to catch up on a missed Sunday."""
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from download_report import download_csv, PROJECT_DIR, RAW_LATEST_PATH

STAMP = Path.home() / ".sheetmusic_last_run"

def most_recent_sunday_6am(now):
    days_since_sunday = (now.weekday() - 6) % 7   # Sunday = 6
    sunday = (now - timedelta(days=days_since_sunday)).replace(
        hour=6, minute=0, second=0, microsecond=0)
    if sunday > now:          # it's Sunday but before 6 AM
        sunday -= timedelta(days=7)
    return sunday


def already_ran_this_week():
    if not STAMP.exists():
        return False
    last = datetime.fromisoformat(STAMP.read_text().strip())
    return last >= most_recent_sunday_6am(datetime.now())


def mark_done():
    STAMP.write_text(datetime.now().isoformat())

def git(*args, check=True):
    """Run a git command inside the project folder."""
    return subprocess.run(["git", *args], cwd=PROJECT_DIR, check=check)


def current_branch():
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=PROJECT_DIR, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def main():
    print(f"--- Run started {datetime.now():%Y-%m-%d %H:%M} ---")

    if already_ran_this_week():
        print("Already ran since Sunday 6 AM — skipping.")
        return

    branch = current_branch()
    if branch != "main":
        print(f"Skipped: the project is on branch '{branch}', not main.")
        return

    git("pull", "--rebase", "--autostash")
    download_csv()

    csv = str(RAW_LATEST_PATH)
    git("add", csv)
    if git("diff", "--cached", "--quiet", "--", csv, check=False).returncode == 0:
        print("No new sales. Nothing to push.")
        mark_done()
        return

    git("commit", "-m", "Weekly sales report update", "--", csv)
    git("push")
    print("Pushed new report.")
    mark_done()


if __name__ == "__main__":
    main()