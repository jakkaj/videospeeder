# Workshop: Workflow & CLI Design — VAD First-Pass + Multi-Angle

**Type**: CLI Flow + Integration Pattern
**Plan**: 007-vad-first-pass-multi-angle
**Spec**: (pending)
**Created**: 2026-02-22
**Status**: Draft

**Related Documents**:
- [Research Dossier](../research-dossier.md)
- [006-VAD Implementation Plan](../../006-vad/vad-speech-detection-plan.md)

---

## Purpose

Workshop the end-to-end user experience for the two-pass VAD workflow: detect once, speed many. Nail down the exact CLI surface, file conventions, folder semantics, and output control so a creator can go from "I have 3 camera angles of a recording session" to "all 3 are sped up identically" in as few commands as possible.

## Key Questions Addressed

- What does the real-world multi-angle recording workflow look like?
- How many commands should it take? What's the minimum-friction path?
- How does the sidecar file get created, found, and consumed?
- What does "disable all overlays" mean and how is it controlled?
- What happens when video durations don't match across angles?
- How does output naming work for folder-based processing?

---

## The Vibe

The user is a **content creator recording screencasts or tutorials** with multiple cameras:
- A face cam (main camera, has the best mic audio)
- A screen recording (system audio or silent)
- Maybe an overhead/wide shot

After recording, they have a folder of raw files. They want to:

1. **Detect once** — run VAD on the file with the best audio
2. **Speed all** — apply the same silence map to every angle
3. **Get clean output** — no overlays, no junk, just tighter videos
4. **Stay in sync** — all angles cut identically so they can be layered in an NLE

This is NOT about fancy editing. It's about **bulk preprocessing** before the real edit. The output goes into DaVinci Resolve, Premiere, or Final Cut. The creator wants **raw, clean, synced files**.

---

## Workflow Scenarios

### Scenario 1: Single File (Simplest — Works Today)

```
$ python videospeeder.py -i recording.mp4 -o recording_fast.mp4 --vad
```

Nothing changes here. Detect + process in one shot. Stays backward-compatible.

---

### Scenario 2: Separate VAD Pass, Then Process (New)

**Why?** You want to inspect the VAD results before committing to a long encode. Or you want to tweak processing params without re-running detection.

```
recording_session/
├── facecam.mp4         ← your raw recording
└── (nothing else yet)
```

**Step 1: Detect**

```
$ python videospeeder.py -i recording_session/facecam.mp4 --vad --detect

┌─────────────────────────────────────────────────────────────┐
│ VAD Detection Complete                                      │
│                                                             │
│   Input:    recording_session/facecam.mp4                   │
│   Duration: 3842.5s (1h 4m 2s)                              │
│   Speech:   47m 12s (73.4%)                                 │
│   Silence:  16m 50s (26.6%)                                 │
│   Segments: 142 speech, 141 silence                         │
│                                                             │
│   Wrote: recording_session/facecam.vad.json                 │
└─────────────────────────────────────────────────────────────┘
```

```
recording_session/
├── facecam.mp4
└── facecam.vad.json     ← NEW — sidecar sits next to the video
```

**Step 2: Process (using sidecar)**

```
$ python videospeeder.py -i recording_session/facecam.mp4 \
                         -o output/facecam.mp4 \
                         --vad-json recording_session/facecam.vad.json

[info] Loading VAD metadata from facecam.vad.json (skipping detection)
Processing: 100%|████████████████████████| 3842/3842 [08:23<00:00]
Done. Output: output/facecam.mp4 (47m 18s, saved 16m 44s)
```

**Key design choice:** `--detect` writes the sidecar and exits. `--vad-json <path>` reads a sidecar and skips detection. Both are flags on the same `videospeeder.py` command — no new script files.

**Why not a separate script?** Keeping it as flags on the existing command means one tool, one `--help`, one thing to learn. `vad_dump.py` stays as the diagnostic/debug tool it already is.

