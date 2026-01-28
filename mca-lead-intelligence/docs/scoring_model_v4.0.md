# MCA PREDICTIVE LEAD INTELLIGENCE FRAMEWORK
## Version 4.0 - Time-Weighted Scoring Engine Edition

A Prospecting Framework for Identifying High-Quality MCA Leads
Calibrated Using 7,634 Historical MCA Transactions
Enhanced with Exponential Decay Time-Weighting

**CONFIDENTIAL - INTERNAL USE ONLY**

Last Updated: January 2026

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2026 | Initial framework |
| 2.0 | Jan 2026 | Three-dimensional model (Fit, Intent, Timing). Revenue-based FIT scoring. |
| 3.0 | Jan 2026 | DATA-CALIBRATED: All scoring tables updated using 7,634 historical deals. Industry propensity, TIB, state, deal size calibrated from actual performance data. |
| 4.0 | Jan 2026 | TIME-WEIGHTED ENGINE: Exponential decay functions, signal-specific half-lives, freshness flags, multiplicative scoring architecture. |

---

## 1. Executive Summary

### 1.1 Framework Purpose

This framework identifies and prioritizes PROSPECTIVE MCA leads—businesses that may need capital and can support MCA repayment. Version 4.0 incorporates data-driven calibrations from 7,634 historical MCA transactions across six funder datasets AND introduces a time-weighted scoring engine that recognizes timing as a multiplier affecting the value of every signal.

The framework helps sales brokers answer:
- Which businesses should I call?
- When should I call them?
- What should I say?
- How big a deal might this be?
- How fresh and actionable is this lead right now?

### 1.2 Data Sources Used for Calibration

| Dataset | Records | Key Fields |
|---------|---------|------------|
| Novac | 694 | Deal amount, factor, performance |
| TVT | 1,020 | Industry, NAICS, TIB, FICO, state |
| eFinancial Tree | 2,071 | Business type, state, position |
| Legend Funding | 3,591 | Industry, state, deal size |
| CapitaWize 2022-2023 | 123 | Industry, TIB, position |
| CapitaWize 2024 | 135 | Industry, TIB, position |
| **TOTAL** | **7,634** | |

### 1.3 Key Calibration Findings

- **Industry Concentration**: 43% of deals from top 5 industries (Restaurant, Trucking, Construction, Auto, Retail)
- **Geographic Hotspots**: FL + TX = 26% of all deals; Top 4 states = 37%
- **TIB Sweet Spot**: Median 7 years; 70%+ deals go to businesses 3+ years old
- **FICO Distribution**: Mean 620 (subprime); deals span all credit tiers
- **Stacking Prevalence**: 49% of deals are 2nd position or higher
- **Deal Size**: Median $48K; 72% of deals under $75K

### 1.4 What's New in Version 4.0

| Enhancement | Description |
|-------------|-------------|
| Exponential Decay Engine | Signal values decay mathematically based on age, using signal-specific half-lives |
| Signal Half-Life Classification | Rapid (7-10 days), Standard (21-30 days), Extended (45-60 days), Structural (90+ days) |
| Lead Freshness Multiplier | Global multiplier (0.1x to 1.3x) applied to final score based on lead age |
| Freshness Flags | Visual indicators: 🔥 HOT, ⚡ WARM, ● STANDARD, ❄ COOLING, ◌ COLD, ○ STALE, ✕ DEAD, ∅ EXPIRED |
| Multiplicative Architecture | Timing affects Intent multiplicatively, not just additively |
| UCC Optimal Window Curve | Refined refinance propensity scoring with peak at 4-6 months |

### 1.5 The Core Insight

> "A hiring signal from yesterday is fundamentally different from the same signal 60 days ago—it's not just 'less timely,' it's potentially worthless because the position may already be filled."

Version 3.0 treated timing as an additive component. Version 4.0 recognizes that time should act as a multiplier that modulates other dimensions—particularly Intent signals.

### 1.6 Industry Benchmark

In the MCA industry, the best leads are those with bank statements submitted within 48 hours. Leads aged 30+ days are considered 'aged' and those 90-180 days old typically have conversion rates 70-90% lower than fresh leads. This framework quantifies and operationalizes this reality.

