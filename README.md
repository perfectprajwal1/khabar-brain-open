# Khabar Brain (open review copy)

Code that makes short Nepali (Devanagari) explainer reels about useful digital skills. One manual GitHub Actions trigger runs: topic from a curated source pack of official pages, claims quoted from those pages, Nepali script, humanizer, hook score, popup icons, validator, Gemini voice with an emotion per line, a Playwright screen capture with auto-zoom for the top half, a lip-sync face for the bottom half (Kaggle free GPU, one job at a time), and a join with a red-word caption on the seam. It makes a DRAFT for a human to review. It never posts and has no schedule. Free tiers only, no cards.

This is a clean review copy with a single commit. Not included: the face photo, voice samples, any API keys, and the video renderer and brand art from another private project. The workflows therefore will not run as-is: they expect `assets/face/photo.jpg` (not published) and secrets `GEMINI_API_KEY`, `GROQ_API_KEY`, `KAGGLE_API_TOKEN`. Set `KAGGLE_KERNEL_SLUG` for your own Kaggle notebook.

Map
- `scripts/brain.py` the brain steps. `scripts/llm.py` provider layer (Gemini writer, Groq reviewer, failover rules). `scripts/gemini.py` Gemini client and TTS. `validator/validate_draft.py` the evidence and format gate.
- `skills/` the rule text for each brain role. `assets/` source pack, emotion list, pronunciations, popup icons.
- `scripts/compose_split.py` the join and captions. `scripts/capture_demo.py` screen capture. `scripts/kaggle_lipsync.py` and `kaggle/` the GPU step.
- `.github/workflows/` the draft-reel workflow (main), a collect workflow, a demo-panel test.

No project license is assigned yet. All rights reserved until the owner decides. The caption font (Noto Sans Devanagari Bold, SIL OFL) is not included: put it at `assets/fonts/NotoSansDevanagari-Bold.ttf`.