---

### Scenario 3: Multi-Angle — The Main Event

**Recording setup:**
```
session_2026-02-20/
├── facecam.mp4          ← main camera, good mic
├── screen.mp4           ← screen capture (may have system audio)
├── overhead.mp4         ← wide shot, no audio
└── broll.mp4            ← cutaway angles
```

**Step 1: Detect on the master audio**

```
$ python videospeeder.py -i session_2026-02-20/facecam.mp4 --vad --detect

  Wrote: session_2026-02-20/facecam.vad.json
```

**Step 2: Speed all angles with the same sidecar**

```
$ python videospeeder.py --folder session_2026-02-20/ \
                         --vad-json session_2026-02-20/facecam.vad.json \
                         -o session_2026-02-20/output/

┌─────────────────────────────────────────────────────────────┐
│ Multi-Angle Batch Processing                                │
│                                                             │
│   VAD source: facecam.vad.json (3842.5s analyzed)           │
│   Videos found: 4                                           │
│                                                             │
│   [1/4] facecam.mp4 .... 3842.5s → output/facecam.mp4      │
│   [2/4] screen.mp4  .... 3842.5s → output/screen.mp4       │
│   [3/4] overhead.mp4 ... 3842.4s → output/overhead.mp4     │
│   [4/4] broll.mp4 ...... 1200.0s → output/broll.mp4        │
│         ⚠ Duration mismatch: video shorter than VAD source  │
│           (1200.0s < 3842.5s) — will process available      │
│           portion only                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Processing starts immediately (no interactive prompt — per spec OQ-3):
```
[1/4] Processing facecam.mp4...
Processing: 100%|████████████████████████| 3842/3842 [08:23<00:00]

[2/4] Processing screen.mp4...
Processing: 100%|████████████████████████| 3842/3842 [06:41<00:00]

[3/4] Processing overhead.mp4...
Processing: 100%|████████████████████████| 3842/3842 [07:12<00:00]

[4/4] Processing broll.mp4...
Processing: 100%|████████████████████████| 1200/1200 [02:45<00:00]

Done. 4 videos processed → session_2026-02-20/output/
```

**Result:**
```
session_2026-02-20/
├── facecam.mp4
├── screen.mp4
├── overhead.mp4
├── broll.mp4
├── facecam.vad.json
└── output/                ← NEW
    ├── facecam.mp4
    ├── screen.mp4
    ├── overhead.mp4
    └── broll.mp4
```

All four output files have **identical timing** — the same segments sped up by the same amounts. Drop them all into a timeline and they're perfectly in sync.

---

### Scenario 4: Quick One-Liner (Power User)

For the user who doesn't want two steps:

```
$ python videospeeder.py --folder session_2026-02-20/ \
                         --vad --vad-master facecam.mp4 \
                         -o session_2026-02-20/output/
```

This detects on `facecam.mp4`, writes the sidecar, then processes all files in one go. `--vad-master` names which file's audio to use for detection.

If `--vad-master` is omitted with `--folder --vad`, it errors:
```
Error: --folder with --vad requires --vad-master to specify which
       file's audio to use for detection.
       Example: --vad-master facecam.mp4
```

---

## Command Reference

### New Flags on `videospeeder.py`

| Flag | Type | Purpose |
|------|------|---------|
| `--detect` | action | Run detection only, write `.vad.json` sidecar, then exit. Requires `--vad`. |
| `--vad-json PATH` | path | Load silence intervals from a `.vad.json` file instead of running detection. Mutually exclusive with `--vad`. |
| `--folder DIR` | path | Process all video files in DIR. Requires `-o` to be a directory. |
| `--vad-master FILE` | filename | When using `--folder --vad`, which file in the folder to run detection on. |
| `--no-stats` | action | Suppress the rich video stats table. |
| `--quiet` | action | Minimal output. No stats, no segment lists, no debug. Just progress bar + done. |
| `--extensions` | string | Comma-separated video extensions for folder scan (default: `mp4,mkv,mov,avi,webm`). |

### Mutually Exclusive Groups

```
Detection source (pick one):
  --vad               Run Silero VAD live on input audio
  --vad-json PATH     Load pre-computed VAD metadata from JSON file
  (default)           Use FFmpeg silencedetect