---

## 2. The Three Dimensions

### 2.1 Overview

Score prospective leads on three independent dimensions:

- **FIT** — Can an MCA work for this business? (Revenue capacity & quality)
- **INTENT** — Are there signals they might need capital?
- **TIMING** — Is NOW the right time to reach out?

### 2.2 Dimension Weights

Version 4.0 adjusts weights to account for time-weighting now being embedded in Intent:

| Dimension | v3.0 Weight | v4.0 Weight | Rationale |
|-----------|-------------|-------------|-----------|
| FIT | 35% | 40% | Revenue capacity determines MCA viability |
| INTENT | 35% | 40% | Intent signals predict response rates (now time-weighted) |
| TIMING | 30% | 20% | Reduced—timing now embedded in Intent decay + Freshness Multiplier |

### 2.3 Composite Score Formula

**Previous Formula (v3.0):**
```
PROSPECT SCORE = (FIT × 0.35) + (INTENT × 0.35) + (TIMING × 0.30)
```

**New Formula (v4.0):**
```
Time-Weighted INTENT = Σ(Signal_Base_Value × Decay_Factor(signal_age, signal_type))
Composite Score = (FIT × 0.40) + (Time-Weighted INTENT × 0.40) + (TIMING × 0.20)
FINAL SCORE = Composite Score × Lead_Freshness_Multiplier
```

---

## 3. Time-Weighted Scoring Architecture (NEW)

### 3.1 The Three Layers of Time-Weighting

**Layer 1: Signal-Specific Decay**
Each intent signal decays at a rate determined by its half-life. Job postings decay rapidly (positions fill quickly), while UCC filings decay slowly (financing decisions take months).

**Layer 2: Composite Time-Weighting**
Time-weighted signals are aggregated into a Time-Weighted Intent Score, replacing the static Intent score from v3.0.

**Layer 3: Lead Freshness Multiplier**
A global multiplier (0.1x to 1.3x) is applied to the final composite score based on the age of the most recent actionable signal.

### 3.2 Exponential Decay Function

Signal values decay according to the exponential decay formula:

```
Signal_Value(t) = Base_Value × e^(-λt)
```

Where:
- `t` = signal age in days
- `λ (lambda)` = ln(2) / half_life
- `half_life` = signal-specific decay rate in days

This formula ensures values drop fastest immediately after detection and slow over time—matching real-world signal degradation patterns.

### 3.3 Signal Decay Classification

| Decay Class | Half-Life | Signal Types | Rationale |
|-------------|-----------|--------------|-----------|
| RAPID | 7-10 days | Job postings, social announcements, emergency promos, review spikes | Position fills, moment passes quickly |
| STANDARD | 21-30 days | Permit filings, hiring patterns, contract wins, equipment signals | Event momentum fades over weeks |
| EXTENDED | 45-60 days | UCC filings, new locations, tax liens, major equipment purchases | Financing decisions take time |
| STRUCTURAL | 90+ days | TIB changes, industry classification, ownership changes | Persistent business characteristics |

### 3.4 Rapid Decay Signals (Half-Life: 7-10 Days)

These signals lose value quickly because the underlying opportunity window closes fast.

| Signal | Base Pts | 0-2 days | 3-7 days | 8-14 days | 15-30 days | 30+ days |
|--------|----------|----------|----------|-----------|------------|----------|
| Active job posting (5+ roles) | 20 | 100% | 85% | 50% | 20% | 5% |
| Active job posting (2-4 roles) | 12 | 100% | 85% | 50% | 20% | 5% |
| Active job posting (1 role) | 5 | 100% | 80% | 45% | 15% | 0% |
| Social media announcement | 10 | 100% | 75% | 40% | 15% | 0% |
| Emergency promotions | 8 | 100% | 70% | 35% | 10% | 0% |
| Review spike (+15 in 2 weeks) | 10 | 100% | 90% | 65% | 40% | 15% |

### 3.5 Standard Decay Signals (Half-Life: 21-30 Days)

These signals maintain relevance for weeks but lose urgency over time.

