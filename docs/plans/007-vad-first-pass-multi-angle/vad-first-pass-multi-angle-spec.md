# VAD First-Pass Detection with Multi-Angle Support

**Mode**: Simple
**File Management**: Legacy

## Research Context

This specification incorporates findings from `research-dossier.md` and the CLI workflow workshop (`workshops/workflow-and-cli-design.md`).

- **Components affected**: `videospeeder.py` (parse_args, main), Justfile
- **Critical dependencies**: Existing Silero VAD pipeline (6 public API functions), FFmpeg/FFprobe
- **Modification risks**: main() is 170 lines with multiple code paths; zero test coverage; build_filtergraph() is fragile. All new functionality adds to videospeeder.py without touching detection or processing internals.
- **Key prior learning**: vad_dump.py already demonstrates the module-reuse pattern for building new commands on existing functions (PL-03)
- **Links**: See `research-dossier.md` for full analysis, `workshops/workflow-and-cli-design.md` for detailed CLI design

---

## Summary

**WHAT**: Decouple voice activity detection from video processing into a two-pass workflow. A "detect" pass analyzes audio and writes a `.vad.json` sidecar file. A "process" pass reads that sidecar and applies speed-ups without re-running detection. A folder mode applies one detection result to multiple camera angles simultaneously.

**WHY**: Content creators recording multi-angle sessions (face cam + screen capture + overhead) need all angles sped up identically so they stay in sync when layered in an NLE. Running VAD once on the best audio track and applying the result to every angle saves processing time and guarantees synchronization. Separating detection from processing also lets users inspect and iterate on VAD results before committing to encoding.

---

## Goals

1. **Two-pass workflow**: Users can run detection separately from processing, inspecting results before committing to a long encode.
2. **Sidecar metadata file**: Detection results are persisted as a `.vad.json` file next to the source video, enabling reuse across multiple processing runs and multiple input files.
3. **Multi-angle folder processing**: A single command processes all video files in a directory using one shared sidecar, producing identically-timed output files.
4. **Clean output by default**: Output videos have zero visual modifications beyond speed changes unless the user explicitly opts in (e.g., `--indicator`). Terminal output has a quiet mode for scripting.
5. **Backward compatibility**: Existing single-file `--vad` workflow continues to work unchanged. No breaking changes to current CLI surface.
6. **Detection-backend agnostic sidecar**: The sidecar format stores silence intervals regardless of whether they came from Silero VAD or FFmpeg silencedetect, enabling two-pass workflow for both detection backends.

---

## Non-Goals

- **Audio fingerprint-based sync verification** between camera angles — sync is the NLE's job
- **Per-angle time offset correction** — cameras start within 1-2 seconds of each other; fine-grained alignment belongs in the editor
- **Parallel video encoding** — process sequentially; FFmpeg already uses multiple CPU cores
- **GUI or drag-and-drop interface** — CLI tool stays CLI
- **New detection backends** (pyannote, NeMo, etc.) — Silero VAD on CPU is sufficient (15s/hr processing, 87.7% TPR)
- **GPU acceleration for VAD** — marginal benefit vs already-fast CPU inference; not worth the ONNX/TensorRT complexity
- **Project/workspace files** — the folder IS the project, the sidecar IS the metadata

---

## Complexity

- **Score**: CS-3 (medium)
- **Breakdown**: S=1, I=0, D=1, N=1, F=1, T=1 (Total P=5)
- **Confidence**: 0.85
- **Assumptions**:
  - Existing detection pipeline (detect_speech_segments_silero, run_silencedetect, normalize, validate) remains untouched
  - Workshop resolved most design questions; remaining open questions (Q4, Q5) are low-impact
  - No new external dependencies needed
- **Dependencies**:
  - FFmpeg 4.x+ (existing)
  - Python 3.6+ (existing)
  - torch + silero-vad for VAD mode (existing, optional)
