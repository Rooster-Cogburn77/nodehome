# Sovereign Node Wiki Index

## Concepts (7 articles)
| Article | Description |
|---------|-------------|
| [blower-gpu-form-factor](concepts/blower-gpu-form-factor.md) | Why 2-slot blower GPUs are mandatory for dense rack builds |
| [quantization-basics](concepts/quantization-basics.md) | Q4/Q6/Q8 quantization for running large models on consumer GPUs |
| [cognitive-core](concepts/cognitive-core.md) | Karpathy's vision for always-on local LLM computing |
| [shenzhen-electronics-hub](concepts/shenzhen-electronics-hub.md) | Why Shenzhen/Huaqiangbei is the global electronics recycling capital |
| [itad-supply-chain](concepts/itad-supply-chain.md) | How datacenter hardware flows from hyperscalers to resale market |
| [gemma4-moe](concepts/gemma4-moe.md) | Gemma 4 26B MoE - 3.8B active params, fits single 3090 |
| [claw-code](concepts/claw-code.md) | Open-source Claude Code agent harness (github.com/instructkr/claw-code) |
| [solar-offgrid-power](concepts/solar-offgrid-power.md) | Solar/Jackery = ~1.6 hours at full load, supplemental only |

## Decisions (5 articles)
| Decision | Date | Summary |
|----------|------|---------|
| [epyc-over-threadripper](decisions/epyc-over-threadripper.md) | 2026-04 | Why EPYC 7302 over Threadripper (128 PCIe lanes, ECC) |
| [blower-mandate](decisions/blower-mandate.md) | 2026-04 | Why blower GPUs, not open-air (slot physics in 4U) |
| [ram-speed-irrelevant](decisions/ram-speed-irrelevant.md) | 2026-04 | Why DDR4-2133 is fine (GPU VRAM is the bottleneck) |
| [tlc-over-qlc](decisions/tlc-over-qlc.md) | 2026-04 | Why TLC SSD mandatory (QLC fails under AI read loads) |
| [noctua-over-arctic](decisions/noctua-over-arctic.md) | 2026-04 | Why Noctua TR4-SP3 over Arctic 4U-M (clearance + idle noise in living room) |

## Research (8 articles)
| Topic | Status | Summary |
|-------|--------|---------|
| [ai-agent-traps](research/ai-agent-traps.md) | Complete | DeepMind's 6 trap categories mapped to Sovereign Node threat model |
| [hyperscaler-capex](research/hyperscaler-capex.md) | Logged for deep dive | $600B+/yr 2026, $1.3T over 3 years |
| [karpathy-dossier](research/karpathy-dossier.md) | Complete | Full research on repos, cognitive core, knowledge base workflow |
| [gpu-resale-side-hustle](research/gpu-resale-side-hustle.md) | Explored, not committed | Blower arbitrage from ITAD vendors |
| [gpu-architecture-comparison](research/gpu-architecture-comparison.md) | Complete | RTX 3090/4090/5090 vs A100/H100 |
| [ebay-seller-behavior](research/ebay-seller-behavior.md) | Complete | China bulk seller dynamics, 12.5% response rate |
| [3090-blower-market-april2026](research/3090-blower-market-april2026.md) | Complete | Full market sweep, pricing, scam warnings |
| [locker-vs-build-our-own-ingest-layer](research/locker-vs-build-our-own-ingest-layer.md) | Considered, not committed | File-store + ingest architecture option; likely useful pattern even if we do not adopt Locker |

## Incidents (1 article)
| Incident | Severity | Summary |
|----------|----------|---------|
| [gemini-hallucination-patterns](incidents/gemini-hallucination-patterns.md) | Medium | 5 documented fabrications: fake products, fake prices, fake narratives |
