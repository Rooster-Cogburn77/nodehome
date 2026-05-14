# Rack Acoustic Treatment

**Date:** 2026-05-13
**Status:** Accepted

## Context

The rack lives close enough to normal living space that idle and low-load noise matter. After the BMC `FANB` threshold fix, the loudest remaining nuisance is intermittent fan ramping / fan hunting, not a constant panel rattle.

The question: should the rack interior be lined with adhesive acoustic foam or similar damping material to reduce fan ramp noise?

## Decision

Do **not** line the rack interior with adhesive acoustic foam as a default noise-reduction strategy.

Use acoustic treatment only where it matches the physical problem:

- Use rubber / neoprene isolation under external HDDs on the 1U shelf.
- Use Dynamat-style butyl damping only on metal panels or shelves that audibly ring or buzz.
- Use blanking panels if open rack gaps cause airflow turbulence.
- Treat fan ramping at the source with measured fan, temperature, and load data.

## Rationale

Adhesive acoustic foam is a weak fit inside this rack:

- Amazon-style "flame resistant" acoustic panels are not the same as rack-rated fire-safe material.
- Adhesive can soften or fail under sustained warm airflow.
- Foam collects dust near fans and electronics.
- Bad placement can block front-to-back airflow.
- Thin `0.4"` panels mostly reduce high-frequency reflections; they do not solve blower fan ramping.

Dynamat-style material is safer than soft foam for internal rack use, but only for vibration damping. It adds mass to sheet metal and reduces panel resonance. It does not absorb airborne GPU blower noise or fix fan-control behavior.

## Allowed

- Rubber feet / neoprene mat under external HDD enclosures.
- Velcro or straps to stop drives, cables, shelves, or panels from rattling.
- Small Dynamat / butyl strips on solid non-vented rack panels that ring.
- Dynamat / butyl on the underside of the external-drive shelf if the shelf resonates.
- Blanking panels to improve airflow if open U gaps create turbulence.

## Not Allowed

- Adhesive foam inside the RM400.
- Foam near GPU exhaust, PSU exhaust, rear exhaust paths, or intake paths.
- Foam over perforated / vented panels.
- Material that can peel and fall into fans or cables.
- Blind fan-speed reductions without temperature validation.

## Operational Path

When fan ramping returns or becomes annoying:

1. Identify which fans are changing speed.
2. Correlate fan speed with temperatures, load state, and service state.
3. Fix the control or thermal cause first.
4. Use damping only for confirmed vibration / resonance problems.

Useful commands:

```bash
watch -n 1 nvidia-smi
sudo ipmitool sdr type fan
sudo ipmitool sdr type temperature
sensors
```

The default answer for "should I stick foam inside the rack?" is no.
