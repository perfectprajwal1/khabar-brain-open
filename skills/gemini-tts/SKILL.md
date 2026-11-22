# Gemini TTS (how the brain speaks)

Default path, same as the earlier working project (do not diverge): model `gemini-2.5-flash-preview-tts`, voice `Sadachbia`, `generateContent` with `responseModalities: AUDIO`, one key (GEMINI_API_KEY secret), ONE request per reel.

Prompt shape (scripts/gemini.py `speech_km`): an instruction to read every paragraph verbatim, then for each line `[DELIVERY ONLY, DO NOT SPEAK: <tone sentence>]` followed by the line. One second of silence between paragraphs. km's 12 tone sentences are used word for word; other emotions from `assets/voice/styles.json` use the same wrapper with their style text.

Controls available:
- Voice: default Sadachbia (brand voice). Other prebuilt Gemini voices exist (Zephyr, Puck, Charon, Kore, Fenrir, Leda, Aoede, Sulafat, Sadaltager and more). Change it only on purpose, for all reels.
- Emotion and delivery per line: from styles.json, picked by the brain per line (see voice-director). Pace and volume words live in the style text ("speaking slowly", "softer", "speaking rapidly").
- Pauses: punctuation and ellipses, the one-second gap between lines. `<short pause>` and `<long pause>` tags belong to the newer Gemini 3.x TTS, not used by default.
- Nepali pronunciation: write English terms in Devanagari before TTS (`assets/voice/pronunciations.json` plus the script's own list). The caption shows the same spelling, so voice and caption match.
- Optional newer path: set `GEMINI_TTS_MODEL=interactions` to use Gemini 3.x TTS (`gemini-3.8-flash-lite-tts`, per-turn `speech_metadata.style`). It worked once on the free key. Off by default.

Rules: free tier only. Any 429 or error stops the run. Never retry a request whose outcome is unknown. No Microsoft/Edge voice anywhere (the Edge code was removed from scripts/tts.py). The key is read from the environment, never printed or written to disk.
Known gap: the voice is one audio file, so line and word timings are estimated from pauses and letter counts. They are not real alignments.