- **Risks**:
  - main() complexity increases with new code paths (already 170 lines)
  - Duration mismatch edge cases in multi-angle may surface unexpected behavior
  - Zero test coverage means regression risk on existing functionality
- **Phases**:
  - Phase 1: Two-pass workflow + output cleanup (`--detect`, `--vad-json`, `--quiet`, debug print cleanup)
  - Phase 2: Folder processing (`--folder`, `--vad-master`, sidecar auto-discovery, duration mismatch handling)

**Breakdown rationale:**
| Factor | Score | Rationale |
|--------|-------|-----------|
| Surface Area (S) | 1 | Multiple additions to videospeeder.py (new flags, load function, folder loop, quiet mode) + Justfile |
| Integration (I) | 0 | No new external dependencies; reuses existing Silero VAD and FFmpeg |
| Data/State (D) | 1 | New `.vad.json` sidecar file format with versioned schema |
| Novelty (N) | 1 | Well-workshopped design but folder batch processing is new territory for this codebase |
| Non-Functional (F) | 1 | Backward compatibility required; duration mismatch handling needed for robustness |
| Testing (T) | 1 | Integration testing with real video files; multi-angle scenarios; backward compat verification |

---

## Acceptance Criteria

### AC-1: Detect-only mode writes sidecar and exits

**Given** a video file with audio
**When** the user runs `videospeeder.py -i video.mp4 --vad --detect`
**Then** a file `video.vad.json` is created next to the input video containing:
- `version` field set to `1`
- `source.file` matching the input filename (basename only)
- `detection.backend` set to `"silero"`
- `detection.analyzed_duration` matching the video duration
- `speech_segments` as array of `[start, end]` pairs
- `silence_intervals` as array of `[start, end]` pairs
- All detection parameters recorded under `detection.params`
And the program exits without running video processing.

### AC-2: Detect-only mode works with silencedetect backend

**Given** a video file with audio
**When** the user runs `videospeeder.py -i video.mp4 --detect` (no `--vad` flag)
**Then** a file `video.vad.json` is created with `detection.backend` set to `"silencedetect"` and silence intervals from the FFmpeg silencedetect filter.

### AC-3: Process from sidecar skips detection

**Given** a valid `.vad.json` sidecar file
**When** the user runs `videospeeder.py -i video.mp4 -o out.mp4 --vad-json video.vad.json`
**Then** no silence detection or VAD analysis is performed, silence intervals are loaded from the sidecar, and the video is processed using those intervals.
And the terminal output confirms: `Loading VAD metadata from video.vad.json (skipping detection)`.

### AC-4: Sidecar with mismatched duration still processes

**Given** a sidecar analyzing 3842.5s of audio and a video file of 3841.8s
**When** the user runs `videospeeder.py -i shorter.mp4 -o out.mp4 --vad-json master.vad.json`
**Then** silence intervals are truncated to the video's duration, a warning is printed about the mismatch, and processing completes successfully.

### AC-5: Sidecar version check

**Given** a `.vad.json` file with `"version": 99`
**When** the user attempts to load it with `--vad-json`
**Then** an error is printed: `Unsupported vad.json version: 99` and the program exits with non-zero status.

### AC-6: Mutually exclusive detection flags

**When** the user passes both `--vad` and `--vad-json path`
**Then** argparse reports an error about mutually exclusive options before any processing begins.

### AC-7: Folder mode processes all videos

**Given** a folder containing `a.mp4`, `b.mp4`, `c.mkv`, and `a.vad.json`
**When** the user runs `videospeeder.py --folder dir/ --vad-json dir/a.vad.json -o dir/output/`
**Then** all three video files are processed sequentially using the same sidecar, output files are written to `dir/output/` with original filenames, and a summary reports how many videos succeeded.

### AC-8: Folder mode auto-discovers sidecar