| Signal | Base Pts | 0-7 days | 8-14 days | 15-30 days | 31-60 days |
|--------|----------|----------|-----------|------------|------------|
| Building permit filed | 12 | 100% | 95% | 80% | 50% |
| Contract win announced | 15 | 100% | 90% | 75% | 45% |
| New location announced | 20 | 100% | 95% | 85% | 60% |
| Franchise expansion | 18 | 100% | 95% | 85% | 65% |
| Equipment purchase signals | 12 | 100% | 90% | 70% | 45% |
| Seasonal pre-peak | 15 | 100% | 100% | 90% | 70% |

### 3.6 Extended Decay Signals (Half-Life: 45-60 Days)

These signals remain relevant for months as financing decisions unfold slowly.

| Signal | Base Pts | 0-14 days | 15-30 days | 31-60 days | 61-90 days |
|--------|----------|-----------|------------|------------|------------|
| New UCC filing* | 25 | 80% | 90% | 100% | 100% |
| UCC termination | 20 | 100% | 95% | 85% | 65% |
| Tax lien filed | 12 | 100% | 95% | 85% | 70% |
| Judgment filed | 10 | 100% | 90% | 75% | 55% |
| Major equipment purchase | 12 | 100% | 90% | 75% | 50% |

*Note: UCC filings have an optimal window—too fresh means they just got capital. See Section 3.8 for the UCC Refinance Window Curve.

### 3.7 Structural Signals (Half-Life: 90+ Days)

These signals represent persistent business characteristics that change slowly.

| Signal | Decay Rate | Notes |
|--------|------------|-------|
| Time in Business milestone | Minimal decay | TIB crossing thresholds (1yr, 3yr, 5yr) remains relevant indefinitely |
| Industry classification change | Minimal decay | Business pivots are significant long-term |
| Ownership change | Slow decay | New owners often seek capital within 6-12 months |
| Location count change | Slow decay | Multi-location status is persistently relevant |

### 3.8 UCC Refinance Window Curve

UCC filings follow an optimal window curve rather than simple decay. The refinance propensity peaks at 4-6 months when merchants feel payment burden but still have runway.

**Data insight from v3.0**: 49% of deals are 2nd position or higher—refinance is a major opportunity pathway.

| UCC Age | Propensity Score | Rationale |
|---------|------------------|-----------|
| 0-2 months | 20% | Too early—still deploying capital, not feeling payment burden yet |
| 2-3 months | 50% | Starting to feel daily payments, may be exploring options |
| 3-4 months | 75% | Optimal early window—established payment history, capital deployed |
| 4-5 months | 100% | PEAK WINDOW—ideal for refinance conversation |
| 5-6 months | 100% | PEAK WINDOW—ideal for refinance conversation |
| 6-7 months | 85% | Still good—may be approaching payoff or already exploring |
| 7-8 months | 65% | May have already refinanced with another funder |
| 8-9 months | 45% | Late window—likely paid off or renewed elsewhere |
| 9-10 months | 30% | Very late—advance likely near completion |
| 10+ months | 15% | Stale signal—likely resolved one way or another |

---

## 4. Lead Freshness System (NEW)

### 4.1 Freshness Flags

Every lead receives a Freshness Flag based on the age of its most recent actionable signal. These flags provide instant visual prioritization for brokers.

| Flag | Lead Age | Multiplier | Broker Action |
|------|----------|------------|---------------|
| 🔥 HOT | 0-48 hours | 1.30x | DROP EVERYTHING. Contact immediately. Highest conversion window. |
| ⚡ WARM | 2-7 days | 1.15x | High priority. Contact within 24 hours. Strong conversion potential. |
| ● STANDARD | 7-14 days | 1.00x | Normal priority. Work through queue. Good conversion potential. |
| ❄ COOLING | 14-30 days | 0.85x | Lower priority. May need re-engagement strategy. Declining odds. |
| ◌ COLD | 30-60 days | 0.65x | Low priority. Situation may have changed. Verify before calling. |
| ○ STALE | 60-90 days | 0.45x | Nurture only. Signal likely resolved. Move to drip campaign. |
| ✕ DEAD | 90-180 days | 0.25x | Archive. Opportunity window closed. Quarterly re-scan only. |
| ∅ EXPIRED | 180+ days | 0.10x | Remove from active pipeline. Data retention only. |

