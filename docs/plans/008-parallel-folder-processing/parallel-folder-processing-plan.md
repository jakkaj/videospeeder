# Parallel Folder Processing Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-02-22
**Spec**: [./parallel-folder-processing-spec.md](./parallel-folder-processing-spec.md)
**Status**: DRAFT

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Critical Research Findings](#critical-research-findings)
3. [Implementation](#implementation)
4. [Change Footnotes Ledger](#change-footnotes-ledger)

## Executive Summary

VideoSpeeder's folder mode processes multiple camera angles sequentially, leaving the GPU underutilized between encode bursts. This plan adds a `--parallel N` CLI switch that runs N simultaneous FFmpeg encodes via `ThreadPoolExecutor`, targeting ~1.8x speedup at `--parallel 2`. The implementation requires fixing a thread-unsafe `setattr` pattern on `run_ffmpeg_processing`, extracting the per-video loop body into a standalone function, and wrapping it in an executor with file-level progress reporting.

## Critical Research Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | **Data race on function attributes**: `setattr(run_ffmpeg_processing, "use_gpu_decode", ...)` and `setattr(run_ffmpeg_processing, "progress_segments", ...)` write to shared function object — threads will overwrite each other's segments | Convert all 4 `setattr` + 3 `getattr` calls to explicit function parameters; update both folder-mode and single-file-mode call sites |
| 02 | High | **NVENC session limit**: Consumer GPUs support 12 concurrent sessions (driver 591.44+). Exceeding the limit causes immediate `NV_ENC_ERR_OUT_OF_MEMORY` failure — no queuing or retry | Warn when `--parallel N` with `--gpu` exceeds 4; document limit in `--help` text |
| 03 | High | **Console output interleaving**: Multiple FFmpeg processes write to stderr simultaneously; tqdm bars collide with no `position` param | Suppress per-file tqdm in parallel mode (`show_progress=False`); show file-level counter instead |
| 04 | High | **run_ffmpeg_processing signature needs 3 new params**: `use_gpu_decode`, `progress_segments`, `show_progress` to replace getattr pattern and control tqdm | Add params with defaults that preserve backward compat: `use_gpu_decode=False`, `progress_segments=None`, `show_progress=True` |
| 05 | Medium | **Folder loop body is self-contained**: Lines 1368-1431 have no shared mutable state after `list()` copy of silence_intervals — ready for extraction | Extract to `process_single_video()` function returning `{"status": "success|error|skipped", "file": name}` |
| 06 | Medium | **Partial output files on failure**: Failed FFmpeg encodes leave incomplete output files, which then trigger the skip-if-exists check on retry | Not in scope (pre-existing behavior), but document as known limitation |
| 07 | Medium | **Thread-safe functions confirmed**: `calculate_segments()`, `build_filtergraph()`, and `fastforward.png` (read-only by FFmpeg) are all safe for concurrent use | No guards needed for these |
| 08 | Medium | **tqdm has no quiet awareness**: The tqdm bar inside `run_ffmpeg_processing` ignores `--quiet` flag — it always shows | Add `show_progress` param to control tqdm; respect it in both sequential and parallel modes |
| 09 | Low | **ThreadPoolExecutor is correct choice**: Python GIL is irrelevant since FFmpeg subprocesses do the actual compute. Threads are lighter than processes for managing subprocess I/O | Use `ThreadPoolExecutor`, not `ProcessPoolExecutor` |
| 10 | Low | **Missing test clips**: Only angle3.mp4 and angle4.mp4 exist in scratch/real-test/ (300.07s each). angle1 and angle2 need cutting from full-length sources | Cut 5-min clips from `~/VideoMedia/SoloXC/Angle {1,2}.mp4` before benchmarking |

## Implementation (Single Phase)

**Objective**: Add `--parallel N` support to folder mode with thread-safe video processing and file-level progress.

**Testing Approach**: Manual Only — benchmark with real 5-min clips at `--parallel 1`, `2`, `4`; compare wall-clock time and verify output durations match.
**Mock Usage**: N/A

### Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Notes |
|--------|-----|------|----|------|--------------|------------------|------------|-------|
| [x] | T001 | Refactor `run_ffmpeg_processing` to accept `use_gpu_decode`, `progress_segments`, and `show_progress` as explicit parameters; remove all `setattr`/`getattr` calls (4 setattr at lines 1403, 1404, 1579, 1582 and 3 getattr at lines 987, 1025, 1588); add `show_progress=True` param to gate tqdm bar creation | 2 | Core | -- | /home/jak/github/videospeeder/videospeeder_project/videospeeder.py | All 7 setattr/getattr sites eliminated; single-file mode still works identically; `python videospeeder.py -i test.mp4 -o out.mp4 --gpu` produces same output | Per Finding 01, 04, 08 |
| [x] | T002 | Update single-file mode call site (lines ~1579-1610) to pass `use_gpu_decode=args.gpu_decode` and `progress_segments=segments` directly to `run_ffmpeg_processing`; update `build_filtergraph` call to use `args.gpu_decode` directly instead of `getattr` | 1 | Core | T001 | /home/jak/github/videospeeder/videospeeder_project/videospeeder.py | Single-file mode with `--gpu` and `--gpu-decode` works identically to before refactor | Keeps single-file path clean |
| [x] | T003 | Extract folder-mode per-video loop body (lines 1368-1431) into `process_single_video(video_path, output_dir, silence_intervals_master, analyzed_duration, args, png_path)` function that returns a result dict `{"status": "success|error|skipped", "file": video_name, "error": optional_str}` | 2 | Core | T001 | /home/jak/github/videospeeder/videospeeder_project/videospeeder.py | Folder mode with `--parallel 1` produces identical results to current sequential behavior | Per Finding 05 |
| [x] | T004 | Add `--parallel N` argument to `parse_args()` with `type=int, default=1, metavar="N"`; add validation: must be >= 1, warn to stderr if N > 4 with `--gpu`; ignore `--parallel` in single-file mode (print info message) | 1 | Core | -- | /home/jak/github/videospeeder/videospeeder_project/videospeeder.py | `--parallel 2` accepted; `--parallel 0` errors; `--parallel 8 --gpu` prints warning; single-file mode ignores the flag | Per Finding 02 |
| [x] | T005 | Replace sequential folder loop with `ThreadPoolExecutor(max_workers=args.parallel)`; use `concurrent.futures.as_completed()` to collect results; show file-level progress (`Processed 2/4 files`); pass `show_progress=(args.parallel == 1)` to suppress per-file tqdm when parallel > 1; collect success/fail/skip from result dicts; print summary at end | 2 | Core | T003, T004 | /home/jak/github/videospeeder/videospeeder_project/videospeeder.py | With `--parallel 2`, two FFmpeg processes visible in `nvidia-smi` simultaneously; summary shows correct counts; `--parallel 1` behavior unchanged | Per Finding 03, 09 |
| [x] | T006 | Update README.md: add `--parallel N` to Common Options table; add parallel example to Multi-Angle Workflow section; add note about NVENC session limits | 1 | Doc | T005 | /home/jak/github/videospeeder/README.md | README documents `--parallel` flag with usage example and GPU limit note | Per spec Documentation Strategy |
| [ ] | T007 | Cut 5-min test clips for angle1 and angle2 from full-length sources; generate shared VAD sidecar; run benchmarks at `--parallel 1`, `2`, `4` on all 4 clips; record wall-clock times | 2 | Test | T005 | /home/jak/github/videospeeder/scratch/real-test/ | Benchmark data shows measurable speedup at `--parallel 2` vs `1`; output durations match across all 4 angles | Per Finding 10, AC8 |

### Acceptance Criteria

- [x] AC1: `--parallel N` argument is accepted in folder mode; ignored in single-file mode
- [ ] AC2: With `--parallel 2`, two FFmpeg encode processes run simultaneously
- [ ] AC3: Output video durations are identical across all angles when processed with `--parallel N`
- [x] AC4: If one video fails during parallel processing, other videos continue; summary reports success/failure
- [x] AC5: `--parallel 1` produces identical behavior to the current sequential implementation
- [x] AC6: A warning is printed when `--parallel N` with `--gpu` exceeds 4
- [x] AC7: File-level progress is shown during parallel processing (e.g., "Processed 2/4 files")
- [ ] AC8: Benchmark shows measurable wall-clock time reduction with `--parallel 2` vs `--parallel 1`

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| NVENC session limit exceeded at high parallelism | Medium | High (FFmpeg fails immediately) | Warn above 4; document in help text |
| Interleaved stdout from parallel FFmpeg processes | High | Low (cosmetic) | Suppress per-file tqdm in parallel mode |
| Thread-unsafe `setattr` pattern causes data race | High (if not fixed) | High (wrong segments for wrong video) | T001 fixes this before parallelism is added |
| Thermal throttling under sustained parallel GPU load | Low | Low (slower but still works) | Users can reduce parallelism |

## Change Footnotes Ledger

[^1]: [To be added during implementation via plan-6a]
[^2]: [To be added during implementation via plan-6a]

---

**Next steps:**
- **Ready to implement**: `/plan-6-implement-phase --plan "/home/jak/github/videospeeder/docs/plans/008-parallel-folder-processing/parallel-folder-processing-plan.md"`
- **Optional validation**: `/plan-4-complete-the-plan` (recommended for CS-3+ tasks)
- **Optional task expansion**: `/plan-5-phase-tasks-and-brief` (if you want a separate dossier)
