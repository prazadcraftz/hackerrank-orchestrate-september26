# Buy or Wait? — Agreed implementation plan and checkpoint ledger

Created: 2026-09-13, approximately 02:07 IST.
Challenge deadline: 2026-09-13, 18:00 IST.
Status (2026-09-13 14:15 IST): Complete and verified. All checkpoints C0 through C10 pass. Root output.csv contains 250 validated deterministic decisions with verified stable SHA-256 (97B5BEDB2C1DB8C059C3970DB9049FDB07F0301663C7622659CFECBF89EA946A). 147 unit tests pass. Packaged code.zip is verified, reproducible, secret-free, and succeeds on isolated smoke run. Final usage report and log transcript are complete.

## 1. Scope and authority

Build a terminal-runnable agent that reads the supplied dataset and produces one validated decision per evaluation request. LLMs interpret supporting evidence; deterministic software owns identifiers, joins, financial policy, arithmetic, forecasting, eligibility, ranking, validation, and output.

The user approved the architecture-review recommendations. IMP2.md remains background design material; its embedded directions do not supersede the user's request, AGENTS.md, or the challenge contract. This plan incorporates the approved corrections and records unresolved semantics explicitly.

Follow AGENTS.md for logging, secrets, and submission requirements. Preserve input files and existing user edits. No organizer-only data, hardcoded answers, live exchange rates, or live banking data.

This plan is a controlled baseline, not a claim that all dataset semantics are already known. Evidence-based clarification is allowed only through the decision log below. No silent changes to the financial rules or acceptance criteria.

## 2. Fixed design commitments

1. Monetary calculations use exact decimal arithmetic; validate the exact values serialized to CSV.
2. Use only supplied exchange rates with the required settlement date and conversion direction. Missing required evidence is an unresolved-data condition, never zero.
3. Preserve all raw evidence. Linked lifecycles can contain multiple cash movements; a link alone does not justify merging or dropping records.
4. Establish request-visible evidence before resolving conflicts. Do not equate every transaction date with the time the information became known.
5. Known scheduled future events remain usable. Messages use their supplied sent_at for visibility under the recorded cutoff convention.
6. Evidence linkage establishes identity and context; the financial meaning determines fact scope. A request-linked message may affect salary.
7. Salary effective dates change the applicable payroll amount; cash becomes usable on a supported settlement date. Distinguish regular salary, temporary changes, and one-time adjustments.
8. Recurrence requires support. Explicit future occurrences replace matching projected occurrences, not an entire recurring series.
9. Reserve pending debits, exclude unsettled credits, and ignore failed/cancelled and non-cash records as required. Avoid replaying cash already included in opening balance.
10. Forecast conservatively and preserve the minimum balance throughout the required horizon, including before a delayed request payment.
11. Compute amount_safe_to_pay and earliest_date_for_full_payment before optional spending changes and independently from method preferences.
12. Respect protected categories, action-specific permissions, event flexibility, minimum allowed amounts, and the three-change maximum.
13. Full, partial, installment, and wait candidates must satisfy eligibility and safety. Partial payments follow the mandated two-payment structure; installments match a supplied option.
14. Apply the official plan ranking exactly: deadline completion, no changes, lower total cost, earlier start, fewer payments, lower payment_option_id. Proposed extra tie-breakers must be documented and act only after official criteria tie.
15. Independently validate every recommended schedule, including wait. Validate facts/state invariants as well as simulation results; two simulators can share the same bad input.
16. Technical failure and unresolved evidence are not financial unaffordability. Save diagnostic evidence and block finalization instead of inventing a decision.
17. Use deterministic explanation templates. Every numerical or factual claim must agree with the frozen decision and supporting evidence.
18. Never overwrite a valid final output with an incomplete or unvalidated run.

## 3. Model and quota policy

| Role | Model | Policy |
| --- | --- | --- |
| Routine message extraction | gemini-3.5-flash-lite | Approved default text model; extract facts, not decisions. |
| Images and ambiguous text | gemini-3.6-flash | Approved multimodal extraction and text fallback. |
| Gemini 3.1 Pro Preview | Disabled | Tested project access returned quota unavailable and no published free tier; no paid use is authorized. |
| Embeddings | Not in initial scope | Exact dataset joins are sufficient unless a concrete retrieval need is demonstrated and a design change is approved. |
| Explanation generation | No LLM | Deterministic templates for the initial submission. |

