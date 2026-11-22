# Voice director (Gemini TTS emotion rule)

The brain picks the emotion for EVERY script line itself. One Gemini TTS request per reel, one turn per line, each turn carries its own `speech_metadata.style`.

Rules:
- Choose each line's emotion from `assets/voice/styles.json` (it lists every emotion and delivery style we support: joy, sadness, fear, anger, calm, hope, awe, humor, drama, whisper, shout, pace and volume styles). Add new ones there, not in code.
- Read the whole script first and design an arc: a strong hook (curious, surprised, urgent, excited), a clear middle (conversational, thoughtful, confident), a warm payoff (hopeful, encouraging, proud). Never use one emotion for every line. Use contrast on purpose: a short whisper or a pause before the key fact.
- Match the emotion to the meaning of the sentence. Sad or worried only when the line is about a problem. Never make a serious fact sound jokey. Never fake certainty.
- Pace and volume go in the style string ("speaking slowly", "speaking rapidly", "softer"). Pauses use `<short pause>` / `<long pause>` inside the text, sparingly. Emphasis: capitalise Latin words only, Devanagari has no case, so rely on punctuation and a short pause.
- Keep style strings short English. The transcript stays verbatim Nepali in Devanagari. English terms are respelled in Devanagari first (assets/voice/pronunciations.json plus the script's own list), so the voice says them the Nepali way.
- Voice name is a brand choice (default Sadachbia), not picked per reel. Do not put age, gender or accent changes in the style.
- Free tier only. A 429 or any error stops the run. No retries.
