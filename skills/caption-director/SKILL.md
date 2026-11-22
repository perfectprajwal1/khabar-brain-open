# Caption director (implemented in scripts/compose_split.py)

- One line at a time, centred on the seam between the top demo and the face, 1080x1920 frame.
- Font: Noto Sans Devanagari Bold, 92 px, white with a thick black outline. The current spoken word is red.
- Words are grouped into chunks that fit one line (max width 990 px). Never wrap to two lines.
- The top panel carries no caption text. Never duplicate the caption in the demo.
- Timings: real word times when available. Today they are ESTIMATED (speech span from silence detection, line boundaries snapped to the longest pauses, words split by letter count). Say so in every report until real alignment exists.
- Popup icons (max 4, from `assets/icons.json`) appear top-right of the top panel for the span of their line, at most 2.5 seconds.
- Caption text is the spoken text (after pronunciation fixes), so what is heard matches what is read.
