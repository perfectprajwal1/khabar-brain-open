# Validator

`validate_draft.py` is a deterministic gate. It fails closed: any error rejects the draft.

Checks: 2 to 5 claims, each with quotes from 2 different publishers, every quote found verbatim in the fetched page text; no news/politics/sports keywords; 4 to 7 script lines, 30 to 75 words, Devanagari only; every body line cites known claim ids; emotions and popup icons come from the allowed lists; hook score at least 7 and not flagged misleading; hook at most 14 words.

Known gap: it proves a quote exists, not that the quote supports the claim, and it cannot judge truth. A human reviews every draft.
