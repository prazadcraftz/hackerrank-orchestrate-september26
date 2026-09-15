# Evidence and forecast review — 2026-09-13 11:45 IST

This is a development checkpoint, not a completed financial agent or submission.

## Authority and live extraction

The user answered "yes" to explicit authorization for sending the dataset's financial messages, images and linked context to Google Gemini for sample testing and the final full-dataset run. The subsequent authorized sample command launched successfully. This resolves the prior execution-authorization blocker; do not request the same authorization again unless scope changes.

Prompt-v2 sample extraction processed 22 sources. After correcting a numeric quote-check bug involving sentence-ending punctuation, all 22 were revalidated from cache with zero new calls. The resulting report is code/runs/evidence-v2-rechecked.json: 13 sources still carry review flags. Keep code/runs/evidence.json and evidence-v2.json for comparison. Flags include both genuine missing evidence and optional fields that the model described as uncertain; they are not 13 proven unanswerable requests.

Do not confuse schema-valid extraction with financial resolution. In particular, v2 omitted v1's cropped-total warning for image_04 and inconsistent-receipt warning for image_02. Both warnings remain relevant. Image_05 v2 retained only the lower due amount, while the visible image also states a higher amount after its deadline. These omissions must be resolved before applying image amounts.

## Provisional conventions approved by user

- 90 dates including request day (through request date + 89 days).
- Debits before credits where intraday order is unknown; request payments follow ordinary flows.
- Maximum of the six most recent comparable expenses for provisional variable-spending forecasts.
- Report sample mismatches before freezing these conventions. This is not approval to accept residual correctness issues or bypass missing evidence.

## Offline study findings

Command: python code/study_recurrence.py. Report: code/runs/recurrence-study.json.

Five samples have no supplied message/image evidence and were studied under 16 horizon/order/estimator combinations. Twenty were skipped pending evidence resolution. The study uses answer-free request objects for construction and accesses sample answers only for comparison. It never writes output.csv.

- Short salary history plus a next confirmed payroll is not currently sufficient for the study's three-occurrence recurrence detector. request_01 therefore misses later payroll projections. This is an identified limitation, not evidence that the maximum expense estimator is wrong.
- Category-only grouping conflates primary and secondary household salary in request_13. Income needs source/series identity and effective cessation handling, not a single category median.
- request_05 has a structured description "Final employer payroll". A generic repeating-salary projection ignores that cessation evidence. The diagnostic must not be used for predictions.
- request_21 remains different from its sample capacity even across the tested expense estimators. The reason is not yet resolved. Do not claim validated accuracy or fit a request-ID correction.
- request_09's safe amount matches under latest/mean variants but not under the provisional maximum estimator. One matching field is not a passing sample decision.

## Implemented independent components

80 tests pass. plans.py generates exact, replay-verified no-change full, partial, installment and wait candidates and ranks official criteria. It requires an explicit installment-duration predicate and does not conclude unaffordability before the separate spending-change search. recurrence.py proposes supported monthly/fixed-day cadence and exposes explicit experimental expense estimators; it does not establish confirmation of future income.

Next: resolve extraction disagreements and income-series identity, then integrate the approved provisional forecast conventions and report all sample discrepancies. Spending-change search, complete decision validation/output, full-dataset prediction, actual final-run usage report and packaging remain unfinished.

## Integrated comparison update, 2026-09-13 12:10 IST

Evidence amendments, series-aware salary recurrence, plan generation, spending-change search, ranking and independent replay are integrated for diagnostics. All 25 samples produce contract-valid rows with no technical blockers. Under `latest`, matches are: amount 3/25 exact (5/25 within 1%), status 19/25, method 20/25, payment plan 19/25, earliest date 18/25, spending changes 21/25. Under provisional `maximum`, the corresponding status/method/plan/earliest counts are 13/14/14/12, with only one exact amount.

This is strong evidence that maximum-of-six is too conservative for the generated examples. Replacing it is a financial policy change and remains pending explicit approval; the reports preserve both variants. Several remaining mismatches are recurrence/timing issues rather than estimator selection, so switching to `latest` will not be represented as complete accuracy.

## Parallel implementation and safety update, 2026-09-13 13:06 IST

Independent packaging and usage-report lanes are implemented and refuse incomplete inputs. A read-only cache audit finds 172/231 sources currently valid (149 Lite, 23 Flash) and 59 still requiring extraction (48 messages, 11 images). Cache-only consolidation is diagnostic only; after a safety review, every missing visible message now blocks the corresponding user's request, while an unavailable settled-history image remains a nonblocking review item unless it leaves a future pending/scheduled cash amount unresolved.

Two income-series defects are closed. One-time employer arrears no longer replace recurring salary, and descriptions identifying freelance, independent, retainer, seasonal, peak-season, temporary-assignment, or previous-employer income are excluded from salary projection. The concrete request_90 regression now produces safe-today capacity zero rather than relying on invented future independent-work credits. The full suite passes 131 tests; no incomplete evidence path can publish root output.

## Full text completion and image quota blocker, 2026-09-13 13:41 IST

The user approved both PC02 `latest` and the remaining full financial-evidence transfer to Google Gemini. Quota-isolated resumption completed candidate extraction for all 215 messages. The validator now ignores model-supplied labels in `source_identity` and deterministically restores the CSV source ID; this preserves the no-ID-rewrite guarantee while recovering otherwise valid quoted facts. Fresh invalid bodies are retained only under diagnostic cache names. The suite passes 134 tests.

Cache coverage is 220/231: all messages plus images 01-05. Gemini 3.6 Flash continues to return HTTP 429, so images 06-16 cannot be obtained from the approved image model today. Local visual review was performed but has not been applied to financial state. Clearly visible candidate totals include image_06 INR 1,995; image_07 shows invoice total INR 8,528.10 and rounded grand total INR 8,528; image_08 INR 15,339; image_09 INR 723; image_10 INR 79,679.26; image_11 INR 3,650; image_12 USD 33.50; image_13 INR 2,298; image_14 handwritten INR 4,593; image_15 INR 9,968. Image_16 visibly shows energy amount INR 333.24 and CGST INR 29.99 but no unambiguous final total, so it remains unresolved even under local review. A user decision is required before substituting documented local review for the approved Gemini path.
