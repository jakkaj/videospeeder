# Research Report: VAD First-Pass Detection with Metadata Output & Multi-Angle Support

**Generated**: 2026-02-22
**Research Query**: "New mode using VAD as a first pass, writing metadata file, then speeder reads metadata. Multi-angle folder support."
**Mode**: Pre-Plan
**Location**: docs/plans/007-vad-first-pass-multi-angle/
**FlowSpace**: Not Available
**Findings**: 55+ across 7 subagents + external research

## Executive Summary

### What It Does
VideoSpeeder already has a fully functional Silero VAD integration (`--vad` flag) that detects speech segments, converts them to silence intervals, and feeds them into the existing speed-up pipeline. The user wants to **decouple detection from processing** into two distinct commands: (1) a VAD first-pass that writes a `.vad.json` sidecar file, and (2) the speeder command that reads that file instead of re-running detection. Additionally, multi-angle support would let one VAD pass drive speed-up across multiple camera angles in a folder.

### Business Purpose
Screencast/tutorial creators often record multiple camera angles simultaneously. Running VAD once on the "master" audio track and applying the same speed map to all angles saves significant time and ensures all angles stay perfectly synchronized.

### Key Insights
1. **vad_dump.py is 90% of the first-pass command already** - it runs the full VAD pipeline and outputs JSON with speech segments, silence intervals, and pipeline segments. Fork/extend it for sidecar generation.
2. **Silero VAD on CPU is fast enough** - 15-30 seconds per hour of audio. GPU acceleration provides marginal benefit (2-3x via ONNX) for a task that's already negligible vs encoding time.
3. **The public API surface is clean** - 6 functions exported from videospeeder.py already used by vad_dump.py. Building new commands requires no changes to core detection logic.
4. **Multi-angle requires a new orchestration layer** - current architecture is strictly single-input/single-output per invocation.
5. **Zero test coverage** - any refactoring carries risk without safety net.

### Quick Stats
- **Components**: 3 Python files (videospeeder.py 1132 lines, vad_dump.py 144 lines, transcribe.py 35 lines)
- **Public API functions**: 6 (get_video_duration, detect_speech_segments_silero, normalize_speech_segments, speech_segments_to_silence_intervals, validate_silence_intervals, calculate_segments)
- **Dependencies**: torch + silero-vad (VAD only), tqdm + rich (optional), ffmpeg/ffprobe (required)
- **Test Coverage**: None (manual testing only)
- **Prior Learnings**: 15 relevant discoveries from plan 006-vad

---

## How It Currently Works

### Entry Points
| Entry Point | Type | Location | Purpose |
|------------|------|----------|---------|
| `main()` | CLI | videospeeder.py:958 | Full pipeline: detect + process |
| `vad_dump.py main()` | CLI | vad_dump.py:58 | VAD analysis only (no rendering) |
| `transcribe.py main()` | CLI | transcribe.py:6 | Whisper transcription |

### Core Execution Flow

**Path A: FFmpeg Silencedetect (default)**
```
main() → run_silencedetect() → parse_silencedetect_output() → silence_intervals
```

**Path B: Silero VAD (--vad flag)**
```
main() → detect_speech_segments_silero()
           → stream_audio_pcm_s16le_chunks() [30s chunks, 1s overlap]
           → pcm_s16le_bytes_to_float_tensor()
           → get_speech_timestamps() [Silero model]
       → normalize_speech_segments() [merge gaps ≤0.3s, pad ±0.05s]
       → speech_segments_to_silence_intervals() [invert speech→silence]
       → validate_silence_intervals()
       → silence_intervals
```

**Convergence (both paths):**
```
silence_intervals
  → calculate_segments() [add 1s buffer before non-silent]
  → build_filtergraph() [per-segment trim/speed/indicator/concat]
  → run_ffmpeg_processing() [execute ffmpeg with progress bar]
  → output video
```

### Data Flow
```
Input Video
    │
    ├─ [ffprobe] → Video stats (duration, codec, resolution)
    │
    ├─ [VAD or silencedetect] → Raw detection output
    │       │
    │       ▼
    │   silence_intervals: List[(start: float, end: float)]
    │       │
    │       ▼
    │   calculate_segments() → List[(start, end, "silent"|"non-silent")]
    │       │
    │       ▼
    │   build_filtergraph() → FFmpeg filter_complex string
    │       │
    ├───────┘
    │
    ▼
[FFmpeg Processing] → Output Video
```

### Key Data Structures

**Speech Segments** (from VAD): `List[Tuple[float, float]]` - (start_sec, end_sec)
**Silence Intervals**: `List[Tuple[float, float]]` - (start_sec, end_sec)
**Pipeline Segments**: `List[Tuple[float, float, str]]` - (start, end, "silent"|"non-silent")