### 4.2 Freshness Multiplier Impact

The Freshness Multiplier is applied to the final composite score, creating significant separation between fresh and aged leads:

**Example: Same lead at different ages**

| Lead Age | Flag | Composite Score | Multiplier | Final Score |
|----------|------|-----------------|------------|-------------|
| 1 day | 🔥 HOT | 72 | 1.30x | 93.6 → P1 |
| 5 days | ⚡ WARM | 72 | 1.15x | 82.8 → P1 |
| 10 days | ● STANDARD | 72 | 1.00x | 72.0 → P2 |
| 25 days | ❄ COOLING | 72 | 0.85x | 61.2 → P2 |
| 45 days | ◌ COLD | 72 | 0.65x | 46.8 → P3 |
| 75 days | ○ STALE | 72 | 0.45x | 32.4 → P4 |
| 120 days | ✕ DEAD | 72 | 0.25x | 18.0 → P5 |

A lead that would be P1 when fresh becomes P5 when dead—same underlying business, vastly different actionability.

---

## 5. Dimension 1: FIT (Data-Calibrated)

### 5.1 Overview

**Question**: Can an MCA actually work for this business?
**Scale**: 0-100 (higher = better fit for MCA product)
**Note**: FIT scores are generally NOT time-weighted because they measure persistent business characteristics.

### 5.2 FIT Components (Calibrated)

| Component | Points | What It Measures |
|-----------|--------|------------------|
| Estimated Revenue Tier | 0-35 | Can they support MCA payments? |
| Revenue Consistency Profile | 0-30 | Steady vs lumpy cash flow |
| Revenue Quality Profile | 0-20 | Credit card processing likelihood |
| MCA Industry Propensity ★ | 0-10 | Historical MCA usage by industry (CALIBRATED) |
| Time in Business ★ | 0-5 | Stability and track record (CALIBRATED) |
| **TOTAL** | **100** | |

★ = Data-calibrated from 7,634 historical transactions

### 5.3 Industry Revenue Multipliers

| Industry | Rev/Employee (Monthly) | Midpoint |
|----------|------------------------|----------|
| Healthcare/Medical | $25K - $40K | $32K |
| Professional Services | $20K - $35K | $27K |
| Technology | $18K - $30K | $24K |
| HVAC/Plumbing/Electrical | $12K - $20K | $16K |
| Auto Repair | $10K - $18K | $14K |
| Construction | $10K - $18K | $14K |
| Salon/Spa | $10K - $15K | $12K |
| Restaurants/Bars | $8K - $15K | $11K |
| Retail | $8K - $12K | $10K |
| Trucking/Transportation | $8K - $12K | $10K |
| Landscaping | $6K - $10K | $8K |
| Cleaning/Janitorial | $5K - $8K | $6K |

### 5.4 MCA Industry Propensity (0-10 points) — CALIBRATED

Based on deal volume analysis of 7,634 historical transactions:

| Propensity | Industries | % of Deals | Points |
|------------|------------|------------|--------|
| VERY HIGH | Restaurants/Bars, Trucking/Transportation, Construction, HVAC/Plumbing | 27% | 10 |
| HIGH | Auto Services, Retail, Healthcare/Medical, Salon/Spa | 12% | 8 |
| MODERATE | Manufacturing, Wholesale, Landscaping, Professional Services, Fitness | 8% | 5 |
| LOWER | Consulting, Technology, Real Estate, Education, Other | 53% | 2 |

### 5.5 Top NAICS Codes by Performance (from TVT data)

| NAICS | Industry | Avg Perf | Avg Deal | Count |
|-------|----------|----------|----------|-------|
| 722511 | Full-Service Restaurants | 251% | $115K | 49 |
| 811111 | General Automotive Repair | 290% | $75K | 17 |
| 236115 | New Single-Family Housing | 250% | $51K | 21 |
| 238220 | HVAC/Plumbing Contractors | 103% | $169K | 26 |
| 484110 | General Freight Trucking (Local) | 110% | $65K | 40 |

### 5.6 Time in Business (0-5 points) — CALIBRATED