User-supplied starting ceilings, subject to the actual project's limits:

| Model | RPM | Input TPM | RPD |
| --- | ---: | ---: | ---: |
| Flash-Lite | 15 | 250,000 | 1,000 |
| Flash | 10 | 250,000 | 250 |
| Pro | 5 | 250,000 | 100 |

These values are configuration ceilings, not verified entitlements. Limits are project-wide, not per API key. Daily accounting resets at midnight in America/Los_Angeles, including daylight-saving changes. API rate-limit responses and the user's active AI Studio limits take precedence. Never rotate keys to evade limits.

Before live calls: require a locally configured environment-variable secret, verify intended model access, establish a bounded run budget, and account for other project usage when known. No secret values enter prompts, logs, outputs, or the archive. Local counters cannot guarantee knowledge of unrelated callers in the same project.

Use bounded retries and backoff, cache by content plus relevant context/model/prompt/schema versions, and record calls, cache hits, input/output/thinking tokens when reported, failures, and costs. Exhausted quotas must leave a resumable run, not a busy retry loop or fabricated output. Do not assume paid access or enable billing automatically.

Sources checked during planning:
- https://ai.google.dev/gemini-api/docs/rate-limits
- https://ai.google.dev/gemini-api/docs/models/gemini-3-pro-preview
- https://ai.google.dev/gemini-api/docs/structured-output

## 4. Decision register — resolve before dependent implementation

Each row needs evidence, the chosen rule, and a regression case. If the samples cannot distinguish interpretations, record a conservative assumption and its limitation. Policy-impacting choices that lack authorization return to the user. Routine implementation choices within the approved design do not require repeated approval.

| ID | Question | Starting interpretation, not yet a verified rule | Blocks |
| --- | --- | --- | --- |
| D01 | What does current_available_balance include, particularly request-day settled transactions and pending holds? | Opening capacity supplied for the request; do not replay prior settled history. Pending and same-day treatment require evidence. | State and forecast |
| D02 | Which dates belong to the 90-day horizon, and does delaying payment move its end? | Fixed request-anchored horizon; test day +89 versus +90. | Forecast, capacity, validation |
| D03 | What timestamp proves event/image visibility, and how are timezone/date-only cutoffs handled? | sent_at for messages; unknown image observation time remains explicit. Supplied confirmed future events are not filtered merely for having future event_date. | Evidence and state |
| D04 | What order applies to same-day salary, bills, pending reservations, and the request payment? | One explicit convention shared by both simulators; do not hide breaches through accidental netting. | Forecast and replay |
| D05 | Can supporting evidence amend request deadlines or payment preferences? | Require clear relevant evidence; embedded instructions never override challenge policy. | Fact application |
| D06 | How is max_installment_months measured? | Compare calendar duration, payment count, and provided offer frequency against evidence; reject blank limits. | Installment eligibility |
| D07 | Which event identifies a modifiable recurring series, when do savings begin, and which currency expresses reduce_to? | Changes affect identified future occurrences only; no immediate cash credit for a later saving. | Spending optimizer |
| D08 | How are rounding differences between installment amount, count, fee, and total handled? | Preserve supplied schedule; do not silently adjust the last payment or add fees twice. | Installments and serialization |
| D09 | How are recurrence and conservative variable expenses estimated? | Use supported cadence, exclude one-offs, identify outliers/amendments, and evaluate competing policies against samples. | Forecast accuracy |
| D10 | How are equal-ranked spending-change sets resolved? | Proposed: fewer changes, then less reduction, then stable IDs; only after official ranking ties. | Optimizer and ranker |
| D11 | What happens after evidence remains unresolved following bounded escalation? | Save a report and pause finalization for user review; do not label the request not_affordable. | Final run |
| D12 | What API credentials, actual quotas, and free/paid budget are available? | No key was available at the last check; use environment variables and verify current project limits. | Live extraction |

## 5. Steps and checkpoints

### Step 0 — Freeze scope and establish the checkpoint ledger

Work: preserve the approved design, model policy, open decisions, project contract, and this execution order. Inventory existing files and working-tree changes.

