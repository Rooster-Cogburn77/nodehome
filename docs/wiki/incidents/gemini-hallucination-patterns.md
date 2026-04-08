# Incident: Gemini Hallucination Patterns

**Last Updated:** 2026-04-04
**Severity:** Medium (caused wasted time, not wasted money - we caught them)

## Pattern: Fabricated Specificity
Gemini consistently invents specific details (seller names, prices, product listings) that sound authoritative but don't exist. The hallucinations are dangerous because they mix real data with fabricated data, making it hard to separate truth from fiction without verification.

## Documented Instances

### 1. PNY Blower RTX 3090 (Fabricated Product)
- **Claim:** "The Texas Unicorn: PNY Blower RTX 3090 ($1,195)" from an Austin-area seller
- **Reality:** PNY does not manufacture a blower RTX 3090. All PNY 3090s are XLR8 open-air coolers. Zero results on eBay. The product literally does not exist.
- **Danger level:** High - could have sent user searching for something that can't be found

### 2. Intel B70 Panic Selling (Fabricated Narrative)
- **Claim:** Intel Arc Pro B70 release was causing 3090 owners to "panic sell," creating $1,050 deals
- **Reality:** Nobody selling a $1,000+ CUDA GPU is panicking over an Intel Arc card. The narrative was invented to explain real-ish price points.
- **Danger level:** Low - narrative was wrong but prices cited were roughly in range

### 3. RAM Pricing at $300-330 (Fabricated Prices)
- **Claim:** 128GB DDR4-2933 ECC RDIMM kits available for $300-330 from specific sellers
- **Reality:** Actual market is $700-1,000+ for 2933 kits. Gemini's prices were off by 3x.
- **Specific sellers cited:** cloud_storage_corp and serverpartdeals DO exist as real eBay sellers, but neither has listings at those prices. serverpartdeals last sold a similar kit for $760.
- **Danger level:** High - could have set incorrect budget expectations

### 4. "3200MHz RAM Cornered by Scalpers" (Fabricated Market Dynamics)
- **Claim:** The 3200MHz RAM market is "completely cornered by scalpers"
- **Reality:** 3200 ECC is more expensive, but "cornered by scalpers" is dramatic invention
- **Danger level:** Low - directionally correct (3200 costs more) but framing is fabricated

### 5. "Dedicated Sales Person for Bulk AI Requests" (Fabricated Seller Detail)
- **Claim:** motorpartners "often handles Bulk AI requests and might have a dedicated sales person"
- **Reality:** motorpartners didn't even respond to our message. No evidence of dedicated sales operations.
- **Danger level:** Low - but represents the pattern of inventing plausible-sounding details

## Detection Strategy
1. **Verify specific sellers exist** before acting on recommendations
2. **Check specific prices against actual eBay listings** - Gemini's prices are often 30-70% below reality
3. **Be skeptical of dramatic narratives** ("panic selling," "cornered by scalpers") - these are invented to sound insightful
4. **Products that sound too good to be true** (PNY blower 3090) usually don't exist
5. **Cross-reference with our own market sweeps** - we have real data, don't let Gemini override it

## Root Cause
Gemini is generating plausible-sounding market intelligence without access to real-time eBay data. It knows what GPU models exist (sometimes wrong), what price ranges are typical (often wrong), and what seller behavior looks like (usually fabricated). The confidence in its output doesn't correlate with accuracy.

## Prevention Rule
**Added to CLAUDE.md Hard Rules:** "Verify AI-generated claims before presenting as fact."
**Added to ATTITUDE.md:** "If another AI provides analysis, verify before endorsing."