Detect-only mode:
  --detect            Write sidecar and exit (requires --vad)
                      Cannot be combined with -o / --folder
```

### Flag Compatibility Matrix

| Flag | Single file | --folder | --detect |
|------|-------------|----------|----------|
| `-i` | Required | Ignored (folder provides inputs) | Required |
| `-o` | Required (file) | Required (directory) | Ignored (auto-names sidecar) |
| `--vad` | OK | OK (with --vad-master) | Required |
| `--vad-json` | OK | OK | N/A (conflict) |
| `--indicator` | OK | OK (applied to all) | N/A |
| `--gpu` | OK | OK (applied to all) | N/A |
| `--offset` | OK | OK (applied to all) | OK |
| `--process-duration` | OK | OK (applied to all) | OK |
| `--quiet` | OK | OK | OK |

---

## Overlay & Output Control

### Current State

The only video overlay is `--indicator` which adds a `>> 4x` badge during sped-up segments. It's **opt-in** (off by default). So "clean output" is already the default.

### What "Disable All Overlays" Means

The user wants confidence that the output video has **zero visual modifications** beyond speed changes. This is guaranteed when:
- `--indicator` is NOT passed (default behavior)

No other overlays exist or are planned. The speed adjustment itself doesn't add any visual artifacts — it's pure `setpts` and `atempo` in the FFmpeg filtergraph.

### Terminal Output Control

For scripting and batch processing, noisy terminal output is undesirable:

**Default output (current — very verbose):**
```
Arguments parsed:
  input: facecam.mp4
  output: facecam_fast.mp4
  ...