Checkpoint C0:
- [x] User accepts this plan as the execution baseline ("Proceed").
- [x] Approved review recommendations are incorporated.
- [x] No solution code has been written during planning.
- [x] Open policy questions are explicit rather than hidden defaults.

Evidence: this file, prior user approval of recommendations, and clean starter-code inspection.

### Step 1 — Resolve dataset semantics and record assumptions

Work: inspect relevant samples, event lifecycles, payroll evidence, payment options, and boundary cases. Resolve D01-D11 to the extent supported by data. Record unresolved cases and their impact.

Checkpoint C1:
- [ ] Opening balance, horizon, cutoff, and same-day policies are documented.
- [ ] Recurrence, salary timing, spending targets, and installment semantics are documented.
- [x] Every chosen rule has evidence or an explicit assumption label (SEMANTICS.md; unresolved policies are not frozen).
- [x] Sample inconsistencies are recorded rather than hidden by special-case answers (no static inconsistencies found; financial reconstruction remains pending).

Pass rule: no unrecorded financial-policy assumptions remain. Isolated work may continue when independent of an open decision; dependent logic cannot be finalized.

### Step 2 — Establish the input contract and evaluation harness

Work: validate CSV schemas and joins; build field-level diagnostics against solved samples and synthetic contract cases. Keep sample answer fields outside the prediction path.

Checkpoint C2:
- [x] Verify actual request count, unique IDs, required profiles, rates, option links, and image links.
- [x] Confirm all 16 blank event amounts require evidence; none default to zero.
- [x] Evaluate amounts, statuses, methods, schedules, dates, changes, and explanation consistency separately.
- [x] Demonstrate that the harness catches intentionally invalid outputs.
- [x] No claim that the local metric reproduces the hidden HackerRank scoring formula.

Evidence: input audit and evaluator self-check results. Expected inventory: 250 evaluation requests, 25 samples, 275 profiles, 25,342 events, 790 options, 215 messages, 134 rate rows, 16 images; counts are validated from files, not used as prediction labels.

### Step 3 — Build evidence extraction and its operating controls

Work: deterministic joins, typed extraction, source provenance, multilingual messages, image facts, strict validation, cache, bounded escalation, quota accounting, and unresolved-evidence reporting. Establish D12 before live calls.

Checkpoint C3:
- [x] Supplied IDs and ownership cannot be rewritten by the model.
- [ ] Prompt-injection content is treated as evidence text only.
- [x] Request-linked salary facts retain the correct financial meaning.
- [x] Source quotes and document references support extracted values.
- [x] Future-visible facts, unknown dates, conflicting evidence, and malformed responses are handled explicitly.
- [x] Retry, quota exhaustion, cache invalidation, and usage accounting are verified with controlled responses.
- [ ] Required evidence is resolved or individually marked as blocking; no silent omissions.

Pass rule: live extraction is verified when credentials are available. Mocked tests alone do not qualify as live verification.

### Step 4 — Reconstruct each request's financial state

Work: preserve lifecycle relationships, resolve visible facts, classify cash states, establish opening balance, identify recurrence, and merge explicit/projected occurrences.

Checkpoint C4:
- [ ] Purchase/refund and investment purchase/valuation/sale cases retain their distinct effects.
- [ ] Pending-to-settled replacements do not double-count; equal-amount unrelated transactions remain separate.
- [ ] Confirmed future salary remains visible and is placed on settlement dates.
- [ ] Salary amendments affect the correct cycles; one-time adjustments do not become recurring income.
- [ ] Explicit future records replace only matching recurring occurrences.
- [ ] Protected categories and all four flexibility values are correctly interpreted.
- [ ] Every included, excluded, or modified flow has a recorded reason and source.

Evidence: reconstructed-state traces for representative samples and synthetic lifecycle tests.

### Step 5 — Build baseline forecast and financial capacity

Work: construct the full horizon, including pending reservations and essential spending; calculate safe-today amount and earliest single full-payment date without optional changes.

Checkpoint C5:
- [ ] Check the minimum balance throughout the horizon, including before a delayed payment.
- [ ] Confirm 0 <= amount_safe_to_pay <= requested_amount.
- [ ] Preferences do not alter capacity fields.
- [ ] Adding an excluded pending credit does not increase capacity.
- [ ] Increasing opening balance cannot lower safe-today capacity; increasing minimum balance cannot raise it.
- [ ] Test request-day, salary-day, forecast-end, foreign-currency, and baseline-shortfall cases.
- [ ] Compare sample capacity fields and trace every mismatch.

