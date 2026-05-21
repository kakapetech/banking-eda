# P02 ⭐⭐ — Banking EDA
## The Darko Method 2026 | Student Project

---

## Your Brief

**Company:** NexBank
**Your role:** Data Analyst, Risk Analytics

The Chief Risk Officer needs statistical evidence of fraud patterns and customer
segment behaviour from the transaction data.

**Question 1 — Fraud patterns:** Do fraudulent transactions cluster in specific
merchant categories, channels, or time periods? Use groupby to find where fraud
concentrates.

**Question 2 — Segment behaviour:** How do transaction amounts and frequencies
differ across Retail, Premium, Business, and Student customer segments? Build a
`SegmentProfiler` class that computes statistics per segment including fraud rate.

**Question 3 — Chi-square independence test:** Are fraud rates statistically
independent of `merchant_category`? Use `scipy.stats.chi2_contingency()` to test
this. If p < 0.05 the relationship is real and statistically significant.

**Question 4 — Transaction anomalies:** Flag transactions that are suspicious
by amount using IQR + Z-score. Also flag the inverse: transactions marked
`is_fraud=True` but with a normal amount (hardest to detect).

**Input:** `data/processed-data.csv` (from Module 05)
**Output:** `reports/analysis_report.txt` + `reports/anomalies.csv` + `reports/segment_profile.csv`

---

## Success Criteria

- [ ] `EDAEngine` extended with `chi_square_test()` method
- [ ] `SegmentProfiler` class computes fraud rate and stats per customer segment
- [ ] `AnomalyDetector` extended with `flag_fraud_anomalies()` method
- [ ] 12+ unit tests pass
- [ ] Project pushed to GitHub with Module 04 branching workflow

---

> Build from scratch using the teaching project as your reference.
