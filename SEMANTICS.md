# Financial semantics decision record

Status: C1 IN PROGRESS. Structural findings verified; forecast-policy assumptions are not yet frozen. Created 2026-09-13.

The contract takes precedence over sample imitation. No request-ID-specific rules are permitted. A sample answer matching itself in evaluator tests is not prediction accuracy.

## Verified findings

| Decision | Finding | Evidence | Consequence |
| --- | --- | --- | --- |
| D01 | Current available balance is a supplied snapshot; no snapshot timestamp field exists. | financial_profiles.csv schema; problem statement | Do not reconstruct an opening balance by replaying all history. Pending/same-day details still require an explicit policy. |
| D03 | Future event_date does not mean future knowledge. | 47 events have event_date after the associated request; every one is scheduled. event_103 is next confirmed salary for request_01. | Retain supplied confirmed future events; don't discard them by event_date alone. |
| D03 | Samples/data do not exercise messages sent after the request. | Audit of all 215 messages against their users' supplied requests: zero later messages. | Future-message handling requires synthetic tests, not a claimed sample-derived rule. |
| D04 | There are no financial event rows with settlement_date equal to their user's request_date. | Audit across 275 requests and 25,342 events. | Same-day transaction handling cannot be inferred directly from these rows; projected occurrences can still land on request day. |
| D07 | Spending-change IDs identify historical members of recurring series. | request_06 stops event_476, a settled subscription from the prior month. request_11 reduces historical dining event_989. request_21 changes events_1815 and _1816 from the prior month. | Changes target future occurrences of the identified series, not a retroactive cash credit. |
| D07 | All four flexibility values must be supported. | fixed: 21,138; stoppable: 1,297; reducible: 2,682; reducible_or_stoppable: 225. | Both event and user permissions must allow the specific action. |
| D08 | Every supplied option is internally exact at its provided precision. | For all 790 options, payment_amount * number_of_payments == total_payable_amount == requested_amount + financing_fee. | Preserve given installment amounts; do not adjust the last installment or add financing fees a second time. |
| D08 | Sample installment outputs reproduce the provided option schedules. | All 25 sample outputs pass exact schedule/static checks. request_02 uses three payments of 15,952,906.67, totaling 47,858,720.01 including fees. | Validate the serialized schedule with Decimal, never floating tolerance. |
| Lifecycle | A link can join distinct cash transactions. | event_98 settled purchase and event_99 settled refund; event_1855 investment contribution and event_1856 non-cash valuation. | Preserve separate dated cash effects; only superseded representations should be deduplicated. |
| Evidence | A request-linked message can describe salary. | message_04, linked to request_06, specifies temporary monthly pay of EUR 1,037.52. | Linkage is context/ownership; extracted meaning determines financial scope. |
| D09 | Historical income may differ from next confirmed salary. | user_01 has a prorated first salary of ZAR 12,826 and a next confirmed salary of ZAR 23,320. | Do not project a prorated first payment as regular salary. |

## Unresolved policies and next evidence

| Decision | Proposed direction | Required before freezing |
| --- | --- | --- |
| D01 | Supplied balance is request opening capacity; reserve pending debits once. | Compare cash-flow reconstructions against samples with pending authorizations; document whether reservations are already reflected. |
| D02 | Use a fixed request-anchored horizon. | Test the 90-date versus +90-day boundary using reconstructions and a synthetic boundary case; label unidentifiable conventions honestly. |
| D03 | Message visibility uses sent_at with explicit date/timezone convention; image observation time remains unknown unless supported. | Extract image dates and establish source provenance; never use a document's effective date as proof of observation time. |
| D04 | One explicit same-day ordering for both simulators, with no accidental netting. | Decide conservative handling of unknown intraday order, and test modeled request-day obligations. |
| D05 | Apply explicit financial amendments, not embedded instructions to alter challenge rules. | Inspect extracted facts for request deadline or preference changes and record concrete conflicts. |
| D06 | Respect profile duration limits and exact offer schedules. | Compare payment-count and elapsed-calendar interpretations on offered/sample plans; record whether they actually discriminate. |
| D07 | Historical series identifier; future savings only, in the output's home-currency convention. | Define deterministic series matching, recurrence proof, first affected occurrence, and treatment of foreign-currency modifiable series. |
| D09 | Infer supported cadence and conservatively estimate variable expenses. | Compare candidate estimators using sample forecast traces; no estimator has yet been implemented or selected. |
| D10 | Only after official ranking ties, prefer fewer changes then lower reductions then stable IDs. | Preserve this as a secondary convention, not an organizer-stated rule; confirm its effect in optimizer cases. |
| D11 | Unresolved essential evidence blocks finalization; save an actionable report. | Verify bounded extraction/escalation failure handling. No answer may silently become not_affordable due to missing evidence. |
| D12 | Flash-Lite text, Flash images/ambiguities, Pro final bounded escalation. | Configure local API credential and verify project access/limits before live calls. No key is visible in the current process as of the C2 audit. |

