# Parallel Folder Processing

**Mode**: Simple

📚 This specification incorporates findings from research-dossier.md

## Research Context

- **Components affected**: `videospeeder_project/videospeeder.py` — folder mode processing loop, `run_ffmpeg_processing()`, `parse_args()`
- **Critical dependencies**: NVIDIA NVENC session limits (12 max on current consumer drivers), Python `concurrent.futures`
- **Modification risks**: Thread-unsafe `setattr` pattern on `run_ffmpeg_processing` must be fixed before parallelizing; tqdm progress bars collide when multiple FFmpeg processes run simultaneously
- **Link**: See `research-dossier.md` for full analysis

## Summary

When processing multiple camera angles in folder mode, VideoSpeeder currently encodes videos one at a time, leaving the GPU underutilized. Adding a `--parallel N` CLI switch lets users process N videos simultaneously, significantly reducing total wall-clock time for multi-angle workflows. Each video's encode is fully independent (shared VAD sidecar, independent filtergraphs and FFmpeg processes), making this embarrassingly parallel.

## Goals

- Allow users to process multiple videos simultaneously in folder mode via `--parallel N`
- Reduce total wall-clock time for multi-angle workflows (target: ~1.8x speedup at `--parallel 2`)
- Maintain identical output quality and duration sync across all angles (same as sequential mode)
- Provide sensible defaults and warnings related to GPU session limits
- Keep `--parallel 1` as default for full backward compatibility
- Report per-file success/failure results with a clear summary at the end

## Non-Goals

- Parallelizing VAD detection (detection runs once on the master file; already fast)
- Automatic GPU session limit detection (no reliable API exists; use conservative defaults)
- Per-frame progress bars for individual files in parallel mode (file-level progress is sufficient)
- CPU encoding parallelism tuning (FFmpeg's `libx265` already uses multiple threads per instance)
- Parallel processing in single-file mode (only folder mode benefits)

## Complexity

- **Score**: CS-2 (small)
- **Breakdown**: S=1, I=0, D=0, N=0, F=1, T=0
  - Surface Area (1): One file modified (`videospeeder.py`), but multiple functions touched (parse_args, run_ffmpeg_processing signature, folder mode loop)
  - Integration (0): Uses only Python stdlib (`concurrent.futures`) — no new external deps
  - Data/State (0): No schema or state changes; sidecar format unchanged
  - Novelty (0): Well-specified from research; clear implementation path
  - Non-Functional (1): Must respect GPU session limits; performance is the whole point
  - Testing/Rollout (0): Manual benchmark testing (1, 2, 4 parallel on 5-min clips)
- **Confidence**: 0.90
- **Assumptions**:
  - User has an NVIDIA GPU with current drivers (session limit >= 8)
  - 4 camera angles is the typical multi-angle workflow
  - `ThreadPoolExecutor` is sufficient (FFmpeg is the actual compute, not Python)
- **Dependencies**: NVIDIA GPU with NVENC support, FFmpeg built with NVENC
- **Risks**: Exceeding NVENC session limit causes immediate FFmpeg failure (not graceful degradation)
- **Phases**: Single phase — refactor for thread safety, add CLI arg, wrap in executor, benchmark

## Acceptance Criteria

1. **AC1**: `--parallel N` argument is accepted in folder mode; ignored in single-file mode
2. **AC2**: With `--parallel 2`, two FFmpeg encode processes run simultaneously (observable via `nvidia-smi` or process list)
3. **AC3**: Output video durations are identical across all angles when processed with `--parallel N` (same as sequential)
4. **AC4**: If one video fails during parallel processing, other videos continue and complete; summary reports which files succeeded/failed
5. **AC5**: `--parallel 1` produces identical behavior to the current sequential implementation (backward compatible)
6. **AC6**: A warning is printed when `--parallel N` with `--gpu` exceeds a conservative threshold (e.g., N > 4)
7. **AC7**: File-level progress is shown during parallel processing (e.g., "Processed 2/4 files")
8. **AC8**: Benchmark shows measurable wall-clock time reduction with `--parallel 2` vs `--parallel 1` on 4 test clips

## Risks & Assumptions

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| NVENC session limit exceeded at high parallelism | Medium | High (FFmpeg fails immediately) | Warn above 4; document limit in help text |
| Interleaved stdout from parallel FFmpeg processes | High | Low (cosmetic) | Suppress per-file progress in parallel mode; show file-level progress only |
| Thread-unsafe `setattr` pattern causes race condition | High (if not fixed) | High (wrong segments applied to wrong video) | Fix by converting to explicit function parameters before adding parallelism |
| Thermal throttling under sustained parallel GPU load | Low | Low (slower but still works) | Users can reduce parallelism if GPU overheats |

**Assumptions**:
- The `run_ffmpeg_processing` function can be made thread-safe by converting 2 `setattr`/`getattr` calls to explicit parameters
- Each FFmpeg encode uses exactly 1 NVENC session
- File-level progress (N/M files done) is acceptable for parallel mode UX

## Open Questions

None — research dossier addressed all significant questions.

## Testing Strategy

- **Approach**: Manual Only
- **Rationale**: This feature wraps FFmpeg subprocesses — automated unit tests add little value. Real-world benchmarking with actual video files on real GPU hardware is the meaningful validation.
- **Focus Areas**: Wall-clock time comparison (1 vs 2 vs 4 parallel), output duration sync across angles, error handling when a file fails
- **Excluded**: Unit tests, integration tests, mocks
- **Mock Usage**: N/A (manual testing with real data)

## Documentation Strategy

- **Location**: README.md only
- **Rationale**: `--parallel` is a simple CLI flag that fits naturally into the existing CLI options section and folder mode examples.
- **Target Audience**: Users running multi-angle video workflows
- **Maintenance**: Update alongside any future folder mode changes

## Workshop Opportunities

None identified — the feature is well-specified from research and has a clear implementation path.

## Clarifications

### Session 2026-02-22

| # | Topic | Decision | Rationale |
|---|-------|----------|-----------|
| Q1 | Workflow Mode | Simple | Pre-set in spec — CS-2 single-phase feature |
| Q2 | Testing Strategy | Manual Only | Benchmark with real 5-min clips at --parallel 1, 2, 4; compare wall-clock time and verify output durations match |
| Q3 | Documentation | README.md only | Add --parallel to existing CLI options section and folder mode examples |
