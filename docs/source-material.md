# Source material — provenance

The strategy this repo tests originates from two Zoom training recordings,
not from any document written for this project. Every rule in
`sports_betting_process.md` traces back to one of these two recordings, and
every citation in this repo's code/docs (e.g. "P1 40:17", "P2 19:48") points
to a `[mm:ss]` timestamp in the corresponding transcript below.

## Recordings

Both are "Line Reading Training" sessions for the "Go Sports" sports-betting
community, presented by Kendrick Smith ("Ken the Millionaire", IG:
@kenthemillionaire). Stored in the Google Drive **PANTHERA** project folder
(`Consulting Biz/Projects/PANTHERA/`), inside
`wetransfer_gmt20240627-021203_recording_1760x900-mp4_2024-08-08_2106/`.

| Label | File | Date | Length | Content |
|---|---|---|---|---|
| **P1** | `notes/GMT20240619-014815/` (video: `GMT20240619-014815_Recording_1760x900.mp4`) | June 18, 2024 | ~1h 56m | Foundational training: the weekly public/Vegas/hybrid schedule framework, MLB basics, line-movement rules, the "skeleton" pre-pick checklist, 7 worked examples (Red Sox/Blue Jays, Nationals/Marlins, Athletics/Twins, Tigers/Nationals, Cubs/Rays, Phillies/Brewers, Athletics/Royals) plus two over/under examples, extended Q&A, and a live real-time schedule walkthrough. |
| **P2** | `notes/GMT20240627-021203/` (video: `GMT20240627-021203_Recording_1760x900.mp4`) | June 26, 2024 | ~44m | Follow-up session: a day-by-day play-policy technique (Tue = totals primary, Thu/Sat = off days, Wed = public-first-half-only), with new examples (Guardians/Orioles, Pirates/Reds, Nationals/Tigers, Reds/Dodgers), Q&A, and a paper-betting check-in. |

Each recording's folder also contains `notes.md` (human-written synthesis,
not a raw transcript dump), `transcript.txt`/`transcript.srt` (full
timestamped transcript — the actual source of truth), and `screenshots/`
(frames sampled at 5-minute intervals). See each folder's own header for how
the transcripts/screenshots were generated (Whisper via Together.ai;
PySceneDetect).

Two other files sit alongside the recordings folder in the PANTHERA
directory: `PROJECT PANTHERA.docx` (the older SaaS-era product spec — not a
strategy source; see this repo's top-level `CLAUDE.md` on the frozen
`backend/`/`frontend/` scaffold) and three `retool_dashboard_layout*.json`
files (also SaaS-era, not used here).

## What changed because of this material (2026-08-19)

Before this analysis, `docs/sports_betting_process.md` was a bullet-point
outline apparently written from memory or a quick read, not the transcripts.
It was lossy enough that the implemented engine (`strategy/rules.py`) ended
up testing a different, in places inverted, strategy — see
`docs/mvp-design.md`'s "Alignment with the source recordings" section for
the full discrepancy list and its measured live impact (`pv_v2`/`pv_v3` at
−15.6%/−29.9% ROI). `sports_betting_process.md` was rewritten as a faithful,
timestamp-cited transcription of P1/P2; the aligned engine is
`strategy/orig_rules.py` / strategy id `pv_orig`.

## Citation convention

`P1 mm:ss` / `P2 mm:ss` refer to that recording's `[mm:ss]` transcript
timestamp. A range (e.g. `P1 40:17-41:24`) covers a continuous passage.
Direct quotes are lightly cleaned of filler words and false starts but
otherwise verbatim; anything paraphrased is marked as such.