**Given** a folder containing `facecam.mp4`, `screen.mp4`, and exactly one `.vad.json` file
**When** the user runs `videospeeder.py --folder dir/ -o dir/output/` (no `--vad-json`)
**Then** the tool auto-discovers and uses the single `.vad.json` file, printing which file it found.

### AC-9: Folder mode errors on ambiguous sidecar

**Given** a folder containing two `.vad.json` files
**When** the user runs `--folder dir/` without `--vad-json`
**Then** an error lists the found sidecar files and instructs the user to specify `--vad-json`.

### AC-10: Folder mode with --vad-master does detect + process

**Given** a folder with `facecam.mp4`, `screen.mp4`, `overhead.mp4`
**When** the user runs `--folder dir/ --vad --vad-master facecam.mp4 -o dir/output/`
**Then** VAD detection runs on `facecam.mp4`, a sidecar `facecam.vad.json` is written, and all three videos are processed using that sidecar.

### AC-11: Folder mode skips existing outputs

**Given** `dir/output/facecam.mp4` already exists
**When** the user runs `--folder dir/ --vad-json dir/a.vad.json -o dir/output/`
**Then** `facecam.mp4` is skipped with a message, other videos are processed.
**When** `--overwrite` is also passed, `facecam.mp4` is re-processed.

### AC-12: Folder mode continues on single-file failure

**Given** one video in the folder is corrupted
**When** folder processing encounters an FFmpeg error on that file
**Then** the error is logged, processing continues to the next file, and the final summary reports the failure.

### AC-13: Quiet mode suppresses verbose output

**When** the user passes `--quiet`
**Then** no video stats table, no silence interval list, no filtergraph preview, and no debug output are printed. Only the progress bar and a final summary line appear.

### AC-14: Clean video output by default

**When** the user processes a video without passing `--indicator`
**Then** the output video contains zero visual overlays — only speed adjustments via `setpts`/`atempo` filters. The video frames are unmodified during non-silent segments.

### AC-15: Backward compatibility preserved

**When** the user runs the exact command `videospeeder.py -i in.mp4 -o out.mp4 --vad`
**Then** behavior is identical to the current version: detection and processing happen in one pass with no sidecar written.

### AC-16: Debug print cleanup

**When** the user runs any command without `--debug-segments`
**Then** no `[DEBUG]` prefixed lines appear in the output. Development-time debug prints are removed from `main()`.

---

## Risks & Assumptions

### Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| main() becomes more complex with new code paths | Harder to maintain, higher bug risk | Keep new paths simple; extract helper functions (load_vad_metadata, process_folder) |
| Duration mismatch causes unexpected segment truncation | Silent segments cut incorrectly at video boundary | Truncate intervals at video duration; validate after truncation; warn user |
| No test coverage means regressions go undetected | Existing --vad or silencedetect behavior breaks | Manual testing with real samples before/after; consider adding unit tests for pure functions |
| Sidecar schema needs future changes | Existing .vad.json files become incompatible | Version field in schema; loader checks version; clear error message |
| Folder mode processes unintended files | User has non-video files with video extensions | Extension whitelist; show file list and confirm before processing |

### Assumptions

- All camera angles from a session have approximately the same duration (within seconds)
- Users accept that sync precision is limited to what the NLE provides — VideoSpeeder applies identical speed maps but doesn't time-align source files
- The existing silencedetect and VAD detection functions remain unchanged and correct
- FFmpeg handles all video codec variations for folder processing (same encoder logic per file)
- Users have sufficient disk space for output files alongside originals

---

## Open Questions

### OQ-1: Should `--detect` require `--vad`, or work with silencedetect too?

**Resolved in workshop (Q4)**: Support both backends. The sidecar is detection-backend agnostic — it stores silence intervals regardless of source. `--detect` without `--vad` uses silencedetect; `--vad --detect` uses Silero VAD. Captured in AC-2.

### OQ-2: Per-angle offset for multi-angle sync?