[DEBUG] Current working directory: /home/jak/session
[DEBUG] Files in cwd: ['facecam.mp4', ...]
[DEBUG] Probing input file: facecam.mp4
┌── Probed Video Information ──┐
│ File:       facecam.mp4      │
│ Duration:   3842.50 sec      │
│ ...                          │
└──────────────────────────────┘
Running FFmpeg silencedetect...
(pages of ffmpeg output)
Parsed silence intervals:
(0.0, 1.5)
(4.2, 7.8)
...
Segments (start, end, type):
(0.0, 0.5, 'non-silent')
...
Generated FFmpeg filtergraph:
(enormous filter string)
Running FFmpeg processing command:
ffmpeg -y -i ...
Processing: 100%|████████████████| 3842/3842
```

**With `--quiet` (proposed):**
```
Processing facecam.mp4: 100%|████████████████| 3842/3842 [08:23<00:00]
Done. output/facecam.mp4 (47m 18s, saved 16m 44s)
```

That's it. Progress bar + summary line. Perfect for batch/folder mode.

**Verbosity levels:**

| Level | Flag | What you see |
|-------|------|-------------|
| Verbose | `--debug-segments` | Everything + per-segment speed details |
| Normal | (default) | Stats table, interval list, filtergraph preview, progress |
| Quiet | `--quiet` | Progress bar + summary only |

**Design choice:** Remove the `[DEBUG]` prints from main() before shipping. They're development artifacts. The `--debug-segments` flag is the proper debug mechanism.

---

## Sidecar File Design

### File Naming Convention

```
<video_stem>.vad.json
```

The sidecar is placed **next to the source video file**, named by stripping the video extension and appending `.vad.json`.

| Video | Sidecar |
|-------|---------|
| `facecam.mp4` | `facecam.vad.json` |
| `my recording.mov` | `my recording.vad.json` |
| `screen.mkv` | `screen.vad.json` |

**Auto-discovery:** When `--folder` is used without `--vad-json`, the tool looks for any `.vad.json` file in the folder. If exactly one exists, it uses it. If multiple exist, it errors with a message to specify `--vad-json`.

### Sidecar Schema (v1)

```json
{
  "version": 1,
  "generator": "videospeeder",
  "generated_at": "2026-02-20T14:30:00Z",

  "source": {
    "file": "facecam.mp4",
    "duration_seconds": 3842.5,
    "codec": "h264",
    "sample_rate": 48000
  },

  "detection": {
    "backend": "silero",
    "threshold": 0.75,
    "offset": 0.0,
    "process_duration": null,
    "analyzed_duration": 3842.5,
    "params": {
      "min_speech_duration_ms": 200,
      "min_silence_duration_ms": 100,
      "speech_pad_ms": 50,
      "merge_gap_seconds": 0.3,
      "pad_seconds": 0.05
    }
  },

  "speech_segments": [
    [1.23, 4.56],
    [8.90, 12.34]
  ],

  "silence_intervals": [
    [0.00, 1.23],
    [4.56, 8.90],
    [12.34, 3842.50]
  ]
}
```

**Design decisions:**

| Choice | Rationale |
|--------|-----------|
| Arrays of `[start, end]` not objects | Compact. Hundreds of segments = smaller file. Easy to scan. |
| `silence_intervals` included | Avoids recomputing the speech-to-silence inversion at load time. |
| No `pipeline_segments` | Those depend on `buffer_duration` which is a processing-time decision. Compute at process time. |
| `source.file` is basename only | Sidecar travels with the video. Absolute paths would break on move. |
| `detection.params` captures all tuning | Reproducibility. Rerun with same params later if needed. |
| `version: 1` | Future schema changes bump this. Loader checks version. |

### Loading Logic

When `--vad-json` is provided:

```python
def load_vad_metadata(path):
    with open(path) as f:
        meta = json.load(f)

    if meta.get("version", 0) != 1:
        error(f"Unsupported vad.json version: {meta.get('version')}")

    silence_intervals = [(s, e) for s, e in meta["silence_intervals"]]
    analyzed_duration = meta["detection"]["analyzed_duration"]

    return silence_intervals, analyzed_duration
```

Then in `main()`, this replaces both the silencedetect and VAD code paths — it directly provides `silence_intervals` which feed into `calculate_segments()`.

---

## Multi-Angle: Duration Mismatch Handling

Real-world recordings rarely have perfectly matching durations. Cameras start/stop at slightly different times.

### Cases

| Case | VAD Duration | Video Duration | Behavior |
|------|-------------|----------------|----------|
| **Exact match** | 3842.5s | 3842.5s | Process normally |
| **Video slightly longer** | 3842.5s | 3843.0s | Process VAD duration, remainder at normal speed |
| **Video slightly shorter** | 3842.5s | 3841.8s | Truncate silence intervals to video duration, warn |
| **Video much shorter** | 3842.5s | 1200.0s | Process available portion, warn prominently |
| **Video much longer** | 3842.5s | 7200.0s | Process VAD duration, remainder at normal speed, warn |

### Tolerance

```
DURATION_WARN_THRESHOLD = 1.0   # seconds — warn if mismatch > this
DURATION_ERROR_THRESHOLD = None  # no hard error — always process what we can
```

**Why no hard error?** The user knows their recordings. A 0.5s mismatch from camera sync drift shouldn't block processing. A large mismatch (broll clip shorter than session) is intentional — they want to speed up what they have.

### Warning Output

```
⚠ Duration mismatch: overhead.mp4 is 0.7s shorter than VAD source
  VAD analyzed: 3842.5s, video: 3841.8s
  Processing will use truncated silence intervals.