Based on 1,244 records with TIB data. Median: 7 years. 70%+ deals to businesses 3+ years old.

| Time in Business | Points | % of Deals | Notes |
|------------------|--------|------------|-------|
| 5+ years | 5 | 60% | Sweet spot—established businesses |
| 3-5 years | 4 | 16% | Solid history |
| 2-3 years | 3 | 9% | Developing track record |
| 1-2 years | 2 | 7% | Minimum threshold |
| <1 year | 0 | 8% | NURTURE flag—follow up at 1-year mark |

### 5.7 Geographic Propensity (Prospecting Bonus)

State-level concentration data for prospecting prioritization:

| Tier | States | % of Deals | Priority |
|------|--------|------------|----------|
| TIER 1 | FL (12%), TX (12%), CA (7%), NY (7%) | 37% | HIGHEST |
| TIER 2 | GA, NJ, NC, IL, PA, CT | 21% | HIGH |
| TIER 3 | OH, AZ, MD, MI, VA, WA, MA, CO, TN, IN | 22% | STANDARD |
| TIER 4 | All other states | 20% | LOWER |

### 5.8 Revenue Consistency Profile (0-30 points)

| Category | Industries | Points |
|----------|------------|--------|
| Highly Recurring | Medical/dental, veterinary, salons/spas, gyms, childcare | 30 |
| Steady | Restaurants, retail, QSR, auto repair, pharmacy | 25 |
| Seasonal Predictable | HVAC, landscaping, pool services, tax prep | 18 |
| Moderately Lumpy | Residential contractors, consultants, catering | 12 |
| Highly Lumpy | Commercial construction, real estate development | 5 |

### 5.9 Revenue Quality Profile (0-20 points)

| CC Level | Industries | Points |
|----------|------------|--------|
| Very High (70%+ CC) | Restaurants, bars, retail, salons, hotels, QSR | 20 |
| High (50-70% CC) | Medical offices, fitness, auto repair, veterinary | 16 |
| Moderate (30-50% CC) | Professional services, HVAC/plumbing (residential) | 12 |
| Low (10-30% CC) | B2B services, wholesale, consulting | 6 |
| Very Low (<10% CC) | Construction, trucking, manufacturing | 2 |

### 5.10 FIT Score Interpretation

| FIT Score | Interpretation | Action |
|-----------|----------------|--------|
| 85-100 | Excellent fit | High priority — pursue aggressively |
| 70-84 | Good fit | Standard priority |
| 55-69 | Moderate fit | Pursue if Intent/Timing strong |
| 40-54 | Marginal fit | Lower priority |
| 25-39 | Weak fit | Nurture only |
| 0-24 | Poor fit | Deprioritize |

### 5.11 FIT Flags

| Condition | Flag | Action |
|-----------|------|--------|
| TIB < 1 year | NURTURE | Follow-up at 1-year mark |
| Est. Revenue < $50K | UNDERSIZE | Note smaller deal potential ($10K-$30K range) |
| Consistency = Highly Lumpy | CASH FLOW RISK | Note repayment complexity |
| Quality = Very Low CC | VERIFICATION | Will need bank statements for verification |

---

## 6. Dimension 2: TIME-WEIGHTED INTENT

### 6.1 Overview

**Question**: Are there observable signals this business might need or want capital?
**Scale**: 0-100 (higher = stronger intent signals)
**NEW IN V4.0**: Every Intent signal is now time-weighted using exponential decay. The Time-Weighted Intent Score replaces the static Intent score from v3.0.

### 6.2 Time-Weighted Intent Calculation

```
Time-Weighted INTENT = Σ(Signal_Base_Value × e^(-λ × signal_age_days))
```

Where `Decay_Factor = e^(-λt)` and `λ = ln(2) / half_life_days`

### 6.3 Growth Signals (0-35 points)