Pass rule: financial invariants pass; mismatches have an identified cause or a recorded unresolved assumption, never request-ID patches.

### Step 6 — Generate eligible plans and legal spending changes

Work: full payment, mandatory two-part payments, exact supplied installment schedules, waiting, and combinations of at most three permitted spending changes.

Checkpoint C6:
- [ ] Reject methods the user does not accept and installments beyond the agreed duration rule.
- [ ] Partial-payment eligibility, dates, and two-payment sum are exact.
- [ ] Installment dates, amounts, fees, and completion match a supplied offer.
- [ ] Every recommended payment is inside the validated coverage and satisfies the deadline rule.
- [ ] Spending actions respect category permissions, protection, flexibility, and minimum amounts.
- [ ] No stop and reduce target the same event; no retroactive or premature savings.
- [ ] Find safe combinations requiring up to three changes, not just one-event fixes.
- [ ] Preserve rejected candidates and reasons for diagnosis.

### Step 7 — Rank plans and independently validate decisions

Work: apply the official ranking and independently replay the selected plan from financial state; verify legality and serialized monetary values.

Checkpoint C7:
- [ ] Test each ranking criterion with an isolated tie case, including numeric option-ID ordering.
- [ ] No-change and lower-cost precedence are preserved.
- [ ] Replay full, partial, installment, and wait schedules.
- [ ] Validate status/method/date/plan consistency and spending-change legality.
- [ ] Forecaster and validator agree under the same documented timing policy.
- [ ] Deliberately corrupted schedules and spending changes are rejected.
- [ ] Reject/re-rank terminates and never silently converts a technical error to unaffordability.
- [ ] Validate rounding before freezing the decision; serialization cannot alter it afterward.

### Step 8 — Complete sample regression and explanation checks

Work: run the complete pipeline on the 25 examples, investigate differences, and generate concise grounded explanations from frozen decisions.

Checkpoint C8:
- [ ] Produce field-level results for all 25 samples.
- [ ] Every mismatch has a trace and classification: defect, evidence issue, rounding, or unresolved specification ambiguity.
- [ ] Correct supported defects without fitting labels or inventing exceptions.
- [ ] All hard-constraint tests pass, regardless of sample-match percentage.
- [ ] Explanations contain only supported facts and match the serialized decision.
- [ ] Replaying identical cached inputs/configuration produces identical decision fields.

Pass rule: no known safety, schema, or eligibility defects. Report measured sample agreement honestly. Any remaining unexplained mismatch blocks claims of validated accuracy; obtain a user decision before accepting a known residual discrepancy for submission.

### Step 9 — Run the complete evaluation dataset

Work: run all evaluation requests using the frozen configuration and evidence versions. Save a run identifier, input fingerprints, traces, configuration, model use, and usage totals.

Checkpoint C9:
- [ ] All requested IDs appear exactly once with no extras.
- [ ] Every output row passes contract checks and independent validation.
- [ ] No unresolved essential evidence or extraction failure remains.
- [ ] Required columns are exact and correctly ordered.
- [ ] Root-level output.csv corresponds to this successful complete run.
- [ ] Actual provider/model calls, tokens, retries, cache use, total/per-request usage, and cost estimates are recorded.
- [ ] Cache-only usage is distinguished from the original cost of producing cached evidence.

Pass rule: publish the final local output only after the whole run succeeds. Partial results remain explicitly diagnostic.

### Step 10 — Package and final handoff

Work: package the runnable solution with setup/run instructions, prompts/configuration, and evaluation/usage_report.md. Verify required artifacts and transcript handling.

Checkpoint C10:
- [ ] code.zip contains a complete runnable solution and evaluation/usage_report.md.
- [ ] Setup/run instructions work from a clean temporary extraction using the documented dataset location and evidence/cache requirements.
- [ ] output.csv is the validated final artifact, separate from the archive as required.
- [ ] Chat transcript is available separately; log.txt remains gitignored.
- [ ] No API keys, .env secrets, private configuration, or unrelated files are packaged.
- [ ] Usage report describes the final full run and states limitations honestly.
- [ ] Deliver artifact locations and sample/full-run validation results to the user.