```

---

## Folder Processing Details

### File Discovery

When `--folder DIR` is specified:

1. Scan `DIR` for files matching video extensions (default: `mp4,mkv,mov,avi,webm`)
2. Exclude files matching `*.vad.json`
3. Sort alphabetically for deterministic order
4. If `-o` is a directory, output files keep their original names inside that directory

### Output Naming

| Input | `-o output/` result |
|-------|---------------------|
| `session/facecam.mp4` | `output/facecam.mp4` |
| `session/screen.mkv` | `output/screen.mkv` |
| `session/overhead.mp4` | `output/overhead.mp4` |

Output directory is created if it doesn't exist.

### Skip Already-Processed

If an output file already exists with the same name:
- Default: skip with message `Skipping facecam.mp4 (output exists)`
- With `--overwrite`: overwrite without asking

### Error Handling in Batch

If one video fails during batch processing:
- Log the error
- Continue to next video
- Report failures at the end:

```
Done. 3/4 videos processed.
Failed:
  overhead.mp4 — FFmpeg error: Invalid data found when processing input
```

---

## Putting It All Together: Real Session Walkthrough

### Recording Day

You recorded a 1-hour tutorial with:
- Face camera (Sony ZV-1) → `facecam.mp4` (good mic built in)
- Screen capture (OBS) → `screen.mp4` (system audio)
- Overhead camera (GoPro) → `overhead.mp4` (crappy audio)

All three started recording within a few seconds of each other. Durations are close but not identical.

### Post-Recording Workflow

```bash
# 1. Detect speech on the file with the best audio
$ python videospeeder.py -i raw/facecam.mp4 --vad --detect

  VAD Detection Complete
  Input:    raw/facecam.mp4
  Duration: 3842.5s (1h 4m 2s)
  Speech:   47m 12s (73.4%)
  Silence:  16m 50s (26.6%)
  Wrote:    raw/facecam.vad.json

# 2. (Optional) Inspect the detection results
$ python vad_dump.py -i raw/facecam.mp4 --format text --at 120.0
  # Shows what VAD detected around the 2-minute mark

# 3. Speed all angles using that detection
$ python videospeeder.py --folder raw/ \
                         --vad-json raw/facecam.vad.json \
                         -o processed/ \
                         --quiet

  [1/3] facecam.mp4:  100%|████████████████| [08:23]
  [2/3] screen.mp4:   100%|████████████████| [06:41]
  [3/3] overhead.mp4: 100%|████████████████| [07:12]
  Done. 3 videos → processed/

# 4. Import processed/ folder into DaVinci Resolve
#    All three files have identical timing — sync up perfectly
```

### Or the One-Liner Version

```bash
$ python videospeeder.py --folder raw/ \
                         --vad --vad-master facecam.mp4 \
                         -o processed/ \
                         --quiet
```

Same result. Detects on `facecam.mp4`, writes sidecar, processes all three.

---

## Just Recipes (Proposed)

```just
# VAD detect on master audio
detect master="facecam.mp4":
  python {{script}} -i "{{input}}/{{master}}" --vad --detect

# Speed all angles in a folder
speed-folder vad_json="facecam.vad.json":
  python {{script}} --folder "{{input}}" \
                    --vad-json "{{input}}/{{vad_json}}" \
                    -o "{{input}}/output/" \
                    --quiet

# One-shot: detect + speed all
speed-all master="facecam.mp4":
  python {{script}} --folder "{{input}}" \
                    --vad --vad-master "{{master}}" \
                    -o "{{input}}/output/" \
                    --quiet
```

---

## Open Questions

### Q1: Should `--detect` require `-i` and `--vad`, or be its own subcommand?

**RESOLVED: Flag on existing command.**

Rationale: Adding a subcommand (`videospeeder detect ...`) would break the simple flat CLI. Keeping `--detect` as a flag means it composes naturally: `--vad --detect` = "do the VAD thing but just write the file". No new entry points, no new scripts to learn.

### Q2: What if a folder has multiple `.vad.json` files?

**RESOLVED: Error with guidance.**

```
Error: Found 2 .vad.json files in session/:
  facecam.vad.json
  screen.vad.json
