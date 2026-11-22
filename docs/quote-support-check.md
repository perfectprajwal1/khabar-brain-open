# Quote-supports-claim check (design, not built)

Problem: validator/validate_draft.py proves a quote exists in the fetched page, not that it supports the claim.

Design, in two layers, both free:
1. Deterministic filter (no model): the claim's key terms must appear in the quote. Extract numbers, units and nouns from the claim; require every number to appear in the quote verbatim, and at least 60 percent of the content words (after stop-word removal) to overlap. Reject quotes that fail. Catches "at least 12" vs "longer than 12" drift and off-topic quotes.
2. Reviewer pass (one request on the REVIEWER provider, never the writer): give claim + quote only, ask "does the quote directly state the claim? yes / partly / no" as JSON. Any "no" or "partly" fails the draft. Counts as one extra text request per claim, batched in a single call for all claims.
Limits: layer 2 is a model opinion, so it lowers risk, not removes it. A human still reads every draft. Needs a second authoritative non-Wikipedia source per claim (source pack work) to be meaningful.
Failure handling: same provider rules as the rest of the brain (no retry, no mixing mid-run).