All timestamps are **relative to processed region** (0 to analyzed_duration), not absolute file positions.

---

## Architecture & Design

### Component Map

```
videospeeder.py (1132 lines)
├─ Probing: probe_and_print_video_stats(), get_video_duration(), get_video_codec()
├─ CLI: parse_args()
├─ Detection Backend A: run_silencedetect(), parse_silencedetect_output()
├─ Detection Backend B: import_vad_dependencies(), extract_audio_pcm_s16le(),
│                        stream_audio_pcm_s16le_chunks(), pcm_s16le_bytes_to_float_tensor(),
│                        detect_speech_segments_silero()
├─ Normalization: normalize_speech_segments(), speech_segments_to_silence_intervals(),
│                 validate_silence_intervals()
├─ Processing: compute_silent_speed(), calculate_segments(), build_filtergraph()
├─ Execution: run_ffmpeg_processing()
└─ Orchestration: main()

vad_dump.py (144 lines) - Analysis-only command
└─ Imports & calls 6 public functions from videospeeder.py
```

### Design Patterns Identified
1. **Pluggable Detection Backend**: VAD and silencedetect diverge at detection, converge at silence_intervals
2. **Lazy Import**: torch/silero_vad loaded only when --vad is used (import_vad_dependencies())
3. **Graceful Degradation**: tqdm, rich are optional with fallback behavior
4. **Module Reuse**: vad_dump.py demonstrates importing videospeeder as a library
5. **List-Based Command Building**: FFmpeg commands built as Python lists with conditional += segments
6. **Streaming Audio Processing**: 30s chunks with 1s overlap, background stderr draining thread

### System Boundaries
- **Internal**: All processing is local, single-process, sequential
- **External**: FFmpeg/FFprobe via subprocess, Silero VAD model (downloaded/cached on first use)
- **No batch/folder processing** currently exists

---

## Dependencies & Integration

### External Dependencies
| Dependency | Required | Purpose | GPU Relevant |
|------------|----------|---------|-------------|
| ffmpeg | Always | Audio extraction, video processing | NVENC encoding, CUVID decoding |
| ffprobe | Always | Video metadata | No |
| torch | VAD only | Tensor ops, model inference | Could use CUDA but currently CPU |
| silero-vad | VAD only | Speech detection model | CPU only (ONNX path exists) |
| tqdm | Optional | Progress bar | No |
| rich | Optional | Formatted output | No |
| torchaudio | In requirements.txt | **NOT ACTUALLY USED** (vestigial) | N/A |

### Public API (used by vad_dump.py)
1. `get_video_duration(input_file) → float`
2. `detect_speech_segments_silero(input_file, vad_threshold, offset, process_duration) → List[(float, float)]`
3. `normalize_speech_segments(segments, max_end, ...) → List[(float, float)]`
4. `speech_segments_to_silence_intervals(segments, total_duration) → List[(float, float)]`
5. `validate_silence_intervals(intervals, max_end) → None (raises ValueError)`
6. `calculate_segments(intervals, duration, buffer=1.0) → List[(float, float, str)]`

---

## Quality & Testing

### Current State
- **Zero automated tests** - no test files, no CI testing
- **Manual testing only** - hardcoded paths in Makefile, Justfile recipes
- **8 pure functions** that are trivially testable (compute_silent_speed, parse_silencedetect_output, normalize_speech_segments, etc.)
- **10 impure functions** tied to subprocesses and I/O

### Modification Risk Assessment

| Task | Risk | Effort | Notes |
|------|------|--------|-------|
| Add `--vad-output` to write sidecar JSON | LOW | ~30 lines | vad_dump.py already has the pattern |
| Add `--vad-input` to read sidecar JSON | MODERATE | ~40 lines | New code path in main(), needs validation |
| Create standalone `vad-detect` command | LOW | ~20 lines | Fork vad_dump.py, change output to sidecar file |
| Add multi-file folder processing | HIGH | ~200 lines | New orchestration layer, progress aggregation |
| Extract library module | MODERATE | ~200 lines | Move functions, update imports |

### Safe to Modify
- Adding new CLI flags to parse_args()
- Creating new standalone scripts that import videospeeder
- The JSON output format (following vad_dump.py pattern)

### Modify with Caution
- main() function (170 lines, multiple code paths)
- Segment calculation pipeline (buffer logic is subtle)

### Danger Zones
- build_filtergraph() - complex FFmpeg filter syntax, easy to break
- stream_audio_pcm_s16le_chunks() - threading, pipe deadlock prevention
- run_ffmpeg_processing() - progress mapping, codec selection

---

## Prior Learnings (From Plan 006-VAD Implementation)