Specify which to use with --vad-json
```

### Q3: Should `--folder` auto-discover `.vad.json`?

**RESOLVED: Yes, with explicit override.**

Auto-discovery when `--folder` is used without `--vad` or `--vad-json`:
1. Look for `*.vad.json` in the folder
2. If exactly one found → use it (print which one)
3. If zero found → error: "No .vad.json found. Run --detect first or specify --vad-json"
4. If multiple found → error (see Q2)

When `--vad-json` is explicit, skip auto-discovery.

### Q4: Should `--detect` also work with silencedetect (non-VAD)?

**OPEN.**

Currently `--detect` requires `--vad`. But the sidecar format could also capture silencedetect results. Would let users do:

```
$ python videospeeder.py -i facecam.mp4 -t -35 -d 1.5 --detect
  Wrote: facecam.vad.json  (using silencedetect backend)
```

The sidecar schema already has `detection.backend` which could be `"silero"` or `"silencedetect"`. This is low effort and makes the two-pass workflow available to non-VAD users too.

**Recommendation:** Support it. The sidecar is backend-agnostic — it stores silence intervals regardless of how they were computed.

### Q5: Per-angle offset for multi-angle?

**OPEN.**

If cameras start at different times, the user needs per-angle offsets. This is complex UX for a CLI tool.

Options:
- **A) Ignore for v1.** User syncs in their NLE after VideoSpeeder. Most cameras start within 1-2 seconds, which is close enough for speed-up purposes.
- **B) Accept a simple global offset.** `--folder-offset 2.5` shifts the VAD timing by 2.5s for all folder videos relative to the master. Useful if you know the other cameras started 2.5s later.
- **C) Per-file offset via a manifest.** Too complex for v1.

**Recommendation:** Option A for v1. Sync is an NLE problem. VideoSpeeder's job is to make the speed-ups identical, not to time-align the source files.

### Q6: What about --detect for the existing --vad inline mode?

**RESOLVED: Keep both paths.**

- `--vad` (no `--detect`): Detect + process in one shot (existing behavior, unchanged)
- `--vad --detect`: Detect only, write sidecar, exit
- `--vad-json PATH`: Load sidecar, skip detection, process

The three modes are additive. No breaking changes.

---

## Summary of New CLI Surface

### Minimum viable addition (Phase 1)

```
--detect           Write .vad.json sidecar and exit
--vad-json PATH    Load .vad.json instead of running detection
--quiet            Progress bar + summary only
```

**3 flags.** That's the minimum to unlock the two-pass workflow for both single files and manual multi-angle (run videospeeder once per angle with same `--vad-json`).

### Folder processing (Phase 2)

```
--folder DIR       Process all videos in directory
--vad-master FILE  Which file to detect on (with --folder --vad)
--overwrite        Overwrite existing outputs
--extensions EXT   Video extensions to scan (default: mp4,mkv,mov,avi,webm)
```

**4 more flags.** Unlocks the `--folder` batch workflow.

### Output cleanup (Either phase)

```
--quiet            Minimal terminal output
--no-stats         Suppress rich video stats table only
```

Plus: remove `[DEBUG]` print statements from `main()` that are development artifacts.

---

## Non-Goals (Explicitly Out of Scope)

- **Audio fingerprint sync** — NLE handles this better
- **GUI/drag-and-drop** — CLI tool stays CLI
- **Parallel encoding** — Process sequentially; FFmpeg already uses multiple cores
- **Cloud/remote processing** — Local only
- **Project files / workspace concept** — The folder IS the project. Sidecar IS the metadata.
- **Frame-accurate sync verification** — Duration check is sufficient

---

*This workshop captures the intended user experience and CLI design. Use as reference during implementation. Update Open Questions as decisions are made.*