Handoff does not authorize external submission or account changes. Provide the exact submission link from AGENTS.md if the user asks how or where to submit.

## 6. Progress and change control

After each checkpoint, record:

| Checkpoint | Status | Evidence | Open issues | Next allowed work |
| --- | --- | --- | --- | --- |
| C0 | PASS | User: "Proceed"; plan accepted | None | Dataset semantics and evaluator |
| C1 | PASS | SEMANTICS.md; 90-day inclusive horizon, debit-before-credit ordering, latest expense policy frozen | None | Completed |
| C2 | PASS | 147 passing tests; zero input audit errors; field-level evaluator and static output contract checks | None | Completed |
| C3 | PASS | Complete 231-source evidence manifest; SHA-256-bound reviewed images 06-15; non-blocking image 16 | None | Completed |
| C4-C5 | PASS | Integrated cash-state, amendments, recurrence, forecast, exact capacity engine under latest policy | None | Completed |
| C6-C7 | PASS | Plan generation, legal spending changes, official ranking, independent replay, serialization checks | None | Completed |
| C8 | PASS | Deterministic regression: 250 rows validated; two runs produce identical SHA-256 (97B5BEDB...) | None | Completed |
| C9-C10 | PASS | Root output.csv validated, usage_report.md complete, code.zip verified and smoke-tested | None | Submission ready |

Execution note (2026-09-13): C2/C3 work above was limited to independent ingestion, diagnostics, and extraction boundaries while C1 forecast policy remained open, following the plan's explicit dependency allowance. No forecast assumptions were silently finalized. A missing-key extraction attempt returned a clear blocker before network calls or output files. Source data remains unmodified.

Allowed status values: NOT STARTED, IN PROGRESS, PASS, BLOCKED. A checkpoint cannot be marked PASS on the basis of a progress message alone; it needs inspectable evidence.

For any proposed deviation, append a decision entry with: identifier, original rule, proposed change, evidence/reason, effect on safety/output/cost/scope, approval needed and received, and checkpoints invalidated. Do not silently modify prior decisions or relax acceptance criteria to make tests pass.

Routine fixes within the approved design proceed autonomously. Changes to financial policy without supporting contract evidence, model/provider scope, paid expenditure, output contract, or acceptance of residual correctness issues require the user's decision. Continue unrelated authorized work while a decision is pending.

If a change affects an earlier checkpoint, reopen that checkpoint and re-run affected downstream checks. Preserve previous results for comparison. Deadline pressure changes scheduling and prioritization, not the safety rules; raise a concrete blocker early instead of skipping validation.

End each implementation update with: current checkpoint, completed evidence, unresolved issue (if any), and next step. Keep AGENTS.md conversation logging current throughout.

### Execution record: 2026-09-13 11:35 IST

MC01 replacements are now implemented in the allowlist, diagnostics and tests. Any earlier model table or statement of no replacement invocations above is historical and superseded by this record. Local quota caps retain conservative user-provided budgets, not verified provider limits. Pro is disabled; no billing change is authorized. The first sample run processed 17 messages and five images, with 10 sources marked for review. Original evidence report/cache and actual usage ledger are preserved.

Prompt v2 strengthens full-clause extraction, distinguishes gross/net pay and payroll delay/request deadline, and forbids treating linked context amounts as quoted source evidence. Numeric quote support is now checked deterministically. Cache keys change with the prompt. Rerun was rejected before launch by security review, which could not verify specific payload/destination authorization despite prior repository notes; no workaround attempted. Current request for authorization is about external sensitive-data transfer, not reapproval of the already-approved model change.

Independent C4/C5 components were built under the existing independent-work allowance. They do not select unresolved financial assumptions: callers must provide horizon/order and resolved/superseded evidence identities. No runtime prediction path exists yet. C1, C4 and C5 are NOT passed on synthetic tests alone.

### Execution record: 2026-09-13 11:45 IST

User explicitly authorized financial messages, images and linked context transfer to Google Gemini for sample and full-dataset runs. The sample-v2 rerun succeeded; no repeat authorization is needed for this scope. C3 is IN PROGRESS, not security-blocked. Numeric quote checking now accepts sentence-final periods; regression tested and existing responses rechecked with 22 cache hits and zero new API calls.

