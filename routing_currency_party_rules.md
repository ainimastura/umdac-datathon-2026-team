# Party type, currency and routing rules: all anomaly types + normal baseline (17 Nov 2026)

Source: claude_routing_currency_party.csv, 57,006 rows = 7,006 anomaly rows (6 types) + 50,000 normal sample. Anomaly rows are in the same order as the earlier per-type files (verified on USD_AMOUNT, all 6 types), so accounts and timestamps were attached by position. Recall-file normals (428,177 rows with accounts and timestamps) used for three cross-checks, marked [R].

Unit of analysis: one independent event per test. Romance = 500 bursts, duplicates = 185 clusters, other types = one row per record.

## A. Normal baseline (structural rules)

A1. Party types
IF normal payment THEN ORDERING_TYPE = B with probability 78.3% and BENEFICIARY_TYPE = C with probability 71.5%, drawn independently (p = 0.44) FOR all normal payments.
Mix: B->C 56.0%, B->B 22.3%, C->C 15.4%, C->B 6.3%.

A2. Currency
IF normal payment THEN CURRENCY_CODE = home currency of the ordering bank's country in 89.4% of cases; otherwise mostly EUR (43.7%) or USD (21.5%), and the beneficiary country's currency in 39.7% of those cases. 145 currencies. Home currency = most common currency per ordering country (e.g. LU, DE, FR = EUR; IM = GBP).

A3. Conversion count
IF any payment THEN CURRENCY_CONVERSION_COUNT = number of consecutive bank pairs on BIC8_PATH whose countries have different home currencies. Holds for 57,004 of 57,006 rows where testable (99.98% of continuous normal paths; 8 exceptions involve rare countries). Hidden "..." hops add no conversions (3,803 of 3,803 broken normal paths). Consequences: count <= PARTICIPANT_COUNT - 1 always; count = 0 only when every bank on the path shares a currency zone.
Rejected: count = number of border crossings (88.3% only; fails inside the eurozone).

A4. Path structure (100% of 57,006 rows each)
- PARTICIPANT_COUNT = number of banks in BIC8_PATH, not counting "...".
- CONTINUITY_QFLAG = N if and only if BIC8_PATH contains "...".
- TRANSACTION_TYPE_CODE = Direct if and only if PARTICIPANT_COUNT = 2.
- "..." is never the first or last element.

A5. Path length
IF normal payment THEN PARTICIPANT_COUNT follows a geometric law: P(k) falls by a factor of about 0.37 per extra bank (62.9% / 23.5% / 8.6% / 3.2% / 1.2% for 2-6 banks). The same bank pair is routed direct about 63% of the time and multi-hop otherwise [R], so path length is drawn per payment, not fixed per pair.

A6. Hidden hops
IF any hop THEN it is hidden as "..." with probability about 5% (5.2% measured), independently per hop. Flag N rate by participants 2-6: 5.0 / 9.2 / 14.1 / 20.0 / 21.4% vs 1 - 0.95^(k-1) = 5.0 / 9.8 / 14.3 / 18.5 / 22.6%. Direct payments can be flagged N ("A;...;B").

A7. Covered vs Indirect
IF multi-hop payment THEN TRANSACTION_TYPE_CODE is a fixed property of the (first bank, last bank) pair: 5,256 of 5,256 bank pairs with 5+ multi-hop payments are all-Covered or all-Indirect [R]; 16.3% of pairs are cover pairs; 11.3% of multi-hop payments in the random sample are Covered. Not related to country, currency, party type, flag, path length or amount.

A8. Endpoint mismatch
IF normal payment THEN the path's first bank differs from ORDERING_BIC8 with probability 5.0% and its last bank differs from BENEFICIARY_BIC8 with probability 5.0%, independently (both: 0.20% vs 0.25% expected). The substitute bank is unrelated (same country in only 6%). Not related to type code, flag or path length.

A9. Duration
IF normal payment THEN TOTAL_DURATION is drawn from one of two modes: fast (median 25 s direct, +10 s per extra bank) or slow (median about 1,470 s). Slow share (over 300 s): 35.9% direct, 44.4 / 54.0 / 62.9 / 72.4% for 3-6 banks. Slow share differs strongly by country and bank (11-92% across beneficiary countries). No hour-of-day or weekday effect [R]; duration is redrawn on every payment, even on the same account pair (0 of 19,793 pairs with 3+ payments repeat one duration) [R].
Not resolved: what sets a bank's or country's slow share.

