# Scheduling

Use Windows Task Scheduler for the daily sweep jobs.

## Recommended Schedule

- `core` at `07:00`
- `extended` at `13:00`
- `weekly` on Sunday at `08:30`

This keeps the fast must-watch pass separate from the broader scene pass.
The weekly task builds the notebook rollup but does not send email by default.

## One-Command Registration

From the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File .\sweeps\register_tasks.ps1
```

Optional overrides:

```powershell
powershell -ExecutionPolicy Bypass -File .\sweeps\register_tasks.ps1 -PythonExe python -CoreTime 07:30 -ExtendedTime 14:00
```

## What It Creates

- `SovereignNodeSweepCore`
- `SovereignNodeSweepExtended`
- `SovereignNodeSweepWeekly`

Each task runs:

```powershell
python C:\Users\bmoor\Local_AI\sweeps\run_workflow.py --profile core
python C:\Users\bmoor\Local_AI\sweeps\run_workflow.py --profile extended
python C:\Users\bmoor\Local_AI\sweeps\run_workflow.py --profile all --weekly --skip-email
```

## Verify

```powershell
schtasks /Query /TN SovereignNodeSweepCore /V /FO LIST
schtasks /Query /TN SovereignNodeSweepExtended /V /FO LIST
schtasks /Query /TN SovereignNodeSweepWeekly /V /FO LIST
```

## Run Immediately

```powershell
schtasks /Run /TN SovereignNodeSweepCore
schtasks /Run /TN SovereignNodeSweepExtended
schtasks /Run /TN SovereignNodeSweepWeekly
```

## Remove

```powershell
schtasks /Delete /TN SovereignNodeSweepCore /F
schtasks /Delete /TN SovereignNodeSweepExtended /F
schtasks /Delete /TN SovereignNodeSweepWeekly /F
```

## Notes

- Tasks are created with `/F`, so rerunning the registration script updates them.
- The workflow runner loads `.env` and `sweeps/.env` automatically, so Task Scheduler does not need secrets embedded in the task command.
- Already-set environment variables win over `.env` values; root `.env` wins over `sweeps/.env`.
- Output files are written under `docs/sweeps/daily/`.
- `core` writes `YYYY-MM-DD.md`.
- `extended` writes `YYYY-MM-DD.extended.md`.
- If `DIGEST_EMAIL_ENABLED=true` and Resend env vars are present, the workflow sends the digest after generation.
- Weekly rollup generation is manual or scheduled via `--weekly`.
- Weekly email requires `DIGEST_EMAIL_ENABLED=true` and either `DIGEST_WEEKLY_EMAIL_ENABLED=true` or `--send-weekly`.