### PL-01: Chunk Boundary Stitching (CRITICAL)
**Source**: Plan 006-vad, Critical Discovery 02
**Type**: gotcha
**Learning**: Naive chunk concatenation creates false silence gaps at boundaries. Requires 1-second overlap between chunks and post-merge with normalize_speech_segments().
**Action**: Any new VAD command must reuse the existing streaming pipeline, not reimplement it.

### PL-02: Offset/Duration Coordinate Alignment (CRITICAL)
**Source**: Plan 006-vad, Critical Discovery 01
**Type**: gotcha
**Learning**: VAD audio extraction and FFmpeg processing must use identical offset/process-duration. Timestamps are relative to processed region starting at 0.
**Action**: Sidecar metadata must clearly label coordinate system. When applying to multi-angle, all videos must use the same offset/duration.

### PL-03: vad_dump.py as Architecture Template
**Source**: Plan 006-vad, Task T012
**Type**: decision
**Learning**: Separate analysis-only command (vad_dump.py) successfully reuses 6 core functions via module import. Proven pattern for new commands.
**Action**: New first-pass command should follow this exact pattern.

### PL-04: Lazy Import for Heavy Dependencies
**Source**: Plan 006-vad, Task T003
**Type**: decision
**Learning**: import_vad_dependencies() ensures --help works without torch installed. Non-VAD users never load PyTorch.
**Action**: New command must follow same lazy import pattern.

### PL-05: FFmpeg Pipe Deadlock Prevention
**Source**: Plan 006-vad, implementation
**Type**: gotcha
**Learning**: stderr must be drained in background daemon thread when reading stdout from ffmpeg, or pipe fills and blocks.
**Action**: Reuse stream_audio_pcm_s16le_chunks() rather than reimplementing audio extraction.

### PL-06: Silero VAD Parameter Defaults (Research-Backed)
**Source**: Deep research findings 02, 03
**Type**: decision
**Learning**: threshold=0.75 optimized for keyboard noise in screencasts. min_speech_duration_ms=200, speech_pad_ms=50, merge_gap=0.3s.
**Action**: Sidecar file should record all parameters used for reproducibility.

---

## External Research: GPU-Accelerated VAD Libraries (2025-2026)

### Key Findings from Perplexity Deep Research

**Recommendation: Stay with Silero VAD on CPU. GPU acceleration is unnecessary for this use case.**

| Library | TPR@5%FPR | RTF (CPU) | GPU Speed | License | Verdict |
|---------|-----------|-----------|-----------|---------|---------|
| **Silero VAD** | 87.7% | 0.004 (15s/hr) | 2-3x via ONNX | MIT | **Best choice** |
| pyannote-audio | ~90% | 0.025 | 2.5% RTF on GPU | MIT | Overkill (speaker diarization) |
| WebRTC VAD | 50% | 0.0003 | N/A | BSD | Too inaccurate |
| NVIDIA NeMo | ~90% | Fast on GPU | Native TensorRT | Apache 2.0 | Too complex for pure VAD |
| Cobra VAD | 98.9% | 0.005 | N/A | **Commercial** | Best accuracy, but paid |
| Whisper-based | N/A | Very slow | Moderate | MIT | Wrong tool for the job |

**Why GPU acceleration doesn't matter here:**
- Silero VAD processes 1 hour of audio in **15 seconds on CPU**
- A 2-hour screencast takes ~30 seconds for VAD analysis
- Video encoding (the next step) takes **minutes to hours**
- GPU acceleration would save ~20 seconds on a 2-hour video - imperceptible vs total workflow time
- Adding ONNX Runtime + CUDA complexity for marginal gain is not worth it

**If GPU acceleration is ever needed** (batch processing 100+ videos):
- Export Silero to ONNX format
- Use onnxruntime-gpu with CUDAExecutionProvider
- Expect 2-3x speedup (TensorRT has Int32/Int64 type mismatch issues with Silero exports)

**Screencast-specific accuracy notes:**
- Silero at threshold=0.75 handles keyboard/mouse noise well
- For heavy mechanical keyboard typing, raise to 0.80-0.85
- 87.7% TPR means ~1 in 8 speech frames missed at 5% FPR
- Adequate for silence removal (missed frames are at speech boundaries, caught by padding)

---

## Modification Considerations for New Feature

### Proposed Architecture: Two-Command Workflow

```
Command 1: vad-detect (first pass)
─────────────────────────────────
$ python vad_detect.py -i recording.mp4
  → Runs VAD pipeline
  → Writes recording.vad.json (sidecar next to video)

Command 2: videospeeder (processing, existing + new flag)
─────────────────────────────────
$ python videospeeder.py -i recording.mp4 -o fast.mp4 --vad-metadata recording.vad.json
  → Reads sidecar instead of running detection
  → Proceeds with existing segment→filtergraph→ffmpeg pipeline

Multi-angle workflow:
─────────────────────────────────
$ python vad_detect.py -i angle1.mp4                           # VAD on master audio
$ python videospeeder.py -i angle1.mp4 -o angle1_fast.mp4 --vad-metadata angle1.vad.json
$ python videospeeder.py -i angle2.mp4 -o angle2_fast.mp4 --vad-metadata angle1.vad.json  # Same metadata!
$ python videospeeder.py -i angle3.mp4 -o angle3_fast.mp4 --vad-metadata angle1.vad.json
```

