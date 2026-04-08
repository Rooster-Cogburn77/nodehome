# The Cognitive Core (Karpathy)

## Concept
Andrej Karpathy's vision for LLM personal computing: a few-billion-parameter model that lives always-on by default on every computer as the "kernel" of a new computing paradigm.

## Key Properties
1. **Natively multimodal** - text/vision/audio at both input and output
2. **Matryoshka architecture** - dial capability up and down at test time
3. **Reasoning dial** - system 2 thinking, adjustable
4. **Aggressive tool use** - with on-device finetuning LoRA slots for personalization
5. **Always-on** - running as a background service, like an OS kernel

## Tradeoffs vs Cloud
| | Local Cognitive Core | Cloud API |
|--|---------------------|-----------|
| Latency | Super low | Network-dependent |
| Data access | Direct, private | Must upload |
| Offline | Yes | No |
| Sovereignty | Full | None |
| World knowledge | Limited | Broad |
| Problem-solving ceiling | Lower | Higher (for now) |

## Sovereign Node Implementation
- **Gemma 4 26B MoE** (3.8B active params) as the cognitive core model
- Runs on a single 3090 (24GB VRAM)
- Remaining 2x 3090s available for larger models or parallel agents
- This is literally the architecture Karpathy is describing

## Source
- https://x.com/karpathy/status/1938626382248149433
