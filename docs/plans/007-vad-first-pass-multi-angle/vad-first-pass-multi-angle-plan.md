# VAD First-Pass Detection with Multi-Angle Support — Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-02-22
**Spec**: [./vad-first-pass-multi-angle-spec.md](./vad-first-pass-multi-angle-spec.md)
**Workshops**: [./workshops/workflow-and-cli-design.md](./workshops/workflow-and-cli-design.md)
**Status**: COMPLETE

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Critical Research Findings](#critical-research-findings)
3. [Technical Context](#technical-context)
4. [Phase 1: Two-Pass Workflow + Output Cleanup](#phase-1-two-pass-workflow--output-cleanup)
5. [Phase 2: Folder Processing](#phase-2-folder-processing)
6. [Cross-Cutting Concerns](#cross-cutting-concerns)
7. [Change Footnotes Ledger](#change-footnotes-ledger)

## Executive Summary

Content creators recording multi-angle sessions need all camera angles sped up identically so they stay in sync when layered in an NLE. This plan decouples VAD detection from video processing into a two-pass workflow — detect once, speed many — with a `.vad.json` sidecar file bridging the two. Phase 1 adds the two-pass workflow and cleans up terminal output. Phase 2 adds folder-based batch processing for multi-angle workflows.

## Critical Research Findings

Synthesized from [research-dossier.md](./research-dossier.md) and [workshop](./workshops/workflow-and-cli-design.md).

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | **Chunk boundary stitching** (PL-01): Naive chunk concatenation creates false silence gaps. Existing pipeline uses 1s overlap + normalize. | Reuse existing `detect_speech_segments_silero()` — never reimplement VAD streaming. |
| 02 | Critical | **Coordinate alignment** (PL-02): VAD timestamps are relative to processed region starting at 0. Sidecar must record coordinate system. | Store `offset` and `analyzed_duration` in sidecar. All angles must use consistent coordinates. |
| 03 | Critical | **vad_dump.py is the architecture template** (PL-03): Already runs full VAD pipeline and outputs JSON with speech segments + silence intervals. | Model `write_vad_metadata()` on vad_dump.py's data collection pattern. |
| 04 | High | **main() is 170 lines with multiple code paths** — adding more branches increases risk. | Extract `write_vad_metadata()`, `load_vad_metadata()`, `process_folder()` as helper functions. Keep main() orchestration thin. |
| 05 | High | **Sidecar stores silence_intervals, NOT pipeline_segments** — buffer is a processing-time decision. | `calculate_segments()` runs at processing time with current `buffer_duration`. Sidecar is reusable across different buffer settings. |
| 06 | High | **`[DEBUG]` prints are development artifacts** — lines 964-966, 974, 981, 985, 990, 994 in main(). | Remove all `[DEBUG]` prefixed prints. `--debug-segments` is the proper debug mechanism (AC-16). |
| 07 | High | **Lazy import pattern** (PL-04): `import_vad_dependencies()` ensures `--help` works without torch. | New detect-only path must follow same lazy import pattern. Don't import torch at module level. |
| 08 | High | **Detection-backend agnostic sidecar**: Format stores silence intervals regardless of source (silero or silencedetect). | `detection.backend` field distinguishes source. Both backends produce same output format (AC-1, AC-2). |
| 09 | High | **Duration mismatch: warn, never error** (Workshop Q resolved). | Truncate silence intervals to video duration. Print warning if mismatch > 1s. Always process what we can. |
| 10 | High | **`-i` and `-o` are currently `required=True`** — breaks `--detect` (no -o needed) and `--folder` (no -i needed). | Remove `required=True` from both. Validate conditionally in main() based on mode. |
| 11 | Medium | **build_filtergraph() is fragile** — complex FFmpeg filter syntax, easy to break. | Do NOT modify build_filtergraph() or run_ffmpeg_processing(). New code feeds into existing pipeline at the `silence_intervals` convergence point. |
| 12 | Medium | **`--indicator` is already opt-in** (off by default). "Clean output" is already the default behavior (AC-14). | No code change needed for AC-14. Just verify and document. |
| 13 | Medium | **run_ffmpeg_processing uses setattr hack** for `progress_segments` and `use_gpu_decode`. | Follow same pattern for folder mode — set attributes before each video's processing call. |
| 14 | Medium | **Sidecar auto-discovery** (Workshop Q3): exactly one `.vad.json` → use it; zero → error; multiple → error with list. | Implement in `discover_sidecar()` helper. Clear error messages guide the user (AC-8, AC-9). |
| 15 | Low | **torchaudio in requirements.txt is vestigial** — not used anywhere in codebase. | Out of scope for this plan. Note for future cleanup. |

### Constitution Compliance

No deviations from constitution principles required:
- **§1 User Workflow Efficiency**: Multi-angle batch processing directly saves time
- **§2 Intelligent Automation**: Auto-discovery of sidecar files; auto-naming of sidecar from input filename
- **§3 Clarity and Transparency**: Detection summary output; duration mismatch warnings
- **§4 Flexibility and Control**: `--quiet` for scripting; `--extensions` for custom file types; `--overwrite` control

### ADR Ledger

No existing ADRs in `docs/adr/`. Two ADR seeds identified in spec (sidecar format, flags vs subcommands) — resolved in workshop.

## Technical Context

### Current System State

```
videospeeder.py (1132 lines)
├─ parse_args()           lines 95-154   ← MODIFY: add new flags
├─ detect_speech_*()      lines 421-509  ← REUSE (no changes)
├─ normalize/validate()   lines 511-615  ← REUSE (no changes)
├─ calculate_segments()   lines 617-667  ← REUSE (no changes)
├─ build_filtergraph()    lines 669-787  ← DO NOT TOUCH
├─ run_ffmpeg_processing() lines 789-956 ← DO NOT TOUCH
└─ main()                 lines 958-1132 ← MODIFY: add new code paths
```

### Pipeline Convergence Point

Both detection backends converge at `silence_intervals`. New code inserts at this convergence point:

```
Detection (existing)     Sidecar (new)
     │                       │
     ▼                       ▼
silence_intervals ◄──── load_vad_metadata()
     │
     ▼
calculate_segments()  ← existing, unchanged
     │
     ▼
build_filtergraph()   ← existing, unchanged
     │
     ▼
run_ffmpeg_processing() ← existing, unchanged
```

### Key Constraints

- All new code goes in `videospeeder.py` — no new script files (spec, workshop decision)
- Existing `vad_dump.py` stays unchanged (diagnostic tool)
- No new external dependencies
- `-i`/`-o` argparse `required=True` must be removed and validated manually in main()

---

## Phase 1: Two-Pass Workflow + Output Cleanup

**Objective**: Enable detect-only mode that writes `.vad.json` sidecar, process-from-sidecar mode that skips detection, and `--quiet` mode for clean terminal output.

**Testing Approach**: Manual Only
**Mock Usage**: Avoid entirely — real video files only

### Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Notes |
|--------|-----|------|----|------|--------------|------------------|------------|-------|
| [x] | T001 | Remove `[DEBUG]` prints and development artifacts from main() | 1 | Cleanup | -- | /home/jak/github/videospeeder/videospeeder_project/videospeeder.py | No `[DEBUG]` lines in output without `--debug-segments` (AC-16) | Lines 964-966, 974, 981, 985, 990, 994, 1126. Keep error messages, remove debug noise. [^1] |
| [x] | T002 | Add `--detect`, `--vad-json`, `--quiet` flags to parse_args(); make `-i`/`-o` not required | 2 | Core | T001 | /home/jak/github/videospeeder/videospeeder_project/videospeeder.py | `--vad` and `--vad-json` are mutually exclusive via argparse group (AC-6); `-i`/`-o` no longer `required=True`; all three new flags accepted | Mutually exclusive group: `--vad` vs `--vad-json`. Manual validation of -i/-o in main() based on mode. [^2] |
| [x] | T003 | Implement `write_vad_metadata()` function | 2 | Core | T002 | /home/jak/github/videospeeder/videospeeder_project/videospeeder.py | Writes valid v1 `.vad.json` sidecar next to input video with all fields from AC-1: version, source.file (basename), detection.backend, detection.analyzed_duration, speech_segments as `[[s,e],...]`, silence_intervals as `[[s,e],...]`, detection.params | Supports both `silero` and `silencedetect` backends. Schema per workshop sidecar design. [^3] |
| [x] | T004 | Implement `load_vad_metadata()` function | 2 | Core | T003 | /home/jak/github/videospeeder/videospeeder_project/videospeeder.py | Loads and validates `.vad.json`; returns `(silence_intervals, analyzed_duration)`; rejects version != 1 with error message and sys.exit(1) (AC-5) | Convert `[[s,e],...]` arrays back to `List[Tuple[float,float]]`. Implemented with T003. [^3] |
| [x] | T005 | Add detect-only code path in main() | 2 | Core | T003 | /home/jak/github/videospeeder/videospeeder_project/videospeeder.py | `--vad --detect`: runs Silero, writes sidecar, prints summary, exits (AC-1). `--detect` alone: runs silencedetect, writes sidecar, exits (AC-2). Validates: -i required, -o ignored, `--vad-json`+`--detect` is error. | Exits before calculate_segments/build_filtergraph. Print detection summary (speech %, silence count). [^4] |
| [x] | T006 | Add `--vad-json` loading code path in main() | 2 | Core | T004 | /home/jak/github/videospeeder/videospeeder_project/videospeeder.py | `--vad-json path` loads sidecar, skips detection, prints "Loading VAD metadata from X (skipping detection)" (AC-3). Truncates intervals if video duration differs (AC-4). | New code path before the existing `if args.vad:` / `else:` detection branches. truncate_intervals_to_duration() implemented in T003. [^5] |
| [x] | T007 | Implement `--quiet` mode output suppression | 1 | Core | T005, T006 | /home/jak/github/videospeeder/videospeeder_project/videospeeder.py | With `--quiet`: no stats table (`probe_and_print_video_stats` skipped), no interval list, no filtergraph preview, no args dump. Only progress bar + final summary (AC-13). | Gate verbose prints behind `not args.quiet`. [^6] |
| [x] | T008 | Manual validation: Phase 1 acceptance criteria | 1 | Validation | T007 | -- | AC-1 (detect with VAD), AC-2 (detect with silencedetect), AC-3 (process from sidecar), AC-4 (duration mismatch), AC-5 (version check), AC-6 (mutual exclusion), AC-13 (quiet), AC-14 (clean output), AC-15 (backward compat), AC-16 (no debug) all pass with staging videos. | 9/10 ACs pass; AC-1 untestable without torch. |

### Acceptance Criteria (Phase 1)
- [~] AC-1: `--vad --detect` writes sidecar and exits — code path verified, torch not installed for live test
- [x] AC-2: `--detect` (no --vad) writes sidecar with silencedetect backend
- [x] AC-3: `--vad-json` loads sidecar, skips detection, processes video
- [x] AC-4: Duration mismatch truncates intervals and warns
- [x] AC-5: Unsupported version rejects with clear error
- [x] AC-6: `--vad` + `--vad-json` → argparse mutual exclusion error
- [x] AC-13: `--quiet` suppresses verbose output
- [x] AC-14: No visual overlays without `--indicator`
- [x] AC-15: Existing `--vad` workflow unchanged
- [x] AC-16: No `[DEBUG]` output without `--debug-segments`

### Risks (Phase 1)
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Removing `required=True` from -i/-o breaks existing CLI | Medium | High | Validate manually in main(); test backward compat (AC-15) immediately |
| Silencedetect sidecar lacks speech_segments | Low | Low | Invert silence_intervals to compute speech_segments for sidecar completeness |
| Quiet mode accidentally suppresses error messages | Low | Medium | Only suppress informational prints; errors always print to stderr |

---

## Phase 2: Folder Processing

**Objective**: Enable batch processing of all videos in a folder using a shared sidecar, with auto-discovery, skip-existing, and continue-on-failure semantics.

**Testing Approach**: Manual Only
**Mock Usage**: Avoid entirely — real video files only

**Dependencies**: Phase 1 must be complete (T001-T008).

### Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Notes |
|--------|-----|------|----|------|--------------|------------------|------------|-------|
| [x] | T009 | Add `--folder`, `--vad-master`, `--overwrite`, `--extensions` flags to parse_args() | 1 | Core | T008 | /home/jak/github/videospeeder/videospeeder_project/videospeeder.py | All four flags accepted; `--extensions` defaults to `mp4,mkv,mov,avi,webm`; validation: `--folder`+`--vad`-without-`--vad-master` → error | [^7] |
| [x] | T010 | Implement `discover_videos()` helper | 1 | Core | T009 | /home/jak/github/videospeeder/videospeeder_project/videospeeder.py | Returns sorted list of video file paths matching extensions; excludes `.vad.json` files | [^8] |
| [x] | T011 | Implement `discover_sidecar()` helper | 1 | Core | T009 | /home/jak/github/videospeeder/videospeeder_project/videospeeder.py | Exactly one `.vad.json` → return path and print which file found (AC-8); zero → error; multiple → error listing found files (AC-9) | [^8] |
| [x] | T012 | Implement folder processing loop in main() | 3 | Core | T010, T011 | /home/jak/github/videospeeder/videospeeder_project/videospeeder.py | `--folder dir/ --vad-json sidecar -o dir/output/`: processes all videos sequentially using shared sidecar (AC-7). Skips existing outputs unless `--overwrite` (AC-11). Continues on single-file failure with error logged (AC-12). Creates output dir if needed. Prints summary: "Done. N/M videos processed." | [^9] |
| [x] | T013 | Implement `--vad-master` one-liner mode | 2 | Core | T012 | /home/jak/github/videospeeder/videospeeder_project/videospeeder.py | `--folder dir/ --vad --vad-master facecam.mp4 -o dir/output/`: detects on master, writes sidecar, then processes all (AC-10) | [^10] |
| [x] | T014 | Add Justfile recipes for new workflows | 1 | Tooling | T013 | /home/jak/github/videospeeder/Justfile | `just detect`, `just speed-folder`, `just speed-all` recipes work | [^11] |
| [x] | T015 | Update README.md with new flags and multi-angle workflow | 2 | Docs | T013 | /home/jak/github/videospeeder/README.md | New flags documented under Common Options; multi-angle workflow example section added with 2-step and 1-liner variants | [^12] |
| [x] | T016 | End-to-end manual validation of all acceptance criteria | 1 | Validation | T015 | -- | All AC-1 through AC-16 verified with staging videos from `~/VideoMedia/staging` | [^13] |

### Acceptance Criteria (Phase 2)
- [x] AC-7: Folder mode processes all videos with shared sidecar
- [x] AC-8: Folder mode auto-discovers single sidecar
- [x] AC-9: Folder mode errors on ambiguous (multiple) sidecars
- [x] AC-10: `--vad-master` does detect + process in one command
- [x] AC-11: Folder mode skips existing outputs (respects --overwrite)
- [x] AC-12: Folder mode continues on single-file failure
- [x] AC-1–AC-6, AC-13–AC-16: Full regression pass

### Risks (Phase 2)
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| main() becomes unwieldy with folder processing loop | Medium | Medium | Extract `process_folder()` helper; keep main() as thin dispatcher |
| Duration mismatch with short broll clips causes unexpected truncation | Medium | Low | Truncate intervals at video boundary; warn; process what we can |
| Folder contains unexpected non-video files | Low | Low | Extension whitelist; only process matching files |
| Output directory creation fails (permissions) | Low | Medium | Use `os.makedirs(exist_ok=True)`; fail with clear error on permission denied |

---

## Cross-Cutting Concerns

### Security
- File paths validated with `os.path.isfile()` and `os.path.isdir()`
- Sidecar `source.file` stores basename only — no absolute paths (portable, no path traversal)
- No network communication; all processing is local

### Observability
- Default mode: stats table, detection summary, filtergraph preview
- Quiet mode: progress bar + one-line summary only
- Debug mode (`--debug-segments`): per-segment speed details

### Documentation
- **Location**: README.md only (per spec Documentation Strategy)
- **Content**: New flags under Common Options + multi-angle workflow example
- **Audience**: CLI users running videospeeder from terminal

### Complexity Tracking

| Component | CS | Breakdown (S,I,D,N,F,T) | Justification |
|-----------|-----|------------------------|---------------|
| Overall feature | 3 | S=1,I=0,D=1,N=1,F=1,T=1 | Per spec. Multiple flags on one file, new sidecar format, workshopped design, backward compat, manual testing |
| Folder processing loop (T012) | 3 | S=1,I=0,D=0,N=1,F=1,T=0 | New orchestration pattern; error handling; skip/overwrite logic |

---

## Change Footnotes Ledger

[^1]: Task T001 - Removed [DEBUG] prints from main()
  - `file:videospeeder_project/videospeeder.py`

[^2]: Task T002 - Added CLI flags and validation matrix
  - `function:videospeeder_project/videospeeder.py:parse_args`
  - `function:videospeeder_project/videospeeder.py:main`

[^3]: Task T003/T004 - Implemented sidecar read/write functions
  - `function:videospeeder_project/videospeeder.py:silence_intervals_to_speech_segments`
  - `function:videospeeder_project/videospeeder.py:write_vad_metadata`
  - `function:videospeeder_project/videospeeder.py:load_vad_metadata`
  - `function:videospeeder_project/videospeeder.py:truncate_intervals_to_duration`

[^4]: Task T005 - Added detect-only code path in main()
  - `function:videospeeder_project/videospeeder.py:main`

[^5]: Task T006 - Added --vad-json loading code path in main()
  - `function:videospeeder_project/videospeeder.py:main`

[^6]: Task T007 - Added --quiet mode output suppression
  - `function:videospeeder_project/videospeeder.py:main`

[^7]: Task T009 - Added folder CLI flags and validation matrix
  - `function:videospeeder_project/videospeeder.py:parse_args`
  - `function:videospeeder_project/videospeeder.py:main`

[^8]: Task T010/T011 - Implemented discover_videos() and discover_sidecar() helpers
  - `function:videospeeder_project/videospeeder.py:discover_videos`
  - `function:videospeeder_project/videospeeder.py:discover_sidecar`

[^9]: Task T012 - Implemented folder processing loop in main()
  - `function:videospeeder_project/videospeeder.py:main`

[^10]: Task T013 - Implemented --vad-master one-liner mode
  - `function:videospeeder_project/videospeeder.py:main`

[^11]: Task T014 - Added Justfile recipes for folder workflows
  - `file:Justfile`

[^12]: Task T015 - Updated README with folder flags and multi-angle workflow
  - `file:README.md`

[^13]: Task T016 - End-to-end manual validation of all acceptance criteria
  - `file:videospeeder_project/videospeeder.py`

---

**Next steps:**
- **Ready to implement**: `/plan-6-implement-phase --plan "docs/plans/007-vad-first-pass-multi-angle/vad-first-pass-multi-angle-plan.md"` (start with Phase 1)
- **Optional validation**: `/plan-4-complete-the-plan` (recommended for CS-3)
- **Test files**: Staging videos available at `~/VideoMedia/staging`
