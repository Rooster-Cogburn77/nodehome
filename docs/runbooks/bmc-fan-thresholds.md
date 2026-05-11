# BMC Fan Threshold — FANB Cycling Fix

**Status:** Applied 2026-05-10 (Session 16, post-rack-install). Survives reboot (BMC NVRAM).
**Board:** Supermicro H12SSL-i v2.0, BMC firmware `01.05.02`.

## Symptom

Audible fan ramp cycle on a steady ~6-7 second interval, present even when the host is at full idle (no GPU compute, CPU at 27-31°C, all containers running but at rest). The whole motherboard fan zone audibly ramps up and then back down on the same rhythm.

## Diagnosis path

Standard idle diagnostics confirmed the GPUs were not the source:
- `nvidia-smi`: all 3 cards at P8, 1 MiB memory, 0% util, no processes
- `sensors`: EPYC 7302P core temps 27-31°C (deep idle), no variance
- `nvidia-smi dmon -s pu -d 1`: GPU power steady at 17-24W, no periodic spikes

Querying the BMC fan table surfaced the actual cause:

```
$ sudo ipmitool sdr type fan
FAN1   | 41h | ns  | 29.1 | No Reading
FAN2   | 42h | ns  | 29.2 | No Reading
FAN3   | 43h | ns  | 29.3 | No Reading
FAN4   | 44h | ok  | 29.4 | 1400 RPM
FAN5   | 45h | ok  | 29.5 | 3220 RPM
FANA   | 46h | ok  | 29.6 | 1820 RPM
FANB   | 47h | lcr | 29.7 | 420 RPM    ← Lower Critical
```

Second query immediately after caught FANB at 1960 RPM with status `ok`, confirming FANB is oscillating between ~420 and ~1960 RPM rather than reading phantom noise from an empty header.

## Root cause

FANB is a physical fan that stalls intermittently at the BMC's commanded low PWM. Each stall drops it below the `lcr` (Lower Critical, 420 RPM) threshold. The Supermicro BMC interprets that as a fan fault and responds by ramping all other motherboard fans (FAN4, FAN5, FANA) to a "safe" speed. After ~6-7 seconds (the BMC's fan recovery poll interval), it re-checks, sees FANB recovered to 1960 RPM, and ramps the others back down. Cycle repeats.

The audible cycling is the BMC's fault response on the other fans, not FANB itself.

## Fix

Lower the FANB `lcr` threshold so the BMC stops treating its stall behavior as a fault:

```bash
sudo ipmitool sensor thresh FANB lcr 100
```

Pre-change threshold values for FANB (restore point):
- Lower Non-Recoverable: `na`
- **Lower Critical: 420.000**
- Lower Non-Critical: `na`
- Negative Hysteresis: 140

After the change, `Lower Critical` reads 100. With the 140 RPM negative hysteresis, FANB cannot trip the threshold under any plausible operation. Cycling stops within ~10 seconds.

## What the fix does and does not do

**Does:** stops the BMC from interpreting FANB's stall as a fault. Stops the cascade ramp-and-recover on the other fans. Eliminates the audible ~6-7s cycle.

**Does not:**
- Disable any fan.
- Change cooling capacity.
- Affect monitoring on FAN4, FAN5, or FANA (those keep their default thresholds).
- Fix FANB itself — it still pulses between ~420 and ~1960 RPM. If FANB is audibly its own source of noise (faint single-fan pulse rather than whole-rack ramp), the underlying fix is to identify which physical fan FANB is connected to and either disconnect, replace, or move to a different control zone. That work is deferred until/unless FANB becomes its own audible nuisance.

## Persistence

BMC stores threshold changes in NVRAM. The fix survives:
- Host reboot
- Host power cycle
- BMC cold reset (e.g., via the BMC reset button or `ipmitool mc reset cold`)

It does NOT survive a BMC factory reset, which would also restore the default ADMIN password and other BMC settings.

## Restore (if ever needed)

```bash
sudo ipmitool sensor thresh FANB lcr 420
```

That returns FANB to the original fault-response behavior. The cycling will resume.

## Verification

After applying the fix:

```bash
sudo ipmitool sdr type fan
```

FANB should show `ok` regardless of whether the current reading is 420 or 1960. The cycling should be audibly gone.

## Aftermath observation — fans stuck high

Immediately after the threshold change (before any BMC reset), the other fans (FAN4 in particular) remained at their ramped-up RPMs rather than returning to baseline. Cause: the BMC's Optimal fan curve ramps UP on threshold trips but doesn't aggressively ramp DOWN once a trip resolves via threshold change (as opposed to actual fan recovery). The BMC needs to be kicked to re-evaluate from current temps.

Fix: cold BMC reset.

```bash
sudo ipmitool mc reset cold
```

The host stays online — `mc reset cold` only restarts the management controller, not the OS. BMC takes ~30-60 seconds to come back, then re-initializes fan curves from NVRAM and current temps. After cold reset on this build:

- FAN4 dropped 2660 → 980 RPM
- FAN5 dropped 3220 → 1120 RPM
- FANA / FANB now report as `Device Not Present` (cleaner state than pre-reset)

Confirming: FAN5 was at 3220 RPM the entire session before this fix, which wasn't its true idle baseline — that was the BMC's stuck ramped-up state baked in from the FANB cycling. Real idle for these fans is roughly 1000 RPM. The fan-zone behavior was running the rack 2-3× harder than needed for as long as the FANB sensor anomaly existed.
