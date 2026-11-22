# Brain skills

Each file is the rule text the brain feeds to its model for one role. The brain picks topic, emotion per line, popup icons and checks the hook automatically; humans only review the finished draft.

| Role | Skill | Used by |
| --- | --- | --- |
| Topic pick | topic-picker | brain.py step 1 (source pack rotation or override) |
| Research ledger | source-ledger | brain.py step 1 (quotes from fetched pages) |
| Script writer | script-writer, nepali-editor | step 2 |
| Humanizer | humanizer | step 3 |
| Hook scorer | hook-scorer | step 4 and validator gate |
| Popup director | icon-motion | step 5 |
| Voice director (emotion per line) | voice-director | step 2 picks, step 7 speaks |
| Gemini TTS (voice, tones, pronunciation, limits) | gemini-tts | step 7, scripts/gemini.py |
| Caption director | caption-director | scripts/compose_split.py |
| trend-scout | trend-scout | not used while topics come from the source pack |

Quality bar: the rules here come from the project plan and an earlier working voice setup (tone wording, caption style). No outside prompt text was copied.