**Deferred (workshop Q5)**: Option A — ignore for v1. Camera sync drift of 1-2 seconds is acceptable for speed-up purposes. Fine-grained alignment belongs in the NLE. May revisit in a future plan if users request it.

### OQ-3: Should `--folder` require confirmation before processing?

**Resolved (clarify session)**: Option C — never prompt. `--folder` starts processing immediately. No interactive confirmation. Simplest for scripting and batch use. Duration mismatches are logged as warnings but don't block.

---

## ADR Seeds (Optional)

### ADR-1: Sidecar File Format

- **Decision Drivers**: Must be human-readable, parseable without special libraries, versionable, portable (no absolute paths)
- **Candidate Alternatives**:
  - A) JSON with version field (chosen in workshop — simple, standard, inspectable)
  - B) YAML (more readable but adds dependency)
  - C) Binary/protobuf (compact but not inspectable)
- **Stakeholders**: End users (inspect/debug), VideoSpeeder CLI (read/write)

### ADR-2: Single Command with Flags vs Subcommands

- **Decision Drivers**: Learning curve, composability, backward compatibility, discoverability
- **Candidate Alternatives**:
  - A) Flags on existing command (`--detect`, `--vad-json`, `--folder`) — chosen in workshop
  - B) Subcommands (`videospeeder detect ...`, `videospeeder process ...`, `videospeeder batch ...`)
  - C) Separate scripts (`vad_detect.py`, keep `videospeeder.py`)
- **Stakeholders**: End users, maintainers

---

## Workshop Opportunities

Workshops already completed for this spec:

| Topic | Type | Status | Document |
|-------|------|--------|----------|
| Workflow & CLI Design | CLI Flow + Integration Pattern | Complete | `workshops/workflow-and-cli-design.md` |

No additional workshops needed — the completed workshop covers CLI flows, sidecar format, folder semantics, duration mismatch handling, and output control in detail.

---

## Unresolved Research

### Multi-Angle Video Sync Verification

**Topic**: Identified in research-dossier.md as Research Opportunity 1 — methods for verifying sync between camera angles from separate recording devices.

**Impact**: Low impact on this spec. The decision to defer per-angle sync to the NLE (OQ-2) means this research is not blocking. If users later request automatic sync detection, this would inform a separate plan.

**Recommendation**: Skip for now. Revisit if user feedback requests automatic sync.

---

## Testing Strategy

- **Approach**: Manual Only
- **Rationale**: No TDD, no fakes. Verify with real video files and manual inspection.
- **Focus Areas**: Sidecar write/read round-trip, folder discovery, duration mismatch handling, backward compat with existing `--vad` flag
- **Excluded**: No unit tests, no mocks, no test fixtures
- **Mock Usage**: Avoid mocks entirely — real data/fixtures only
- **Verification**: Run each AC manually with sample video files; visual/terminal output inspection

---

## Documentation Strategy

- **Location**: README.md only
- **Rationale**: New flags and multi-angle workflow examples belong alongside existing usage docs in README
- **Target Audience**: End users running videospeeder from the command line
- **Content**: Add new flags to Common Options, add multi-angle workflow example section
- **Maintenance**: Update README when flags change

---

## Clarifications

### Session 2026-02-22

| # | Question | Answer | Spec Section Updated |
|---|----------|--------|---------------------|
| Q1 | Workflow mode | **Simple** — lite mode, single-phase plan | Header (Mode: Simple) |
| Q2 | Testing approach | **Manual Only** — no TDD, no fakes | Testing Strategy (new section) |
| Q3 | Mock/stub policy | **Avoid entirely** — real data only | Testing Strategy (Mock Usage) |
| Q4 | Folder confirmation | **C) Never** — just process, no prompts | OQ-3 resolved |
| Q5 | Documentation location | **A) README.md only** | Documentation Strategy (new section) |

---

*Spec clarified and ready for architecture. Next: `/plan-3-architect`*
