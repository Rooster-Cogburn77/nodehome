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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run daily sweep workflow and optionally send digest email.")
    parser.add_argument("--profile", choices=("core", "extended", "all"), default="core")
    parser.add_argument("--date", dest="run_date", help="Override date in YYYY-MM-DD format.")
    parser.add_argument("--skip-x-email-ingest", action="store_true", help="Do not ingest X notification emails first.")
    parser.add_argument("--skip-fact-notebook", action="store_true", help="Do not update the sweep fact notebook.")
    parser.add_argument("--skip-email", action="store_true", help="Do not run the email send step.")
    return parser.parse_args()


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
        return 0

    email_enabled = os.getenv("DIGEST_EMAIL_ENABLED", "false").strip().lower() == "true"
    if not email_enabled:
        print("DIGEST_EMAIL_ENABLED is not true; skipping email step.")
        return 0

    email_cmd = [python_exe, str(SEND_EMAIL), "--profile", args.profile]
    if args.run_date:
        email_cmd.extend(["--date", args.run_date])
    subprocess.run(email_cmd, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