| Signal | Base Pts | Decay Class | Detection Method |
|--------|----------|-------------|------------------|
| Active hiring (5+ roles) | 20 | RAPID | Indeed, LinkedIn, career pages |
| New location announced | 20 | STANDARD | News, social, permits, Google Maps |
| Franchise expansion | 18 | STANDARD | State registrations |
| Contract win announced | 15 | STANDARD | News, social, press releases |
| Active hiring (2-4 roles) | 12 | RAPID | Indeed, LinkedIn |
| Equipment purchase signals | 12 | STANDARD | Social media, job postings |
| Expansion language | 10 | RAPID | Website, social media |
| Active hiring (1 role) | 5 | RAPID | Indeed, LinkedIn |

### 6.4 Refinance Eligibility (0-25 points) — KEY PATHWAY

**Data insight**: 49% of deals are 2nd position or higher—refinance is a major opportunity.

| Signal | Base Pts | Decay Class | Detection |
|--------|----------|-------------|-----------|
| UCC from MCA lender (4-6 months old) | 25 | OPTIMAL WINDOW | Secretary of State UCC search |
| UCC termination (paid off) | 20 | EXTENDED | Secretary of State UCC search |
| UCC from MCA lender (6-9 months old) | 18 | EXTENDED | Secretary of State UCC search |
| Multiple MCA UCCs | 15 | EXTENDED | Secretary of State UCC search |
| UCC from MCA lender (3-4 months old) | 10 | EARLY WINDOW | Secretary of State UCC search |

### 6.5 Operational Signals (0-25 points)

| Signal | Base Pts | Decay Class | Detection |
|--------|----------|-------------|-----------|
| Seasonal business pre-peak | 15 | STANDARD | Industry + calendar timing |
| Renovation/remodel activity | 12 | STANDARD | Permits, social media |
| Inventory restocking signals | 10 | RAPID | Industry patterns, website |
| Fleet/vehicle needs | 10 | STANDARD | Job postings |
| Technology upgrade signals | 8 | STANDARD | Job postings, website changes |

### 6.6 Stress Signals (0-15 points)

| Signal | Base Pts | Decay Class | Detection |
|--------|----------|-------------|-----------|
| Tax lien filed | 12 | EXTENDED | Public records |
| Judgment filed | 10 | EXTENDED | Court records |
| Emergency promotions | 8 | RAPID | Social, website |
| Reduced operating hours | 8 | RAPID | Google Business |
| Negative review spike | 5 | RAPID | Google, Yelp |

### 6.7 Intent Pathway Tags

Based on dominant signals, assign a pathway tag to guide outreach messaging:

| Pathway | Dominant Signals | Message Approach |
|---------|------------------|------------------|
| GROWTH | Hiring, expansion, new locations | "Fuel your growth" |
| OPERATIONAL | Seasonal, equipment, inventory | "Capital when you need it" |
| REFINANCE | UCC in optimal window | "Better terms available" |
| STRESS | Liens, judgments, reduced hours | "Bridge the gap" |
| GENERAL | Good fit, no strong signals | "Did you know about MCA?" |

---

## 7. Dimension 3: TIMING

### 7.1 Overview

**Question**: Is NOW the right time to reach out?
**Scale**: 0-100 (higher = more urgent)
**Note**: In v4.0, TIMING weight is reduced from 30% to 20% because time-weighting is now embedded in Intent signals and applied via the Freshness Multiplier.

### 7.2 Seasonal Timing (0-30 points)

| Timing | Points |
|--------|--------|
| 4-6 weeks before industry peak | 30 |
| 6-8 weeks before peak | 25 |
| 8-12 weeks before peak | 18 |
| During peak season | 15 |
| Off-season | 8 |

### 7.3 Signal Recency (0-30 points)

Points based on the age of the most recent actionable signal:

| Signal Age | Points | Freshness Flag (v4.0) |
|------------|--------|----------------------|
| < 48 hours | 30 | 🔥 HOT |
| 2-7 days | 25 | ⚡ WARM |
| 7-14 days | 18 | ● STANDARD |
| 14-30 days | 10 | ❄ COOLING |
| 30-60 days | 5 | ◌ COLD |
| > 60 days | 0 | ○ STALE / ✕ DEAD |

### 7.4 Refinance Window (0-15 points)

| UCC Age | Points | Window Status |
|---------|--------|---------------|
| 4-5 months | 15 | OPTIMAL |
| 5-6 months | 12 | OPTIMAL |
| 6-7 months | 8 | GOOD |
| 3-4 months | 5 | EARLY |
| 7-9 months | 5 | LATE |