### Sidecar JSON Schema (extending vad_dump.py format)

```json
{
  "version": 1,
  "generator": "videospeeder-vad",
  "generated_at": "2026-02-22T10:30:00Z",
  "source": {
    "input": "recording.mp4",
    "duration": 3600.5,
    "offset": 0.0,
    "process_duration": null,
    "analyzed_duration": 3600.5
  },
  "vad_params": {
    "backend": "silero",
    "threshold": 0.75,
    "min_speech_duration_ms": 200,
    "min_silence_duration_ms": 100,
    "speech_pad_ms": 50,
    "merge_gap_seconds": 0.3,
    "pad_seconds": 0.05
  },
  "speech_segments": [
    {"start": 1.23, "end": 4.56},
    {"start": 8.90, "end": 12.34}
  ],
  "silence_intervals": [
    {"start": 0.0, "end": 1.23},
    {"start": 4.56, "end": 8.90},
    {"start": 12.34, "end": 3600.5}
  ]
}
```

**Note**: Pipeline segments (with buffer) are NOT stored - they're computed by videospeeder.py at processing time using calculate_segments(). This allows buffer_duration to be tuned without re-running VAD.

### Multi-Angle Considerations

1. **Duration matching**: All angle videos must have same or longer duration than VAD source. Shorter angles should be padded or truncated.
2. **Offset handling**: If angles have different start times, user provides per-angle offset.
3. **Batch command** (optional future): `python videospeeder.py --folder angles/ --vad-metadata master.vad.json -o output/` processes all videos in folder.
4. **Sync verification**: Compare durations between VAD source and target video, warn if mismatch > 1 second.

### What Changes vs What Stays

**New files:**
- `vad_detect.py` - Standalone first-pass VAD command (fork of vad_dump.py)

**Modified files:**
- `videospeeder.py` - Add `--vad-metadata` flag to parse_args(), add JSON loading branch in main()

**Untouched:**
- All detection functions (detect_speech_segments_silero, etc.)
- All processing functions (calculate_segments, build_filtergraph, run_ffmpeg_processing)
- transcribe.py

---

## External Research Opportunities

### Research Opportunity 1: Multi-Angle Video Sync Verification

**Why Needed**: Multi-angle workflows need to verify that all camera files represent the same recording session. Different cameras may have slightly different start times, frame rates, or durations.
**Impact on Plan**: Determines whether we need audio fingerprinting or simpler duration-based checks.

**Ready-to-use prompt:**
```
/deepresearch "How do professional video editors verify multi-angle sync for videos recorded on separate cameras? Methods for detecting time offset between two video files from same recording session. Audio fingerprinting approaches (chromaprint, dejavu) vs timecode-based sync. Python libraries for audio fingerprinting. Accuracy requirements for frame-level sync."
```

**Results location**: Save to `docs/plans/007-vad-first-pass-multi-angle/external-research/multi-angle-sync.md`

---

## Appendix: File Inventory

### Core Files
| File | Purpose | Lines |
|------|---------|-------|
| videospeeder_project/videospeeder.py | Main pipeline (detect + process) | 1132 |
| videospeeder_project/vad_dump.py | VAD analysis/dump utility | 144 |
| videospeeder_project/transcribe.py | Whisper transcription | 35 |
| videospeeder_project/requirements.txt | Python dependencies | 6 |
| videospeeder_project/Makefile | Build/test shortcuts | ~40 |
| Justfile | Task runner recipes | 73 |

### Documentation
| File | Purpose |
|------|---------|
| docs/plans/006-vad/ | Original VAD implementation plan + deep research |
| docs/rules-idioms-architecture/ | Architecture, rules, idioms, constitution |
| docs/plans/5-mac-gpu-acceleration/ | GPU acceleration planning |

---

## Next Steps

**No external research strictly required** (GPU VAD research already completed above).

**Optional external research:**
- Multi-angle sync verification (Research Opportunity 1 above)

**Recommended next step:**
- Run `/plan-1b-specify` to create the feature specification
- Key decisions to capture in spec:
  1. Sidecar file format and naming convention
  2. Whether `vad_detect.py` is a new file or extension of `vad_dump.py`
  3. Multi-angle folder mode scope (simple loop vs batch command)
  4. Whether to add tests as part of this feature

---

**Research Complete**: 2026-02-22
**Report Location**: docs/plans/007-vad-first-pass-multi-angle/research-dossier.md
