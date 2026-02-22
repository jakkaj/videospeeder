# Phase 2: Folder Processing — Execution Log

**Plan**: [../../vad-first-pass-multi-angle-plan.md](../../vad-first-pass-multi-angle-plan.md)
**Dossier**: [./tasks.md](./tasks.md)
**Started**: 2026-02-22

---

## Task T009: Add CLI flags + validation matrix
**Started**: 2026-02-22
**Status**: ✅ Complete

### What I Did
1. Added 4 new argparse flags to `parse_args()` after `--debug-segments`:
   - `--folder DIR` (str, default None) — process all video files in DIR
   - `--vad-master FILE` (str, default None) — master file for VAD detection in folder mode
   - `--overwrite` (store_true) — re-process even if output exists
   - `--extensions` (str, default "mp4,mkv,mov,avi,webm") — comma-separated video extensions

2. Restructured validation matrix in `main()` (lines 1074-1132):
   - `--vad-master` requires `--folder` (line 1081)
   - Folder mode: no `--detect`, requires `-o`, `--vad` requires `--vad-master`, folder must exist
   - Detect-only: requires `-i`
   - vad-json: requires `-i` and `-o`
   - Default: requires `-i` and `-o`

3. Applied DYK #1 fix: Changed `os.path.isfile(args.input)` to `if args.input and not os.path.isfile(args.input)` (line 1130) — prevents TypeError when args.input is None in folder mode.

### Evidence
- `--folder` flag accepted: `parser.add_argument("--folder", ...)` at line 167
- `--vad-master` flag accepted: `parser.add_argument("--vad-master", ...)` at line 171
- `--overwrite` flag accepted: `parser.add_argument("--overwrite", ...)` at line 175
- `--extensions` defaults to `mp4,mkv,mov,avi,webm`: line 180
- Validation matrix covers all error cases: lines 1074-1132
- DYK #1 guarded: `if args.input and not os.path.isfile(args.input):` at line 1130

### Files Changed
- `videospeeder_project/videospeeder.py` — Added 4 argparse flags (lines 167-182), restructured validation matrix (lines 1074-1132)

**Completed**: 2026-02-22
---

## Task T010: Implement discover_videos() helper
**Started**: 2026-02-22
**Status**: ✅ Complete

### What I Did
Added `discover_videos(folder, extensions)` function between `truncate_intervals_to_duration()` and `calculate_segments()`. It:
1. Parses comma-separated extensions string into a list
2. Scans folder with `os.listdir()` — flat only, no recursion
3. Filters by extension match (case-insensitive)
4. Excludes `*.vad.json` files explicitly
5. Returns sorted list of absolute paths

### Evidence
- Function at line 730 of videospeeder.py
- Handles edge cases: strips whitespace, normalizes dots in extensions, case-insensitive matching

### Files Changed
- `videospeeder_project/videospeeder.py` — Added `discover_videos()` (~15 lines)

**Completed**: 2026-02-22
---

## Task T011: Implement discover_sidecar() helper
**Started**: 2026-02-22
**Status**: ✅ Complete

### What I Did
Added `discover_sidecar(folder)` function next to `discover_videos()`. It:
1. Uses `glob.glob()` to find `*.vad.json` files in folder
2. Exactly one → returns path + prints which file found (AC-8)
3. Zero → prints error to stderr + `sys.exit(1)`
4. Multiple → prints error listing all found files + `sys.exit(1)` (AC-9)

### Evidence
- Function at line 747 of videospeeder.py
- Zero sidecars: `Error: No .vad.json sidecar found in '{folder}'.`
- Multiple sidecars: lists each file, suggests `--vad-json` flag
- Single sidecar: `Auto-discovered sidecar: {path}`

### Discoveries
- Combined T010 and T011 in single edit since they're naturally co-located between `truncate_intervals_to_duration()` and `calculate_segments()`.

### Files Changed
- `videospeeder_project/videospeeder.py` — Added `discover_sidecar()` (~18 lines)

**Completed**: 2026-02-22
---

## Task T012: Implement folder processing loop in main()
**Started**: 2026-02-22
**Status**: ✅ Complete

