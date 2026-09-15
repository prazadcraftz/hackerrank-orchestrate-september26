# PC02 — Variable-expense forecast estimator

Status: APPROVED 2026-09-13 13:07 IST. Created 2026-09-13 12:20 IST.

Original provisional rule: forecast each variable recurring expense at the maximum of its six most recent comparable settled observations. The user approved this specifically as provisional, with sample mismatches reported before freezing.

Proposed rule: forecast each supported variable recurring series using its latest comparable settled amount. Continue to reserve pending debits separately, include all supported occurrences, use exact dated FX, and independently replay the entire 90-date path. Do not use this estimator for income.

Evidence: after applying current evidence amendments and recurrence rules, the 25 solved examples produce the following field matches:

| Policy | Safe amount exact | Status | Method | Payment plan | Earliest full date | Spending changes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| latest | 3/25 | 19/25 | 20/25 | 19/25 | 18/25 | 21/25 |
| maximum-of-six | 1/25 | 13/25 | 14/25 | 14/25 | 12/25 | 21/25 |

The maximum rule is materially more conservative and changes valid methods/plans, not just numerical tolerance. Latest is also consistent with the dataset's regularly refreshed transactions, but the problem statement only says “conservatively” and does not explicitly prescribe an estimator. Remaining mismatches show that latest is not a claim of full ground-truth reconstruction.

Effect: latest raises capacity for some users relative to maximum. Safety invariants remain enforced against the resulting forecast, but forecast risk is less conservative if the next variable bill rises above the latest observation. This affects C1, C5, C8, and final predictions. No output has been published using either policy.

Approval requested: freeze `latest` for the final run, or retain the previously approved provisional `maximum` despite lower sample agreement. No request-ID exceptions or label hardcoding are proposed.

Decision: the user replied "Approved" directly to the combined request to authorize the remaining full financial-evidence transfer to Google Gemini and confirm PC02 `latest`. The final run is therefore frozen to `latest`; no request-ID exceptions or sample-label hardcoding are authorized.