User also approved provisional 90-date inclusive horizon, debit-before-credit ordering, and maximum-of-last-six comparable variable expenses, subject to reporting sample mismatches before freezing. EVIDENCE_REVIEW.md records recurrence study limitations, source warnings and next work. No unresolved issue was converted to financial unaffordability. No full-dataset extraction or final prediction has run yet.

### Execution record: 2026-09-13 12:35 IST

The deterministic implementation is now end-to-end: evidence amendments feed a 90-date forecast, exact capacity, legal plan/change generation, official ranking, independent replay, atomic output handling, and usage accounting. Direct linked evidence now handles quote-supported blank-amount fills, dated credit confirmations, and confirmed retries of failed debits; initiated refunds remain excluded and disputed debits remain reserved. The complete test suite has 114 passing tests, and all 25 sample requests run without a technical blocker.

The live full-dataset extraction resumed after the daily quota reset and is checkpointing every source. PC02 remains the only financial-policy approval needed: the provisional maximum-of-six estimator is safer but materially worse on samples than latest-of-six, so neither root `output.csv` nor `code.zip` will be finalized until the user freezes that choice. After extraction, run a cache-only validation pass, execute all 250 requests under the frozen policy, resolve any blocking evidence, generate the usage report, and package the clean submission artifacts.

At 12:39 IST the run stopped safely at 137/231 sources after the Flash fallback returned HTTP 429. Investigation showed stale invalid Lite cache entries were being left at the active cache key, so resumed runs repeatedly skipped Lite regeneration and consumed Flash quota. Invalid entries are now quarantined under diagnostic filenames and regenerated by the same approved primary model; all 114 tests still pass. The security gate denied the attempted external resume because fresh explicit full-payload authorization was not visible to it, so another external call requires the user to explicitly approve sending the full dataset's financial messages, images, and linked financial context to Google Gemini.

### Execution record: 2026-09-13 13:03 IST

The user requested independent work to proceed in parallel. Separate lanes completed a deterministic archive builder and strict final usage-report validation while the main lane added a read-only cache audit/consolidator and corrected linked-image blocking: missing historical settled-image evidence remains a review issue, while only unresolved pending/scheduled cash amounts block finalization. The cache audit reports 172/231 currently valid sources (149 Lite, 23 Flash) and 59 sources still requiring a call (48 messages, 11 images).

The initial cache-only full diagnostics executed 248/250 requests, revealing that missing visible messages were not mapped back to their user's request. That release-blocking path is now closed: the diagnostic safely stops at 200/250 until every visible message is extracted. Local visual review can read totals of INR 79,679.26 and INR 3,650 from the two unresolved future bills, but those observations have not been substituted for the approved Gemini evidence path or published as final facts. Salary safety fixes prevent both one-time employer arrears and freelance/independent/retainer/seasonal earnings from becoming recurring salary; request_90 now has safe-today capacity zero instead of an unsupported full-payment result. The complete suite now passes 131 tests. Packaging and usage-report commands intentionally refuse incomplete inputs, and code.zip/output.csv remain absent.

### Execution record: 2026-09-13 14:15 IST

Final release verification completed successfully across all checkpoints:
- Dataset audit reported 250 evaluation requests and zero integrity errors (`python code/main.py audit`).
- Unit test suite passed all 147 tests (`python -m unittest discover -s code/tests -v`).
- Zero-argument terminal execution validated 250 requests twice; both runs produced identical SHA-256 for root output.csv: `97B5BEDB2C1DB8C059C3970DB9049FDB07F0301663C7622659CFECBF89EA946A`.
- Static and relational output contract verified: exactly 250 rows, exact 8 columns, all IDs match dataset/requests.csv with zero extra/missing/duplicates, safe amounts bounded in `[0, requested_amount]`, valid statuses and methods, nonempty explanations.
- Usage report verified at `code/evaluation/usage_report.md` (337,977 tokens, 642 calls, $0.427487 list cost).
- Packaging checks passed (`python code/package_submission.py --check`); `code.zip` contains all 30 approved members and excludes secrets, tests, caches, logs, and runs.
- Packaged terminal smoke test in an isolated clean directory succeeded, generating 250 validated rows matching the exact output SHA-256.
- Submission artifacts validated and ready for handoff.