### What I Did
Added `if args.folder:` block after detect-only exit (line 1236), containing the full folder processing flow:

1. **DYK #3 guard**: `os.path.realpath(folder) != os.path.realpath(output_dir)` — prevents `--overwrite` from destroying source files when output dir == input folder.
2. **Output dir creation**: `os.makedirs(output_dir, exist_ok=True)`
3. **Sidecar resolution**: Uses `--vad-json` if given, otherwise calls `discover_sidecar()`
4. **Load sidecar once**: `load_vad_metadata()` returns `silence_intervals_master` + `analyzed_duration`
5. **Video discovery**: `discover_videos()` finds matching files; error if empty
6. **DYK #4**: `args.gpu_decode = False` set independently (unreachable from line 1236 GPU disable)
7. **Per-video loop** with `try/except`:
   - Skip existing outputs unless `--overwrite` (AC-11)
   - Compute per-video duration
   - **DYK #2**: `list(silence_intervals_master)` defensive copy before truncation
   - Duration mismatch: truncate + warn to stderr
   - `calculate_segments()` → `build_filtergraph()` → `run_ffmpeg_processing()`
   - **DYK #4**: `setattr` for `use_gpu_decode` and `progress_segments` per video
   - On exception: log error to stderr, increment fail_count, continue (AC-12)
8. **Summary**: Always prints "Done. N/M videos processed, X skipped, Y failed."
9. **Exit code**: `sys.exit(1)` only if all videos failed; `sys.exit(0)` if any succeeded

### Evidence
- Folder block at lines 1236-1337 of videospeeder.py
- DYK #2 defensive copy: `silence_intervals = list(silence_intervals_master)` at ~line 1281
- DYK #3 realpath check at lines 1238-1242
- DYK #4 gpu_decode set at line 1261, setattr per video at lines 1296-1297
- Skip logic: `os.path.isfile(output_path) and not args.overwrite` at line 1269
- Continue on failure: `except Exception as e:` at line 1321
- Summary prints regardless of `--quiet` at line 1329

### Files Changed
- `videospeeder_project/videospeeder.py` — Added folder processing block (~100 lines) in main()

**Completed**: 2026-02-22
---

## Task T013: Implement --vad-master one-liner mode
**Started**: 2026-02-22
**Status**: ✅ Complete

### What I Did
Added `if args.vad_master:` block inside the folder processing section (before sidecar resolution). It:
1. Resolves master file path relative to `--folder` if not absolute
2. Validates master file exists
3. Computes detection duration (respects `--offset`, `--process-duration`)
4. Branches on `args.vad` for Silero vs silencedetect backend (same as detect-only path)
5. Calls `write_vad_metadata()` to write sidecar next to master file
6. Prints detect summary (speech %, silence count, duration)
7. Falls through to folder loop which now uses the just-written sidecar

Also updated sidecar resolution: `elif not args.vad_master:` ensures auto-discover only runs when vad-master didn't just write a sidecar (otherwise `sidecar_path` is already set).

### Evidence
- vad-master block at lines 1249-1316 of videospeeder.py
- Master path resolution: relative to --folder if not absolute (line 1252)
- Both backends supported: Silero VAD (lines 1266-1288), silencedetect (lines 1289-1306)
- Sidecar resolution: `elif not args.vad_master:` prevents overwriting just-written sidecar path

### Files Changed
- `videospeeder_project/videospeeder.py` — Added vad-master detect block (~70 lines), modified sidecar resolution conditional

**Completed**: 2026-02-22
---

## Task T014: Add Justfile recipes
**Started**: 2026-02-22
**Status**: ✅ Complete

### What I Did
Added folder mode variables and 3 new recipes to the Justfile:

1. **Variables** (lines 77-79):
   - `folder ?= "scratch/multi-angle"` — default input folder
   - `folder_output ?= "scratch/multi-angle/output"` — default output folder
   - `master ?= "scratch/multi-angle/facecam.mp4"` — default master file

