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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run daily sweep workflow and optionally send digest email.")
    parser.add_argument("--profile", choices=("core", "extended", "all"), default="core")
    parser.add_argument("--date", dest="run_date", help="Override date in YYYY-MM-DD format.")
    parser.add_argument("--skip-email", action="store_true", help="Do not run the email send step.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    python_exe = sys.executable
    daily_cmd = [python_exe, str(RUN_DAILY), "--profile", args.profile]
    if args.run_date:
        daily_cmd.extend(["--date", args.run_date])
    subprocess.run(daily_cmd, check=True)

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
