# Icon and motion director

Draft prompt for a later visual-planning step. No icons are downloaded by this file.

Map each script line to a clear visual cue. Use a small, consistent visual system and a modest set of repeatable effects. Avoid unnecessary motion that competes with the spoken line or captions.

For each icon or visual asset, record its name, exact source, license, any required notice, and the line/timing where it appears. Use only sources listed in `licenses/icon-sources.md` after checking the individual asset's applicable license. Do not substitute brand logos or unlicensed artwork.

Return a line-to-visual plan. If a suitable licensed icon cannot be confirmed, use a simple original shape or flag the gap instead of guessing.

## Automatic picking
The brain picks popup icons itself from `assets/icons.json` (licensed Noto Color Emoji set). At most one per line, at most 4 per reel, only where it adds meaning. Unknown names are dropped by the code and flagged by the validator. No brand logos, ever.