---

## 8. Priority Levels & Actions

### 8.1 The v4.0 Complete Scoring Formula

**Step 1: Calculate Time-Weighted Intent**
```
Time-Weighted INTENT = Σ(Signal_Base_Value × e^(-λ × signal_age_days))
```

**Step 2: Calculate Composite Score**
```
Composite Score = (FIT × 0.40) + (Time-Weighted INTENT × 0.40) + (TIMING × 0.20)
```

**Step 3: Apply Freshness Multiplier**
```
FINAL SCORE = Composite Score × Freshness_Multiplier
```

**Step 4: Assign Priority Level**
```
Priority = P1 if FINAL SCORE ≥ 75, P2 if ≥ 60, P3 if ≥ 45, P4 if ≥ 30, else P5
```

### 8.2 Priority Classification

| Priority | Score | Action | Timeline |
|----------|-------|--------|----------|
| P1 | 75-100 | Immediate outreach | Within 24 hours |
| P2 | 60-74 | High priority | Within 48 hours |
| P3 | 45-59 | Standard outreach | Within 1 week |
| P4 | 30-44 | Nurture sequence | Automated drip |
| P5 | 0-29 | Monitor | Quarterly review |

### 8.3 Priority Matrix

Cross-reference Fit, Intent, and Timing to determine priority:

|  | High Timing (60+) | Med Timing (40-59) | Low Timing (<40) |
|--|-------------------|--------------------|--------------------|
| High Fit + High Intent | P1 | P1 | P2 |
| High Fit + Med Intent | P1 | P2 | P3 |
| High Fit + Low Intent | P2 | P3 | P4 |
| Med Fit + High Intent | P1 | P2 | P3 |
| Med Fit + Med Intent | P2 | P3 | P4 |
| Low Fit + Any | P3-P4 | P4 | P5 |

---

## 9. Expected Deal Size — CALIBRATED

### 9.1 Deal Size Distribution (from 6,940 deals)

| Deal Size Range | % of Deals | Cumulative % | Note |
|-----------------|------------|--------------|------|
| <$25K | 27% | 27% | Small deals |
| $25K-$50K | 30% | 58% | Most common range |
| $50K-$75K | 15% | 72% | |
| $75K-$100K | 12% | 84% | |
| $100K-$150K | 8% | 92% | |
| $150K-$200K | 3% | 95% | |
| $200K+ | 5% | 100% | Large deals |

**Key insight**: Median deal size is $48,000. 72% of deals are under $75K.

### 9.2 Deal Size by Estimated Revenue

| Est. Monthly Revenue | Typical MCA Range | Median |
|----------------------|-------------------|--------|
| $150K+ | $75K - $200K | $100K |
| $100K - $149K | $50K - $125K | $75K |
| $75K - $99K | $35K - $85K | $50K |
| $50K - $74K | $20K - $50K | $35K |
| <$50K | $10K - $30K | $20K |

### 9.3 Deal Size by Industry (Calibrated Medians)

| Industry | Median Deal | Typical Range |
|----------|-------------|---------------|
| Manufacturing | $80K | $20K - $350K |
| Construction | $65K | $10K - $200K |
| Restaurants/Bars | $50K | $10K - $350K |
| HVAC/Plumbing | $50K | $10K - $350K |
| Auto Repair | $50K | $10K - $250K |
| Professional Services | $50K | $10K - $200K |
| Salon/Spa | $40K | $10K - $250K |
| Retail | $35K | $10K - $250K |
| Trucking | $35K | $15K - $350K |

---

## Appendix A: Complete Industry Scoring Reference

