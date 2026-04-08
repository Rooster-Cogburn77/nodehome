# ITAD Supply Chain (IT Asset Disposition)

**Last Updated:** 2026-04-04

## What Is ITAD
IT Asset Disposition is the industry that handles decommissioned enterprise hardware. When a hyperscaler like Microsoft, Amazon, or Google retires a generation of servers (typically every 3-5 years), the hardware doesn't go to a landfill. It flows through ITAD vendors who:
1. Securely wipe data (certified destruction)
2. Sort and grade hardware by condition
3. Test components individually
4. Resell what works, recycle what doesn't

## The Flow
```
Hyperscaler / Enterprise
    ↓ 3-5 year depreciation cycle
ITAD Vendor (contracted for secure disposal)
    ↓ Data wipe, sort, test
Wholesale Broker
    ↓ Bulk lots (by pallet, by weight, by SKU)
Reseller / Refurbisher
    ↓ Individual listing, testing, warranty
End Buyer (eBay, direct, Alibaba)
```

## Key ITAD Vendors (US)
- **GreenTek Solutions** (Austin TX) - General refurb electronics. Checked their eBay store: zero GPUs.
- **DMD Systems Recovery** (Austin TX) - Needs investigation
- **Liquis** (Austin TX area) - Needs investigation
- **Liquid Technology** - Needs investigation
- Many more exist nationally but most sell bulk to brokers, not individual components

## Pricing Dynamics
- **ITAD acquisition cost for RTX 3090:** Estimated $500-650/card in bulk
- **ITAD vendors don't price the blower premium** - They sell by GPU model, not by cooler type
- **This creates the arbitrage opportunity** - Buy blower 3090s at generic 3090 prices from ITAD, resell on eBay at the 10-25% blower premium to AI builders who need the 2-slot form factor

## The Coming Wave
With $1.3T in hyperscaler CapEx over 2024-2026, there will be a massive decommission wave in 2027-2030 when this hardware reaches end of depreciation. A100s and H100s will flood the ITAD market. This is the future upgrade path for the Sovereign Node (swap 3090s for used A100s).

## Relevance
- Current build: All purchased components except RAM came through some version of this pipeline
- Side hustle: ITAD is the buy-side of the GPU resale opportunity
- Future upgrades: A100/H100 prices will drop when the decommission wave hits
