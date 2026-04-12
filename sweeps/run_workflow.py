#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RUN_DAILY = ROOT / "sweeps" / "run_daily.py"
SEND_EMAIL = ROOT / "sweeps" / "send_digest_email.py"
INGEST_X_EMAIL = ROOT / "sweeps" / "ingest_x_email.py"
FACT_NOTEBOOK = ROOT / "sweeps" / "fact_notebook.py"
BUILD_WEEKLY = ROOT / "sweeps" / "build_weekly.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run daily sweep workflow and optionally send digest email.")
    parser.add_argument("--profile", choices=("core", "extended", "all"), default="core")
    parser.add_argument("--date", dest="run_date", help="Override date in YYYY-MM-DD format.")
    parser.add_argument("--skip-x-email-ingest", action="store_true", help="Do not ingest X notification emails first.")
    parser.add_argument("--skip-fact-notebook", action="store_true", help="Do not update the sweep fact notebook.")
    parser.add_argument("--skip-email", action="store_true", help="Do not run the email send step.")
    parser.add_argument("--weekly", action="store_true", help="Build the current ISO-week rollup after daily ingest.")
    parser.add_argument("--send-weekly", action="store_true", help="Send the weekly rollup email when --weekly is used.")
    return parser.parse_args()


def iso_week_label(run_date: date) -> str:
    year, week, _ = run_date.isocalendar()
    return f"{year}-W{week:02d}"


def main() -> int:
    args = parse_args()
    python_exe = sys.executable

    x_email_ready = all(
        os.getenv(name, "").strip()
        for name in ("X_EMAIL_IMAP_HOST", "X_EMAIL_IMAP_USERNAME", "X_EMAIL_IMAP_PASSWORD")
    )
    if args.skip_x_email_ingest:
        print("Skipping X email ingest by request.")
    elif x_email_ready:
        subprocess.run([python_exe, str(INGEST_X_EMAIL)], check=True)
    else:
        print("X email ingest not configured; skipping.")

    daily_cmd = [python_exe, str(RUN_DAILY), "--profile", args.profile]
    if args.run_date:
        daily_cmd.extend(["--date", args.run_date])
    subprocess.run(daily_cmd, check=True)

    if args.skip_fact_notebook:
        print("Skipping fact notebook ingest by request.")
    else:
        notebook_cmd = [python_exe, "-m", "sweeps.fact_notebook", "--profile", args.profile]
        if args.run_date:
            notebook_cmd.extend(["--date", args.run_date])
        subprocess.run(notebook_cmd, check=True)

    if args.skip_email:
        if not args.weekly:
            return 0

    email_enabled = os.getenv("DIGEST_EMAIL_ENABLED", "false").strip().lower() == "true"
    if not args.skip_email and not email_enabled:
        print("DIGEST_EMAIL_ENABLED is not true; skipping email step.")
    elif not args.skip_email:
        email_cmd = [python_exe, str(SEND_EMAIL), "--profile", args.profile]
        if args.run_date:
            email_cmd.extend(["--date", args.run_date])
        subprocess.run(email_cmd, check=True)

    if args.weekly:
        weekly_date = date.fromisoformat(args.run_date) if args.run_date else date.today()
        weekly_cmd = [python_exe, str(BUILD_WEEKLY), "--profile", args.profile, "--date", weekly_date.isoformat()]
        weekly_result = subprocess.run(weekly_cmd, check=True, capture_output=True, text=True)
        weekly_path = weekly_result.stdout.strip().splitlines()[-1]
        print(f"Weekly rollup: {weekly_path}")

        weekly_email_enabled = (
            not args.skip_email
            and (
                args.send_weekly
                or os.getenv("DIGEST_WEEKLY_EMAIL_ENABLED", "false").strip().lower() == "true"
            )
        )
        if not weekly_email_enabled:
            print("Weekly email disabled; set DIGEST_WEEKLY_EMAIL_ENABLED=true or pass --send-weekly to send it.")
            return 0
        if not email_enabled:
            print("DIGEST_EMAIL_ENABLED is not true; skipping weekly email send.")
            return 0
        weekly_subject = f"Weekly Sweep - {iso_week_label(weekly_date)}"
        weekly_email_cmd = [
            python_exe,
            str(SEND_EMAIL),
            "--input",
            weekly_path,
            "--subject",
            weekly_subject,
        ]
        subprocess.run(weekly_email_cmd, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
