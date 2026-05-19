# H12SSL-i Front Panel Header (JF1)

**Status:** CAPTURED - JF1 wiring follow-on closed.
**Source:** Supermicro H12SSL-i/C/CT/NT User's Manual `MNL-2314`, section 2.6 "Front Control Panel", Figure 2-2: <https://www.supermicro.com/manuals/motherboard/EPYC7000/MNL-2314.pdf>

This runbook records the front-panel header used during the permanent in-chassis install. The board also has an onboard power button, but the RM400 front-panel wiring is kept connected for the permanent build.

## Orientation

JF1 is a 20-pin, two-column front control panel header.

When using the manual's Figure 2-2 orientation:

- Left column is even pins, bottom to top: `2, 4, 6, ... 20`.
- Right column is odd pins, bottom to top: `1, 3, 5, ... 19`.
- Bottom pair is `2` / `1`.
- Top pair is `20` / `19`.

## Pin Map

| Pins | Function |
|---:|---|
| `1` / `2` | Power button: `PWR` / `Ground` |
| `3` / `4` | Reset button: `Reset` / `Ground` |
| `5` / `6` | Power Fail LED: `3.3V` / `Power Fail LED` |
| `7` / `8` | UID LED: `3.3V Stby` / `UID LED` |
| `9` / `10` | NIC2 Link LED: `3.3V Stby` / `NIC2 Link LED` |
| `11` / `12` | NIC1 Link LED: `3.3V Stby` / `NIC1 Link LED` |
| `13` / `14` | HDD LED: `3.3V Stby` / `HDD LED` |
| `15` / `16` | Power LED: `3.3V` / `PWR LED` |
| `17` / `18` | No connection / no connection (`X` / `X`) |
| `19` / `20` | No connection / NMI (`X` / `NMI`) |

## Build Notes

- Front-panel power switch uses pins `1` and `2`; switch polarity does not matter.
- Front-panel reset switch, if used, uses pins `3` and `4`; switch polarity does not matter.
- LED polarity matters. Treat the `3.3V` / `3.3V Stby` side as the positive side unless the chassis lead documentation says otherwise.
- Do not guess or short other pins. Use this map, the board silkscreen, or the official Supermicro manual.

## Current Nodehome State

- Chassis front-panel leads were wired during the 2026-05-10 permanent in-chassis install.
- Operator clarified on 2026-05-19 that the prior JF1 pinout-capture follow-on is complete.
- The remaining stale docs that still listed JF1 capture as open were corrected in the same follow-up pass.
