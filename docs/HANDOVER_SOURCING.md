# Handover: Component Sourcing

## Status: IN PROGRESS
## Expires when: All components purchased and received

**Last Updated:** 2026-04-07

## GPU Sourcing (RESOLVED)

### Winner: kuaka02 (Ada)
- **Cards:** 3x Gigabyte GeForce RTX 3090 Turbo 24GB (blower/2-slot)
- **Price:** $3,180 ($1,060/ea) shipped FedEx air from China
- **Feedback:** 99.5% positive, 2,484 ratings
- **Process:** Will create custom eBay links at agreed price for payment
- **Contact:** Seller name "Ada", responsive, professional

### Other Sellers Contacted (All Resolved)
| Seller | Feedback | What Happened |
|--------|----------|---------------|
| MemoryPartner_Deals | 100% / 101K | Vague stall ("we will check it"), same entity as quark_12 |
| quark_12 | 99.5% / 3.4K | Identical message to MemoryPartner — confirmed same operator |
| e-dealsglobal | 98.5% / 66 | No response |
| motorpartners | 99.6% / 4K | Said no |
| sinobright | ~21.6K | Said no |
| bodorship | 100% / 2.8K | Said no |
| long2207 | - | Away until 4/17 |
| aymdam-0 | - | Original offer, Gigabyte Turbo ~$1,176 |

### Market Intel (April 2026)
- **Available blower variants:** Gigabyte Turbo, GALAX Turbo, MSI Turbo, ASUS Turbo, Leadtek WinFast
- **Does NOT exist:** PNY Blower, Dell Blower (Dell is dual-fan)
- **Listed prices:** $1,084-$1,199 (China), rare US listings at $980-$1,176
- **Sold prices (last 7 days):** $980-$1,199, median ~$1,100
- **Alibaba:** MORE expensive ($1,424-$2,100), not a viable channel
- **Market condition:** Frozen/stagnant. WinFast inventory not moving. Sellers holding firm. Buyers hesitant.
- **eBay tax (TX):** 8.25% on top of all purchases

## RAM Sourcing (RESOLVED)

### Winner: scwcomputers
- **Kit:** 128GB DDR4 (4x32GB) PC4-2133P ECC RDIMM Samsung HPE 752372-081
- **Price:** $420 (listed $499.99, offered $350 auto-declined, $400 auto-declined, $420 accepted)
- **Condition:** Used, tested and passed Memtest86
- **Feedback:** 100% positive, 1,304 ratings
- **Ships from:** Roseville, California
- **Order:** #03-14469-02999, Item ID 137189045593

### Market Intel
- DDR4-2133/2400 128GB kits: $420-550 (tested)
- DDR4-2933 128GB kits: $700-1,000+ (Gemini claimed $300 - false)
- DDR4 speed irrelevant for LLM inference (GPU VRAM is the bottleneck)
- Avoid A-Tech branded sticks (rebranded, non-standard SPD profiles)
- Samsung, SK Hynix, Micron OEM modules are gold standard

## Mobo + CPU (RESOLVED)
- **Combo:** EPYC 7302 + Supermicro H12SSL-i
- **Price:** $910
- **Seller:** tugm4470
- **Notes:** Saved $90 vs buying separately. Better CPU than the downgrade we considered.

## PSU (RESOLVED)
- **Unit:** Super Flower Leadex Titanium 1600W
- **Price:** $223
- **Seller:** respec.io (eBay), 1yr warranty
- **Notes:** vs $400 Amazon. Professional refurb seller.

## SSD (RESOLVED)
- **Unit:** Acer Predator GM7 2TB TLC
- **Price:** $269
- **Notes:** TLC mandatory (QLC fails under AI server read loads). GM7 variant, not GM7000.

## Chassis (RESOLVED)
- **Unit:** SilverStone RM400 (SST-RM400)
- **Price:** ~$240 (exact TBD)
- **Source:** Amazon
- **Notes:** Arriving Saturday 2026-04-12. Came bundled with Noctua NF-A12x25 PWM case fan.

## CPU Cooler (RESOLVED)
- **Unit:** Noctua NH-U9 TR4-SP3 (125mm, 23mm clearance in RM400)
- **Price:** $150 ($161.29 incl tax)
- **Seller:** kuaka02 (Ada) — same seller as GPUs
- **Notes:** Changed from Arctic Freezer 4U-M (145mm, 3mm clearance — too risky) to Noctua (125mm, 23mm clearance). Ada negotiated from $134.85+$79.99 ship to $150 flat.

## Server Rack (RESOLVED)
- **Unit:** SysRacks 24x24
- **Price:** $75
- **Notes:** Purchased.

## Cooler Decision History
- Arctic Freezer 4U-M was original spec: 145mm tall, only 3mm clearance in RM400 without card retainer bracket. No real-world confirmation of this combo found online.
- Noctua NH-U9 TR4-SP3 considered: 125mm tall, 23mm clearance. Best cooler but out of stock everywhere at MSRP (~$100). Cheapest was UK seller at ~$168.
- Supermicro SNK-P0064AP4 considered: 126mm tall, 22mm clearance, ~$84. Louder (38 dBA) but functional. Would be loudest component at idle (GPUs idle at 33-35 dBA).
- Final decision: Noctua from Ada at $150. Near-silent at idle matters because server lives in living room. GPUs at 50-55 dBA under load drown everything out, but at idle the CPU cooler noise profile matters.
