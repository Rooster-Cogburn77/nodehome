# Session Scratch - 2026-05-09 (Session 13)
Focus: All-3-GPU hardware bring-up under the temporary pigtail rule on GPU #3, 70B Q4 layer-split inference validated, cable ordered.

## Observed (validated this session)
- 70B Q4 layer-split inference works on the 2-GPU configuration. `ollama ps` reported `100% GPU`. Mid-flight `nvidia-smi` showed both GPUs at `P2`, `~110 W` each, same Ollama PID on both. Output was coherent. Generation rate was within the expected `8-15 tok/s` ceiling for this topology — slow but correct.
- Power-yank from a pet pulling the cord mid-generation. Post-recovery: `Critical Warning 0x00`, `Available Spare 100%`, `Percentage Used 0%`, `Unsafe Shutdowns 3`, ext4 journal replay clean (`orphan cleanup on readonly fs` → `re-mounted r/w`). One nvidia 7.0 kernel `__warn_thunk` warning observed at module load — filed as known noise, not a blocker.
- All three RTX 3090s now installed and link-validated:
  - GPU 0: `81:00.0`, CPU SLOT1, `gen.max = 4`, `width.max = 16`. Validated under sustained TDP load earlier.
  - GPU 1: `C1:00.0`, CPU SLOT3, `gen.max = 4`, `width.max = 16`. Validated under multi-GPU layer-split.
  - GPU 2: `C2:00.0`, next available CPU x16 slot, `gen.max = 4`, `width.max = 16`. Brought up under the temporary pigtail rule. Touch-check at idle was clean (ambient).
- Bus IDs `C1:` and `C2:` are adjacent → GPU #2 and GPU #3 share a PCIe root complex / IOD. Informational for later NUMA-aware tensor-parallel work.

## Decisions made this session
- Adopted the formal **temporary pigtail rule** for GPU #3 (`docs/wiki/decisions/temporary-pigtail-rule.md`). Permitted: BIOS, `lspci`, driver install, `nvidia-smi`, brief supervised low-load smoke tests. Not permitted: long inference, unattended operation, stress tests, benchmarks, or any sustained multi-GPU load. Retires when the proper dedicated cable is installed.
- Replaced the earlier glib "375 W single-cable safety limit" framing with use-category-bounded guidance, since real-world safety depends on PSU brand, cable construction, connector quality, ambient temperature, and load duration — none of which are well-characterized for this exact stack. Captured as feedback memory.
- Ordered the proper cable from eBay seller `lizzieb753` UK at landed cost `$49.85`, order `05-14624-65956`. Corrected an earlier `$33.98` quote (item + shipping only) that omitted UK→US import charges and checkout tax. Also corrected an earlier `5-8 days` shipping-time quote — realistic UK→US window is 2-4 weeks, ending around `2026-05-23 to 2026-06-10`. Both quoting errors captured as feedback memory.

## Late-session validation
- Re-ran the full 1500-word essay generation on `llama3.3:70b-instruct-q4_K_M` across the 2-GPU layer-split configuration. Output completed with a coherent, well-structured 1500-word essay on distributed computing — research-grade quality, expected slow rate (~8-15 tok/s ceiling for this topology).
- **Interactive tier benchmarked.** `qwen2.5:32b-instruct-q4_K_M` on a single 3090: `eval rate 39.31 tok/s`, `prompt eval rate 696.63 tok/s`, `load duration 8.02 s`. ~3-4× faster than 70B layer-split. Day-one tiering empirically confirmed: 8B fast / 32B interactive / 70B deep-reasoning.

## Not Proved (still ahead of the build)
- Sustained 3-GPU heavy inference. Gated on the proper cable arriving and the pigtail being retired. Realistic window for the cable: **2026-05-23 to 2026-06-10**, per the eBay seller's posted estimate. The earlier `5-8 days` figure was a cross-border-shipping quoting mistake on my part; UK Royal Mail / eBay International to US is 2-4 weeks realistically.
- vLLM install + `TENSOR_PARALLEL_SIZE=2` on the existing 2-GPU configuration, with later upgrade to `TENSOR_PARALLEL_SIZE=3` once GPU #3 is unrestricted.
- 70B Q6 across all 3 GPUs — the original day-one model target.
- Sustained thermal validation under multi-hour load (single-shot 348 W draw was clean on GPU #1; soak test still pending).
- ReBAR enable + A/B benchmark vs current `[Disabled]` baseline.
- Final physical deployment: RM400 chassis is desk-mounted, not rail-mounted in the SysRacks 24x24. Cable routing is functional but not tidied. Dedicated IPMI ethernet not patched into rack-side networking. Permanent living-room location move not done. Deferred until the proper cable is installed.

## Hardware-side rule reminders in effect right now
- **Pigtail on GPU #3:** idle / `nvidia-smi` / brief light queries only. No sustained 3-GPU workload.
- **Power cord:** household pet pulled it once today during inference. Real recurring risk until the box moves to the rack with proper cable management. A cord lock or locking IEC adapter is a $5 cope until then.

## Next physical step
- Wait for the cable. Realistic window: 2026-05-23 to 2026-06-10. Order number `05-14624-65956` from `lizzieb753` UK at landed `$49.85`.
- Continuing to look for a faster source in parallel (CableMod Rush+Express in 5-10 days at ~$70 from US warehouse, or r/hardwareswap local pickup if anyone happens to have one). The eBay UK order is the floor; if a faster legitimate source materializes, the eBay order can be cancelled.
- When the cable arrives: power down → swap pigtail for the proper dedicated cable → boot → validate → run sustained 3-GPU workload → retire the temporary pigtail rule.

## Next software step (in flight or imminent)
- Stage vLLM install on the 2-GPU configuration so `TENSOR_PARALLEL_SIZE=2` testing can begin. vLLM TP is generally faster than Ollama's pipeline parallel on PCIe-only setups. Real numbers to compare against tonight's 70B Q4 baseline.
- For interactive work in the meantime: prefer 30B-class models (Qwen 30B, Mistral 24B, Gemma 4 27B) on a single GPU. Expected `25-40 tok/s`.
