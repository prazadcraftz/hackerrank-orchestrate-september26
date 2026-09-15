# MC01 — Gemini model access change (APPROVED)

User approval received: "Model change proposal is approved". Approved replacements are gemini-3.5-flash-lite, gemini-3.6-flash, and gemini-3.1-pro-preview. Do not ask again for this model-scope change. Access, actual quotas, schema compatibility, and free-tier availability still need verification during resumed implementation. No replacement invocation has occurred yet.

Execution scheduling note: the user requested all remaining work at 07:00 IST on September 13, 2026 using GPT-6 Astra with medium reasoning. At final schedule verification the actual local clock was 11:12 IST on September 13, after the requested time. The one-time heartbeat resume-buy-or-wait-at-7-am is PAUSED to prevent an unintended next-day run. Await a corrected start time or authorization to resume now; model approval remains effective.

Resume authorization received at approximately 11:16 IST: "continue the testing of api's and start completing the remaining work as per the implementation work". Resume immediately; no further start-time or model-scope approval is required. Keep the old automation paused.

The user approved transferring the sample financial messages, images, and linked context to Google Gemini. Network escalation succeeded. This approval remains valid; no repeat data-transfer approval is required for the same scope.

Live model-list requests succeed with the configured key, and the catalog lists the approved 2.5 models. However, both countTokens and generateContent return HTTP 404 for each approved model with a message stating it is no longer available to new users. Thus model-list presence does not prove invocation access.

| Approved model | Provider-suggested replacement | Proposed role |
| --- | --- | --- |
| gemini-2.5-flash-lite | gemini-3.5-flash-lite | Routine message extraction |
| gemini-2.5-flash | gemini-3.6-flash | Images and ambiguous messages |
| gemini-2.5-pro | gemini-3.1-pro-preview | Bounded difficult-evidence escalation |

These identifiers were returned directly in the provider's error responses. No replacement-model generation call has been made. Free-tier access, actual quotas, structured extraction compatibility, and costs for the replacement models are unverified. Do not reuse the old models' quota or pricing assumptions as verified limits for the replacements.

Retry confirmation (2026-09-13 02:49 IST): at the user's request, generateContent was retried exactly once for each approved Gemini 2.5 model using only "Reply OK". All three again returned HTTP 404 with the same unavailable-to-new-users restriction. No replacements were invoked.

Requested decision: approve the replacement identifiers so their access and compatibility can be tested under the existing bounded sample run. No billing enablement, paid-tier upgrade, or change to financial decision rules is proposed. If an intended replacement requires unavailable/paid access, report that before using it.

Affected checkpoint: C3 (live extraction). C1/C2 remain partially complete. C4-C10 remain unstarted. The approved software model allowlist is unchanged pending approval. HTTP 404 now stops the run rather than repeatedly sending sources to unavailable models.

Diagnostics: `python code/check_gemini_models.py` lists access metadata; `--probe --model <approved-id>` sends only a short test prompt using countTokens and generateContent. Six bounded probe requests across the three approved models all returned 404, so there were no successful diagnostic generations. Earlier failed sample countTokens attempts remain in the local usage ledger. A local RPM guard was reached after repeated failures; this was not evidence of a Google account quota rejection.