2. **Recipes**:
   - `detect` — runs `--detect` on master file to write `.vad.json` sidecar
   - `speed-folder` — runs `--folder` mode with existing sidecar
   - `speed-all` — runs `--folder` + `--vad-master` one-liner mode

### Evidence
- `just detect` recipe at line 82
- `just speed-folder` recipe at line 86
- `just speed-all` recipe at line 90
- All recipes use existing `script` variable pattern

### Files Changed
- `Justfile` — Added 3 variables + 3 recipes (~15 lines)

**Completed**: 2026-02-22
---

## Task T015: Update README.md
**Started**: 2026-02-22
**Status**: ✅ Complete

### What I Did
Updated README.md with all new flags and a multi-angle workflow section:

1. **Added Phase 1 flags** to Common Options:
   - `--detect` — write `.vad.json` sidecar and exit
   - `--vad-json` — load silence intervals from sidecar
   - `--quiet` — suppress informational output

2. **Added Phase 2 flags** to Common Options:
   - `--folder` — process all videos in directory
   - `--vad-master` — master file for folder-mode detection
   - `--overwrite` — re-process existing outputs
   - `--extensions` — comma-separated video extension filter

3. **Added Multi-Angle Workflow section** with:
   - Two-step workflow example (detect + speed-folder)
   - One-liner workflow example (--vad-master)
   - Feature list: auto-discover, skip existing, continue on failure, duration mismatch handling

### Evidence
- Phase 1 flags at lines 84-86 of README.md
- Phase 2 flags at lines 87-90 of README.md
- Multi-Angle Workflow section at lines ~102-130

### Files Changed
- `README.md` — Added 8 flag descriptions + Multi-Angle Workflow section (~30 lines)

**Completed**: 2026-02-22
---

## Task T016: End-to-end manual validation
**Started**: 2026-02-22
**Status**: ✅ Complete

### What I Did
Ran comprehensive end-to-end validation with synthetic test videos. Created 3 short (2s) test videos with silent audio to verify all Phase 2 acceptance criteria plus Phase 1 regression.

### Evidence

**Validation matrix (CLI error handling):**
- `--vad-master` without `--folder` → "Error: --vad-master requires --folder." ✅
- `--folder` without `-o` → "Error: --folder requires -o/--output (output directory)." ✅
- `--folder` + `--detect` → "Error: --folder and --detect cannot be used together." ✅
- `--folder` + `--vad` without `--vad-master` → "Error: --folder with --vad requires --vad-master..." ✅

**AC-3/AC-4 (--detect writes sidecar):** `--detect` writes valid v1 JSON sidecar with silence_intervals ✅

**AC-7 (folder processes all videos):** 3/3 videos processed with shared sidecar, all output files created ✅

**AC-8 (auto-discovers sidecar):** "Auto-discovered sidecar: .../facecam.vad.json" printed, single sidecar found ✅

**AC-9 (multiple sidecars error):** Two sidecars → error listing both, suggests `--vad-json` ✅

**AC-10 (--vad-master one-liner):** Detected on master, wrote sidecar, processed all 3 videos in one command ✅

**AC-11 (skip existing / --overwrite):**
- Without `--overwrite`: "Skipping (output exists): facecam.mp4" × 3, "0/3 processed, 3 skipped" ✅
- With `--overwrite`: All 3 re-processed ✅

**AC-12 (continue on failure):** Corrupt video failed, 3 valid videos processed, "3/4 processed, 1 failed" ✅

**DYK #3 (output == input dir):** "Error: Output directory is the same as input folder." ✅

**Phase 1 regression:**
- `--vad-json` single-file mode works ✅
- `--quiet` suppresses verbose output ✅
- Default mode (silencedetect, no new flags) works ✅
- `--folder` with explicit `--vad-json` works ✅

**Zero sidecars error:** "Error: No .vad.json sidecar found in '...'" ✅

### Notes
- AC-1 (Silero VAD) untestable without torch — same as Phase 1 (structural verification only)
- AC-13-AC-16 are Phase 1 ACs already verified during Phase 1 E2E validation
- Test used synthetic 2-second silent videos (testsrc + anullsrc) to keep validation fast

**Completed**: 2026-02-22
---
