# Flight Plan: Phase 1 — Two-Pass Workflow + Output Cleanup

**Phase**: Phase 1: Two-Pass Workflow + Output Cleanup
**Plan**: [../../vad-first-pass-multi-angle-plan.md](../../vad-first-pass-multi-angle-plan.md)
**Dossier**: [./tasks.md](./tasks.md)
**Date**: 2026-02-22

---

## What This Phase Does

Adds two-pass VAD workflow to videospeeder: detect-only mode writes `.vad.json` sidecar, process-from-sidecar mode reads it. Also adds `--quiet` flag and removes `[DEBUG]` artifacts. All changes in one file: `videospeeder.py`.

## Before

```
videospeeder.py -i in.mp4 -o out.mp4 --vad
  → Detects + processes in one pass (only workflow)
  → [DEBUG] lines print to terminal
  → No way to suppress verbose output
```

## After

```
videospeeder.py -i in.mp4 --vad --detect
  → Runs detection, writes .vad.json sidecar, exits

videospeeder.py -i in.mp4 -o out.mp4 --vad-json in.vad.json
  → Loads sidecar, skips detection, processes video

videospeeder.py -i in.mp4 -o out.mp4 --vad --quiet
  → Single-pass with minimal output (progress bar + summary only)

videospeeder.py -i in.mp4 -o out.mp4 --vad
  → Still works exactly as before (backward compat)
```

---

## Stages

### Stage 1: Cleanup
- [x] **T001**: Remove `[DEBUG]` prints from main()

### Stage 2: CLI Foundation
- [x] **T002**: Add `--detect`, `--vad-json`, `--quiet` flags; mutual exclusion group; remove required=True from -i/-o

### Stage 3: Sidecar Functions
- [x] **T003**: Implement `write_vad_metadata()` — sidecar writer (both backends)
- [x] **T004**: Implement `load_vad_metadata()` — sidecar reader + version check

### Stage 4: New Code Paths
- [x] **T005**: Detect-only path in main() (VAD + silencedetect)
- [x] **T006**: Vad-json loading path in main() + duration mismatch handling

### Stage 5: Output Control
- [x] **T007**: `--quiet` mode output suppression

### Stage 6: Validation
- [x] **T008**: Manual validation of AC-1 through AC-16 (Phase 1 subset)

---

## Key Files

| File | Changes |
|------|---------|
| `videospeeder_project/videospeeder.py` | All T001-T007: cleanup, new flags, 2 new functions, 2 new code paths, quiet gates |

## Protected Zones (DO NOT MODIFY)

- `build_filtergraph()` (lines 669-787)
- `run_ffmpeg_processing()` (lines 789-956)
- Detection functions (lines 190-615)

## Test Videos

- `~/VideoMedia/SoloXC/working/Angle 1.mp4` (~5 min clip)
- `~/VideoMedia/SoloXC/working/Angle 2.mp4` (~5 min clip)

---

## Acceptance Criteria Checklist

- [~] AC-1: `--vad --detect` writes sidecar and exits — code path verified, torch not available for live test
- [x] AC-2: `--detect` (no --vad) writes silencedetect sidecar
- [x] AC-3: `--vad-json` loads sidecar and processes
- [x] AC-4: Duration mismatch truncates + warns
- [x] AC-5: Bad version → error + exit(1)
- [x] AC-6: `--vad` + `--vad-json` → argparse error
- [x] AC-13: `--quiet` suppresses verbose output
- [x] AC-14: No overlays without `--indicator`
- [x] AC-15: Backward compat preserved
- [x] AC-16: No `[DEBUG]` without `--debug-segments`

---

**Next**: `/plan-6-implement-phase --phase "Phase 1: Two-Pass Workflow + Output Cleanup" --plan "/home/jak/github/videospeeder/docs/plans/007-vad-first-pass-multi-angle/vad-first-pass-multi-angle-plan.md"`
