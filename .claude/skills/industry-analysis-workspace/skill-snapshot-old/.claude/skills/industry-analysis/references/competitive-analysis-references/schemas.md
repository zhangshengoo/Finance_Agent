<!-- Adapted from anthropics/financial-services @ 120a31d (Apache 2.0). Forked unmodified on 2026-06-04 as reference skeleton; do not edit in place. See LICENSE-anthropic-financial-services for full license. -->

# Schemas Reference

Additional table formats not shown in main SKILL.md.

## M&A Transaction Table

| Acquirer | Target | Date | Deal Value | Multiple | Rationale |
|----------|--------|------|------------|----------|-----------|
| Company A | Company B | MMM YYYY | $X.XB | X.Xx EV/Rev | [Strategic logic] |

State multiple methodology: "X.Xx EV/Revenue" or "X.Xx EV/EBITDA"

## Scenario Analysis Table

| Scenario | Probability | Valuation | Key Assumptions |
|----------|-------------|-----------|-----------------|
| Bull | XX% | $XXB | [Specific, quantified] |
| Base | XX% | $XXB | [Specific, quantified] |
| Bear | XX% | $XXB | [Specific, quantified] |

## Slide Structure

```
┌─────────────────────────────────────────────────────────────┐
│ [Insight headline, not topic]                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                     [Main Content]                          │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ Source: [Citation] ([Date])                                 │
└─────────────────────────────────────────────────────────────┘
```