## B. Anomaly rules

B1. ROMANCE_SCAM (500 bursts, 2,476 rows)
IF ROMANCE_SCAM THEN
- ORDERING_TYPE = C (500 of 500 bursts; baseline 21.7% C). Beneficiary type free: C 72.8% vs 71.5% baseline.
- every payment in a burst copies one route exactly: path, duration, currency, conversion count, flag, type code and both BICs are identical within 500 of 500 bursts. Normal repeat payments on a pair share a path 24% of the time and a duration under 2% of the time [R].
- no endpoint mismatch at either end: 0 of 500 each (baseline 5%; p = 2e-11).
- Covered almost never: 1 of 191 multi-hop bursts (baseline 11.3%; p = 6e-9).
- victims sit in different countries from normal consumers: IN 19.2%, CN 17.2%, US 4.8%, then ID, NG, PK, BR, BD (normal C orderers: US 14.7%, CH 9.3%, GB 6.8%). Currency follows: INR 17.8%, CNY 16.8%; currency = ordering home currency 94.0% (baseline 89.4%, p = 0.0005).
- cross-border by construction: same country 3.0% (baseline 7.0%), zero conversions 2.6% (baseline 10.8%).
- path length and flag N at baseline given geography: direct 61.8%, N 8.6% (predicted 8.6%).
- slow share 71.4% vs 66.1% predicted from origin and destination country (p = 0.008): mostly geography, small unexplained excess.
Rejected: restricted to one currency; longer or broken paths; duration tied to burst length (route duration exceeds the burst's whole time span in 52% of bursts, so later payments are sent before the first has arrived).

B2. CEO_SCAM (945 rows)
IF CEO_SCAM THEN
- ORDERING_TYPE = B (945 of 945; baseline 78.3%; p < 1e-90). Beneficiary type free: C 72.3%.
- last bank on path = BENEFICIARY_BIC8 always: 0 mismatches of 945 (p = 3e-21). Ordering-end mismatch at baseline: 6.1% (p = 0.12).
- Covered almost never: 7 of 353 multi-hop (2.0%; p = 7e-11).
- cross-border: same country 1.3%, zero conversions 2.1% (p < 1e-15 each).
- currency mix at baseline: EUR 30.8%, USD 16.0%, CHF 9.8%, GBP 7.9%; = ordering home currency 89.8% (p = 0.67).
- path length, flag N at baseline (direct 62.6%; N 7.2% vs 7.6% predicted).
- slow share 59.6% vs 55.4% predicted from geography (p = 0.006): mostly geography, small excess.
Each scam is routed afresh: same victim or same mule never repeats a path or duration.

B3. ACCOUNT_REPLACEMENT_SCAM (649 rows)
IF ACCOUNT_REPLACEMENT_SCAM THEN
- party types at baseline: B->C 57.0%, B->B 21.3%, C->C 16.5%, C->B 5.2% (p = 0.58). Not locked to Business victims.
- last bank on path = BENEFICIARY_BIC8 always: 0 mismatches of 649 (p = 1e-14). Ordering-end mismatch 5.2% (baseline).
- Covered almost never: 3 of 206 multi-hop (1.5%; p = 1e-7).
- cross-border: same country 0.6%, zero conversions 2.0%.
- currency mix at baseline (EUR 31.6%, USD 20.0%); = ordering home currency 91.5% (p = 0.07).
- flag N and duration at baseline given geography (slow 57.8% vs 55.3% predicted, p = 0.18). Direct share 68.3% vs 64.2% predicted (p = 0.03, not claimed).

B4. FAT_FINGER_MISTAKE (1,940 rows)
IF FAT_FINGER_MISTAKE THEN party types, currency, conversion count, type code, flag, duration and endpoint mismatch all follow the normal baseline: party mix p = 0.27; currency = home 89.3% (p = 0.94); Covered 13.2% of multi-hop (p = 0.13); mismatch 5.5% / 5.2% (p = 0.25 / 0.75); slow 40.3% vs 41.1% predicted (p = 0.48); N 7.0% (p = 0.33). Only USD_AMOUNT is altered (see fat_finger_rule.md). Multi-hop share 34.5% vs 37.1% (p = 0.016) not claimed given the number of tests.

B5. DUPLICATE_PAYMENT (185 clusters, 679 rows)
IF DUPLICATE_PAYMENT THEN every copy in a cluster is identical in path, duration, currency, conversion count, flag, type code, both BICs and party types (185 of 185 clusters); only EPOCH_SECONDS differs. Across clusters everything follows baseline: party mix p = 0.41; Covered 10.8% (p = 1.0); mismatch 4.3% / 4.9%; N 7.0%; slow 47.6% vs 41.3% predicted (p = 0.08).
Note: row-level tests overstate significance (p = 0.008 for party mix) because copies are not independent.

B6. CUSTOMER_RECALL (317 rows)
IF CUSTOMER_RECALL THEN all three dimensions follow baseline: party mix p = 0.75; currency = home 89.6% (p = 1.0); Covered 11.5% (p = 0.89); mismatch 4.7% / 4.4%; slow 42.0% vs 40.4% (p = 0.57). Flag N 11.0% vs 7.5% predicted (p = 0.018): third appearance of the same borderline signal, still not claimed after roughly 100 tests in this file.

## C. Cross-anomaly finding: the three scams share one routing signature
IF the payment is ROMANCE_SCAM, CEO_SCAM or ACCOUNT_REPLACEMENT_SCAM THEN the route is built fresh to the mule's own bank: beneficiary-end mismatch 0 of 2,094 events (baseline 5%), Covered 11 of 750 multi-hop events (1.5% vs 11.3%), domestic 31 of 2,094 (1.5% vs 7.0%).
Mechanism supported by the data: cover status belongs to established bank pairs (A7), and scam corridors are new. The (first bank, last bank) pair of a scam appears in normal traffic for only 3.6% (romance), 10.1% (CEO) and 12.2% (account replacement) of events, against 53-75% for fat finger, duplicate and recall. Whenever an anomaly does run on a known cover pair it is labelled Covered (79 of 79).
The non-scam anomalies (fat finger, duplicate, recall) are ordinary payments with one field changed or none.

## D. Summary table
| Type | Party lock | Currency | Covered (multi-hop) | Beneficiary-end mismatch | Within-event copies |
|---|---|---|---|---|---|
| Normal | none (78.3% B, 71.5% C) | 89.4% home | 11.3% | 5.0% | paths redrawn |
| Romance | ordering C 100% | victim home (INR, CNY lead) | 0.5% | 0% | identical |
| CEO | ordering B 100% | baseline | 2.0% | 0% | n/a |
| Account replacement | none | baseline | 1.5% | 0% | n/a |
| Fat finger | none | baseline | 13.2% | 5.5% | n/a |
| Duplicate | none | baseline | 10.8% | 4.3% | identical |
| Recall | none | baseline | 11.5% | 4.7% | n/a |

## E. Method notes
- Geography control: logistic model of slow / multi-hop / flag N on ordering country, beneficiary country and ordering type, fitted on the 50,000 normal rows (holdout check: 41.3% observed vs 40.8% predicted), then applied to each anomaly type.
- Exact binomial tests against baseline rates for mismatch, Covered, domestic and zero-conversion shares.
- About 100 tests were run on this file; only effects with p below 1e-4 are stated as rules.
- Not available in this file: text fields. Not resolved: source of the 4-5 point slow-share excess in romance and CEO scams (bank-level effects are a candidate).

## F. Interpretation (not observed)
- Conversion count tracking currency-zone changes is how correspondent chains work: each bank holding a different currency converts.
- Cover status as a property of a bank pair matches the cover method, which needs a standing relationship between sender and receiver banks; a fraudster's bank is a new counterparty, so the payment goes serially.
- Romance victims concentrated in India and China, then other very populous countries, looks like a draw proportional to population; mule destinations (Egypt, China, Indonesia) explain the slower, always cross-border routes.
- Endpoint mismatch at 5% may represent accounts serviced through another institution; its absence for scam beneficiaries is a generator artefact that would make a strong detection feature in this dataset but should not be assumed in real traffic.
