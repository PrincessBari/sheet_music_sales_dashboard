"""Downloads a fresh ArrangeMe report and pushes it to GitHub if it changed.
Run weekly by launchd."""
import subprocess
from datetime import datetime

from download_report import download_csv, PROJECT_DIR, RAW_LATEST_PATH


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

    branch = current_branch()
    if branch != "main":
        print(f"Skipped: the project is on branch '{branch}', not main.")
        return

    git("pull", "--rebase")
    download_csv()

    csv = str(RAW_LATEST_PATH)
    git("add", csv)
    if git("diff", "--cached", "--quiet", "--", csv, check=False).returncode == 0:
        print("No new sales. Nothing to push.")
        return

    git("commit", "-m", "Weekly sales report update", "--", csv)
    git("push")
    print("Pushed new report.")


if __name__ == "__main__":
    main()