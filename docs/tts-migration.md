# TTS migration plan (note only, nothing switched)

Today the voice uses `gemini-2.5-flash-preview-tts` (voice Sadachbia, one request, "[DELIVERY ONLY, DO NOT SPEAK: ...]" per line). Per Google's deprecation notice relayed by the reviewer, this preview model is scheduled to shut down on 2026-12-18. Verify that date on https://ai.google.dev/gemini-api/docs/deprecations before acting.

Plan:
1. Keep the default as it is until about 2026-12-01. Do not switch now.
2. A newer path already exists in code, off by default (`GEMINI_TTS_MODEL=interactions`). Before the deadline, run ONE test render with it from the manual workflow and compare by ear against the current voice: same Nepali pronunciations (assets/voice/pronunciations.json), no spoken direction text, same length within 10 percent.
3. If it passes, change the default model name in scripts/gemini.py only (one constant), update this note, and keep the old name as an env override until it stops working.
4. If it fails, the voice stays on the last working model; do not mix voices inside one reel; ask the owner.
5. The failure mode on shutdown is a Gemini 404/400 from the TTS call. The run stops (exit 5), no retry, no other voice is used.
