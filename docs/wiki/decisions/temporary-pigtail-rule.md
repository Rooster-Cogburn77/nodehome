# Decision: Temporary Pigtail / Y-Splitter Use on the Third 3090

**Date:** 2026-05-09
**Type:** authored
**Status:** Active until the proper dedicated PCIe modular cable for the SF-1600F14HT arrives and is installed on GPU #3.

## Context
GPU #1 and GPU #2 are powered with the validated configuration: two separate dual-head PCIe modular cables per GPU, each cable connected to a separate PSU socket, only one head of each cable in use at the GPU. That configuration validated cleanly under sustained `~348 W / 89% util` load on GPU 0.

GPU #3 is on hand but the build is short by one dual-head cable. The proper cable for the `Super Flower SF-1600F14HT` (Leadex 80+ Titanium 1600W) is being sourced (eBay `lizzieb753` UK, ~5-8 days) but is not yet in hand.

The question this decision addresses: can a single existing dual-head cable be used as a temporary pigtail (both heads from one cable feeding both 8-pin connectors of GPU #3, drawing from a single PSU socket) until the proper cable arrives?

## Decision
Yes, **temporarily and only under explicit constraints.** A pigtail / Y-split configuration on GPU #3 is acceptable for short, supervised validation work, and is not acceptable for any normal workload posture.

### Allowed under temporary pigtail
- Boot / POST through BIOS
- `lspci` enumeration
- NVIDIA driver install
- `nvidia-smi` queries
- Brief, supervised low-load smoke tests
- Touch-check on the cable and connectors after a few minutes of any of the above; if anything is hot, power down immediately

### Not allowed under temporary pigtail
- Long inference runs
- Unattended operation
- Stress tests
- Benchmarking
- Any sustained multi-GPU load

## Why this rule exists

Two separate PCIe cables from two PSU sockets → power delivery is split across separate connector pin sets and separate cable runs, so each cable carries roughly half the GPU's draw and connector heat is bounded.

A pigtail forces the GPU's full draw through **one PSU socket and one cable's pin-set**. For a 3090 under sustained TDP (`~350 W`), that means a single connector pair has to carry close to its rated current limit for hours. Real-world failure mode is connector heat → melted plastic → bad contact → voltage droop → instability or fire.

For brief validation activity (idle / light queries / driver work) the draw is far below the connector rating and heat does not accumulate. The risk profile is genuinely different between "10 minutes of `nvidia-smi`" and "8 hours of 3-GPU inference."

A glib single-number "single-cable safety limit" is not what governs this — the real limits depend on PSU brand, cable construction, individual connector quality, ambient temperature, and how long the load is sustained. None of those are well-characterized for this specific PSU + cable + 3090 combination, so the rule is framed by *use category*, not by a watt threshold.

## Operational guidance

When bringing GPU #3 up under the temporary rule:

1. Full power-down. PSU unplugged from wall. Discharge with the front-panel power button.
2. One dual-head cable into a free PSU socket. Both heads into GPU #3's two 8-pin headers, fully seated.
3. Boot. Verify BIOS sees the card. Boot into Ubuntu.
4. SSH in. `lspci | grep -i nvidia`, `sudo lspci -vv -s <bus>:00.0 | grep -E "LnkCap:|LnkSta:"`.
5. If the card is enumerating, `nvidia-smi` should already show it (driver is already installed from GPU #1 + #2 work).
6. **After a few minutes of light use, touch-check the cable and connectors.** If warm, fine. If hot, power down immediately and stop.
7. Keep GPU #3 out of any heavy or unattended workload rotation. Run sustained 70B / multi-GPU inference on GPUs 0 and 1 only until the proper cable arrives.

## Exit criteria
This rule is retired the moment the proper dedicated PCIe cable for the SF-1600F14HT is installed on GPU #3. At that point GPU #3 returns to the same configuration as GPUs #1 and #2 (two separate cables, two separate PSU sockets, one head of each in use), and the full sustained multi-GPU workload posture is unlocked.

## Sources / framing references
- Constraint framing was authored by the user after pushback on an earlier overconfident "375 W single-cable safety limit" framing. Real limits are not well-characterized for this exact stack and the rule is therefore use-category-bounded, not threshold-bounded.
- Background context on individual vs pigtail connectors: `https://www.corsair.com/us/en/explorer/diy-builder/power-supply-units/individual-8-pin-vs-pigtail-connectors-for-gpus/`
- NVIDIA RTX 3090 product page (TDP / connector spec reference): `https://www.nvidia.com/en-us/geforce/graphics-cards/30-series/rtx-3090/`
- Super Flower SF-1600F14HT cable inventory: `https://www.cybenetics.com/ISO17025/psus/2220/`
