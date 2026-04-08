# Research Sweeps

Daily and weekly internet sweep outputs live here.

## Layout

- `daily/` - one markdown digest per day and profile
- `health/` - source health for each run (`ok`, `cached`, `failed`)
- `validation/` - follow-up queue for social discoveries with outbound links
- `weekly/` - weekly rollups
- `state/` - cached source snapshots for diffing
- `health/degraded_sources.json` - rolling source degradation state across runs

## Runner

Source manifest:

- `sweeps/sources.json`

Script:

- `sweeps/run_daily.py`
- `sweeps/register_tasks.ps1`
- `sweeps/build_weekly.py`
- `sweeps/send_digest_email.py`
- `sweeps/run_workflow.py`
- `sweeps/email_env.example`

## Example

```powershell
python sweeps/run_daily.py
python sweeps/run_daily.py --dry-run
python sweeps/run_daily.py --date 2026-04-07
python sweeps/run_daily.py --bootstrap-emit
python sweeps/run_daily.py --profile extended
python sweeps/run_daily.py --profile all
python sweeps/build_weekly.py --date 2026-04-07 --profile core
python sweeps/send_digest_email.py --profile core --date 2026-04-07 --dry-run
python sweeps/run_workflow.py --profile core
```

The script is intentionally narrow:

- no external dependencies
- feed-first
- simple page hashing fallback
- writes markdown digests into `docs/sweeps/daily/`
- writes source health reports into `docs/sweeps/health/`
- writes validation queues into `docs/sweeps/validation/`
- concurrent fetching
- profile-based watchlists (`core`, `extended`, `all`)
- top-signals summary at the top of each digest
- weekly rollup stubs under `docs/sweeps/weekly/`
- optional Resend email delivery as a separate send step

Output filenames:

- `core`: `docs/sweeps/daily/YYYY-MM-DD.md`
- `extended`: `docs/sweeps/daily/YYYY-MM-DD.extended.md`
- `all`: `docs/sweeps/daily/YYYY-MM-DD.all.md`
- validation queue follows the same suffix pattern under `docs/sweeps/validation/`
- health report follows the same suffix pattern under `docs/sweeps/health/`

On first real run, the script bootstraps local state from the current snapshot and does not emit historical backlog unless `--bootstrap-emit` is provided.

Current X approach:

- curated X accounts are ingested via `OpenRSS` feed bridges
- this supports automatic discovery without building a brittle first-party scraper yet
- X items should still be treated as discovery-first and validated before decisions
- outbound links in new social items are automatically resolved into a validation queue
- follow-up links are typed (`github`, `release`, `blog`, `paper`, `video`) and prioritized
- follow-up links are enriched with resolved domain and fetched page title when available
- follow-up links also carry a short fetched page description when available
- high-priority follow-ups can create intake stubs under `docs/wiki/raw/`
- transient feed failures fall back to cached state and are recorded in the health report
- repeated failures/cached fallbacks accumulate in `degraded_sources.json`
- sources degraded for repeated runs are quarantined automatically, then retried after a cooldown window

Recommended schedule:

- `core` every morning
- `extended` once later in the day or on a separate schedule
- `all` only when you want a full sweep
- scheduled workflow now follows `generate -> optional send`

See also:

- `docs/sweeps/SCHEDULING.md`