| Industry | Rev/Emp | Consist. | CC Level | Propensity | Median $ | Decay |
|----------|---------|----------|----------|------------|----------|-------|
| Restaurants/Bars | $11K | 25 | 20 | 10 | $50K | RAPID |
| Trucking/Transport | $10K | 25 | 2 | 10 | $35K | STANDARD |
| Construction | $14K | 12 | 2 | 10 | $65K | EXTENDED |
| HVAC/Plumbing | $16K | 18 | 12 | 10 | $50K | STANDARD |
| Auto Services | $14K | 25 | 16 | 8 | $50K | STANDARD |
| Retail | $10K | 25 | 20 | 8 | $35K | RAPID |
| Healthcare/Medical | $32K | 30 | 16 | 8 | $60K | EXTENDED |
| Salons/Spas | $12K | 30 | 20 | 8 | $40K | RAPID |
| Manufacturing | $18K | 18 | 6 | 5 | $80K | EXTENDED |
| Wholesale | $15K | 18 | 6 | 5 | $55K | STANDARD |
| Landscaping | $8K | 18 | 2 | 5 | $40K | STANDARD |
| Professional Services | $27K | 12 | 12 | 5 | $50K | EXTENDED |
| Fitness/Gyms | $12K | 30 | 16 | 5 | $45K | RAPID |
| Technology | $24K | 25 | 12 | 2 | $60K | EXTENDED |
| Consulting | $30K | 12 | 6 | 2 | $50K | EXTENDED |

---

## Appendix B: Seasonal Timing Calendar

| Month | Target Industries (4-6 weeks pre-peak) |
|-------|----------------------------------------|
| January | Fitness (New Year), Tax Services (prep), Restaurants (post-holiday recovery) |
| February | HVAC (prep), Construction (early spring), Landscaping (prep) |
| March | Construction, Landscaping, HVAC |
| April | Construction, Food/Hospitality (summer prep), Landscaping |
| May | HVAC (summer peak), Food/Hospitality, Construction |
| June | HVAC (peak), Construction, Food/Hospitality |
| July | HVAC (peak), Restaurants, Retail (back-to-school prep) |
| August | Food/Hospitality, Retail (back-to-school), Healthcare |
| September | Food/Hospitality, Retail (holiday prep), HVAC (winter prep) |
| October | Food/Hospitality, Retail (holiday), HVAC |
| November | Retail (holiday peak), HVAC (winter), Fitness (New Year prep) |
| December | Retail (holiday), Tax Services (prep), Fitness (New Year prep) |

---

## Appendix C: Decay Function Quick Reference

### C.1 Exponential Decay Formula

```
Decayed_Value = Base_Value × e^(-λ × days_old)
λ = ln(2) / half_life_days ≈ 0.693 / half_life_days
```

### C.2 Pre-Calculated Lambda Values

| Decay Class | Half-Life | Lambda (λ) |
|-------------|-----------|------------|
| RAPID | 7 days | 0.099 (lose ~10% per day) |
| RAPID | 10 days | 0.069 (lose ~7% per day) |
| STANDARD | 21 days | 0.033 (lose ~3% per day) |
| STANDARD | 30 days | 0.023 (lose ~2% per day) |
| EXTENDED | 45 days | 0.015 (lose ~1.5% per day) |
| EXTENDED | 60 days | 0.012 (lose ~1% per day) |
| STRUCTURAL | 90 days | 0.008 (lose ~0.8% per day) |

### C.3 Decay Percentage at Key Time Points

| Half-Life | 7 days | 14 days | 30 days | 60 days | 90 days |
|-----------|--------|---------|---------|---------|---------|
| 7 days (RAPID) | 50% | 25% | 6% | 0.4% | ~0% |
| 21 days (STD) | 79% | 64% | 37% | 14% | 5% |
| 45 days (EXT) | 90% | 80% | 63% | 40% | 25% |
| 90 days (STRUCT) | 95% | 90% | 79% | 63% | 50% |

---

## Summary

**MCA Predictive Lead Intelligence Framework v4.0**
*Time-Weighted Scoring Engine Edition*
*January 2026*

Based on analysis of 7,634 historical MCA transactions
Enhanced with exponential decay time-weighting and freshness flags

**Key Enhancements in v4.0:**
- Exponential decay engine with signal-specific half-lives
- Lead freshness flags (🔥 HOT → ∅ EXPIRED)
- Freshness multiplier (0.1x to 1.3x) on final scores
- UCC optimal window curve for refinance timing
- Multiplicative scoring architecture
- All v3.0 calibrated data preserved and enhanced