## C2 evidence

- Command: `python code/main.py audit`.
- Counts: 250 evaluation requests, 25 samples, 275 profiles, 25,342 events, 790 payment options, 215 messages, 134 rate rows, 16 images, 250 output-template rows.
- Input integrity errors: zero. All 16 blank amounts have image links and existing PNG files.
- Exact currency conversion keys needed by eligible supplied foreign cash rows: all present.
- Sample static contract errors: zero; this does not assert forecast safety or prediction accuracy.
- `python -m unittest discover -s code/tests -v`: 20 tests passed at the initial C2 checkpoint, including deliberately corrupted plans and forbidden changes.
- No output.csv has been generated. No final-dataset model usage has been incurred.
- After adding offline evidence and Gemini adapter tests, the complete suite has 36 passing tests. Live extraction stops before network access because the credential is unavailable.
- C2 remains IN PROGRESS: the static field evaluator is implemented, but trace-grounded explanation checks and financial safety validation are not implemented yet. No full checkpoint pass is claimed.

## Decision history

- User said "Proceed", accepting IMPLEMENTATION_PLAN.md as the execution baseline: C0 PASS.
- C2 input auditing and evaluator work proceeded independently while C1 forecast-specific policies remain unresolved, as explicitly permitted by the plan's dependency rule.
- No safety rule, model scope, or acceptance criterion has been relaxed. C1 cannot be marked PASS until the policy table above is resolved or explicitly documented as approved assumptions.

## Live evidence review, 2026-09-13 11:35 IST

- Model access/key statements above describe earlier checkpoints: Flash-Lite 3.5 and Flash 3.6 have now succeeded. Pro 3.1 Preview returned quota failure and is disabled. Actual project quotas remain unverified; the local ledger is only a conservative budget.
- The sample evidence report contains 22 sources (17 messages, five images), ten flagged by extraction v1. This is extraction coverage, not resolved evidence or prediction accuracy.
- Visual inspection confirms image_04 is cropped below Item Bill INR 2854.00; that visible subtotal is not proof of the final settled charge. Do not substitute an invented total. Its forecasting relevance needs explicit assessment.
- image_02 has inconsistent receipt prose versus the received/due table. It also refers to a multi-month historical rent period, so its total must not silently become monthly rent.
- image_01 shows gross salary IDR 4500000 and net pay IDR 4365000. The gross figure is not available recurring cash. Its print date is not proof of bank settlement; linked event dates and document dates require separate treatment.
- image_05 visibly distinguishes INR 704.05 due through 2026-02-06 from INR 822.05 afterward. Applicable amount depends on resolved payment timing, not choosing the lower number unconditionally.
- v1 message_14 and message_17 copied amounts from context while quoting source text with no numeric amount. Added numeric quote support checks and prompt v2; do not automatically apply these facts as independent amendments.
- The pure cash-flow component supports explicit debits-first or credits-first ordering and a caller-specified inclusive horizon. No dataset-wide policy is frozen by this API. Tests prove arithmetic/replay invariants, not that recurrence or extracted financial facts are correct.
- D06 is resolved for this dataset: every installment offer uses a 28, 30, or 31-day frequency, so each payment represents one monthly installment. Compare `number_of_payments` to `max_installment_months`; a blank profile limit rejects installments. The five sample installment choices all use three payments within their limits, while their 15/18/21-payment alternatives exceed the corresponding profile limits.
- Provisional maximum-of-six variable expenses materially underperforms latest-observation policy after the first integrated sample run: maximum matches 14/25 methods and 12/25 earliest dates; latest matches 20/25 methods and 18/25 earliest dates. Amount matches remain low (1/25 versus 3/25) because recurrence and evidence differences remain. This is the promised mismatch report, not authority to silently freeze a replacement policy.
