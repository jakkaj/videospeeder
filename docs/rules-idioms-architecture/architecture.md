# VideoSpeeder Architecture

This document describes the high-level architecture, system boundaries, and interaction contracts for the VideoSpeeder project.

See also:
- [Constitution](../rules/constitution.md) - Guiding principles
- [Rules](rules.md) - Enforceable standards
- [Idioms](idioms.md) - Patterns and examples

---

## System Overview

VideoSpeeder is a **command-line video processing tool** that orchestrates FFmpeg to intelligently modify video playback speed based on audio characteristics.

### Design Philosophy

**Single Responsibility:** VideoSpeeder focuses exclusively on silence-based speed adjustment. It does not:
- Transcode videos (delegates to FFmpeg)
- Edit video content (cuts, crops, overlays beyond speed indicators)
- Manage video libraries or batch processing queues
- Provide GUI or web interface

**Composition over Ownership:** VideoSpeeder composes FFmpeg's capabilities rather than reimplementing video processing. The tool:
- Generates FFmpeg command strings
- Executes FFmpeg as subprocess
- Parses FFmpeg output
- Does NOT manipulate video data directly

**Technology-Agnostic Core:** While currently implemented in Python 3.x:
- Core algorithms (silence detection, speed calculation) are language-independent
- Could be reimplemented in any language with subprocess capabilities
- FFmpeg is the only hard dependency for video processing

---

## System Components

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         VideoSpeeder CLI                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────┐│
│  │  Argument       │  │  Video Stats &   │  │  Progress    ││
│  │  Parser         │──│  Validation      │  │  Reporting   ││
│  └─────────────────┘  └──────────────────┘  └──────────────┘│
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │          Silence Detection & Analysis Pipeline           │ │
│  │  ┌──────────────┐  ┌─────────────┐  ┌────────────────┐ │ │
│  │  │ FFprobe      │  │ Silencedetect│  │ Segment        │ │ │
│  │  │ Executor     │─▶│ Executor    │─▶│ Calculator     │ │ │
│  │  └──────────────┘  └─────────────┘  └────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Filter Graph Generation                     │ │
│  │  ┌──────────────┐  ┌─────────────┐  ┌────────────────┐ │ │
│  │  │ Speed        │  │ Visual      │  │ Filter Graph   │ │ │
│  │  │ Calculator   │─▶│ Indicator   │─▶│ Builder        │ │ │
│  │  └──────────────┘  │ Generator   │  └────────────────┘ │ │
│  │                    └─────────────┘                      │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Video Processing Execution                  │ │
│  │  ┌──────────────┐  ┌─────────────┐  ┌────────────────┐ │ │
│  │  │ Codec        │  │ Encoder     │  │ FFmpeg         │ │ │
│  │  │ Detector     │─▶│ Selector    │─▶│ Executor       │ │ │
│  │  └──────────────┘  └─────────────┘  └────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
└───────────────────────────┬───────────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │         FFmpeg Suite        │
              ├─────────────────────────────┤
              │  • ffprobe (analysis)       │
              │  • ffmpeg (processing)      │
              │  • silencedetect filter     │
              │  • Video/Audio filters      │
              │  • Encoders/Decoders        │
              │  • GPU Acceleration (opt)   │
              └─────────────────────────────┘
```

### Component Responsibilities

#### 1. Argument Parser
**Purpose:** Parse and validate command-line arguments

**Inputs:** Command-line arguments
**Outputs:** Validated configuration object

**Contracts:**
- MUST validate required arguments exist
- MUST apply default values for optional arguments
- MUST validate parameter ranges (threshold, duration)
- MAY provide usage help and examples

#### 2. Video Stats & Validation
**Purpose:** Extract video metadata and validate file integrity

**Inputs:** Input video file path
**Outputs:** Video metadata (duration, resolution, codec, fps, bitrate)

**Contracts:**
- MUST verify file exists and is readable
- MUST execute ffprobe to extract metadata
- MUST parse JSON output from ffprobe
- MUST exit with error if file unreadable or corrupt

**Dependencies:** FFprobe (external)

#### 3. Silence Detection & Analysis Pipeline

##### 3a. FFprobe Executor
**Purpose:** Execute ffprobe to gather video information

**Inputs:** Video file path
**Outputs:** Video metadata as structured data

**Contracts:**
- MUST execute `ffprobe -v quiet -print_format json -show_format -show_streams`
- MUST parse JSON output
- MUST handle subprocess errors gracefully

##### 3b. Silencedetect Executor
**Purpose:** Run FFmpeg silencedetect filter to identify silent segments

**Inputs:** Video file, threshold (dB), minimum duration (seconds)
**Outputs:** List of (start_time, end_time) tuples for silent intervals

**Contracts:**
- MUST execute `ffmpeg -i input -af silencedetect=n=<threshold>dB:d=<duration> -f null -`
- MUST parse stderr output for silence_start and silence_end markers
- MUST return empty list if no silence detected
- MAY support offset and process-duration for partial processing

##### 3c. Segment Calculator
**Purpose:** Convert silence intervals into processing segments

**Inputs:** Silence intervals, total video duration, buffer duration
**Outputs:** List of (start, end, type) tuples where type is "silent" or "non-silent"

**Contracts:**
- MUST create non-silent segments for gaps between silences
- MUST add buffer before non-silent segments (default 1 second)
- MUST handle edge cases (no silence, all silence, start/end boundaries)
- MUST ensure segments cover entire video duration without gaps or overlaps

#### 4. Filter Graph Generation

##### 4a. Speed Calculator
**Purpose:** Determine speed multiplier for each segment

**Inputs:** Segment duration, segment type
**Outputs:** Speed multiplier (float)

**Contracts:**
- MUST return 1.0 for non-silent segments (normal speed)
- MUST return 4.0 for silent segments ≤ 10 seconds
- MUST return variable speed for silent segments > 10 seconds (compress to ~4 seconds)
- MUST cap maximum speed at 1000x for video
- MUST calculate chainable atempo filters for audio (max 2.0x per filter)

##### 4b. Visual Indicator Generator
**Purpose:** Create FFmpeg filter string for speed indicator overlay

**Inputs:** Segment bounds, speed multiplier, indicator enabled flag
**Outputs:** FFmpeg filter string for overlay (or empty if disabled)

**Contracts:**
- MUST overlay semi-transparent box at top-left
- MUST overlay fastforward.png icon
- MUST overlay speed text (e.g., "4x")
- MUST apply overlays BEFORE speed adjustment (prevents distortion)
- MUST return empty string if indicator disabled

##### 4c. Filter Graph Builder
**Purpose:** Construct complete FFmpeg filter_complex string

**Inputs:** List of segments with speed and indicator settings
**Outputs:** Complete FFmpeg filter_complex string

**Contracts:**
- MUST generate per-segment filters (trim, speed adjust, indicator)
- MUST concatenate all segments into single output
- MUST handle video and audio streams separately
- MUST reset PTS (presentation timestamp) after trim operations
- MUST produce valid FFmpeg filter syntax

#### 5. Video Processing Execution

##### 5a. Codec Detector
**Purpose:** Identify input video codec

**Inputs:** Video file path
**Outputs:** Codec string (h264, hevc, av1, etc.)

**Contracts:**
- MUST execute ffprobe to query codec_name
- MUST return standardized codec identifier
- MUST handle unknown codecs gracefully

##### 5b. Encoder Selector
**Purpose:** Choose appropriate encoder based on codec and GPU settings

**Inputs:** Codec, GPU enabled flag, GPU decode flag
**Outputs:** Encoder name, decoder name (if GPU decode enabled)

**Contracts:**
- MUST map codecs to encoders:
  - H.264: h264_nvenc (GPU) or libx264 (CPU)
  - HEVC: hevc_nvenc (GPU) or libx265 (CPU)
  - AV1: av1_nvenc (GPU) or libaom-av1 (CPU)
- MUST select decoder if GPU decode enabled:
  - H.264: h264_cuvid
  - HEVC: hevc_cuvid
- MUST fall back to CPU encoder if GPU unavailable

##### 5c. FFmpeg Executor
**Purpose:** Execute final FFmpeg processing command with progress tracking

**Inputs:** Input file, output file, filter graph, encoder, decoder
**Outputs:** Processed video file

**Contracts:**
- MUST construct FFmpeg command with all parameters
- MUST use `-filter_complex` for complex filter graph
- MUST use `-progress pipe:1` for progress tracking
- MUST parse progress output and update tqdm progress bar
- MUST capture stderr for error reporting
- MUST exit with non-zero on FFmpeg failure
- MUST report processing statistics on completion

**Dependencies:** FFmpeg (external)

#### 6. Progress Reporting
**Purpose:** Provide real-time feedback to user

**Inputs:** Processing events, progress updates
**Outputs:** Terminal output (progress bars, statistics)

**Contracts:**
- MUST show video statistics before processing (duration, resolution, codec)
- MUST show progress bar during processing (with percentage and ETA)
- MUST show final statistics after processing (time saved, output size)
- SHOULD use rich library for formatted tables
- SHOULD use tqdm for progress bars

---

## Data Flow

### High-Level Processing Flow

```
Input Video
    │
    ├─▶ [Video Stats] ──▶ Display stats table
    │
    ├─▶ [Silencedetect] ──▶ Silence intervals
    │                          │
    │                          ▼
    │                    [Segment Calculator] ──▶ Segments with types
    │                                                   │
    │                                                   ▼
    │                                             [Speed Calculator]
    │                                                   │
    │                                                   ▼
    │                                             Speed multipliers
    │                                                   │
    │                                                   ▼
    │                                          [Filter Graph Builder]
    │                                                   │
    ├───────────────────────────────────────────────────┘
    │
    ▼
[FFmpeg Processing] ──▶ Progress updates ──▶ Progress bar
    │
    ▼
Output Video
```

### Data Structures

#### Silence Interval
```python
SilenceInterval = Tuple[float, float]  # (start_time, end_time) in seconds
```

#### Video Segment
```python
VideoSegment = Tuple[float, float, str]  # (start_time, end_time, type)
# type: "silent" or "non-silent"
```

#### Video Metadata
```python
VideoMetadata = {
    'duration': float,      # seconds
    'width': int,           # pixels
    'height': int,          # pixels
    'codec': str,           # codec name
    'fps': float,           # frames per second
    'bitrate': int          # bits per second
}
```

---

## External Dependencies

### Required Dependencies

#### FFmpeg Suite (External Binary)
**Purpose:** Video processing engine

**Components:**
- `ffmpeg` - Video processing and encoding
- `ffprobe` - Video metadata extraction and analysis

**Contract:**
- MUST be FFmpeg version 4.x or later
- MUST support silencedetect audio filter
- MUST support filter_complex
- MUST support progress output format

**Optional Components:**
- `NVIDIA NVENC` - GPU hardware encoding (H.264, HEVC, AV1)
- `NVIDIA CUVID/NVDEC` - GPU hardware decoding

### Python Dependencies

#### tqdm (PyPI Package)
**Purpose:** Progress bars

**Version:** >= 4.0
**Contract:** Standard tqdm progress bar interface

#### rich (PyPI Package)
**Purpose:** Formatted terminal output

**Version:** Latest stable
**Contract:** Console, Table APIs for formatted output

#### openai-whisper (PyPI Package) - Optional
**Purpose:** Speech-to-text transcription for VTT subtitles

**Usage:** Separate script (`transcribe.py`), not core functionality
**Contract:** Whisper model API for transcription

---

## Integration Points

### FFmpeg Integration

**Interaction Model:** Subprocess execution

**VideoSpeeder → FFmpeg:**
- Constructs command-line arguments
- Executes as subprocess
- Captures stdout (progress) and stderr (errors)
- Parses text output

**FFmpeg → VideoSpeeder:**
- Writes progress to stdout (`out_time_ms=<value>`)
- Writes errors to stderr (plain text)
- Returns exit code (0 = success, non-zero = error)

**Error Handling:**
- FFmpeg errors reported to user with full stderr output
- Non-zero exit codes trigger program termination
- Missing FFmpeg binaries detected at startup

### File System Integration

**Input:**
- MUST be able to read video files from local filesystem
- SHOULD support all FFmpeg-supported video formats
- File paths MAY be relative or absolute

**Output:**
- MUST write output video to local filesystem
- MUST prompt before overwriting existing files (optional: force flag)
- Output format determined by file extension

**Assets:**
- Visual indicator assets (fastforward.png, fastforward.svg)
- MUST be co-located with script or in known path
- SHOULD embed or inline to avoid external dependencies (future)

### GPU Integration (Optional)

**NVIDIA NVENC/CUVID:**
- Detected at runtime via FFmpeg encoder query
- Enabled via `--gpu` and `--gpu-decode` flags
- Graceful fallback to CPU if unavailable

**Contract:**
- MUST check encoder availability before use
- MUST provide informative error if GPU requested but unavailable
- SHOULD warn user if GPU available but not requested

---

## Boundaries and Constraints

### What VideoSpeeder Does

**In Scope:**
- Silence detection based on audio amplitude
- Dynamic speed calculation
- FFmpeg filter graph generation
- Visual speed indicators
- GPU acceleration orchestration
- Progress reporting

### What VideoSpeeder Does NOT Do

**Out of Scope:**
- Video transcoding (delegated to FFmpeg)
- Batch processing (one video at a time)
- Video editing beyond speed adjustment (cuts, crops, color correction)
- Audio processing beyond speed (normalization, effects)
- Cloud processing or distributed compute
- User authentication or authorization
- Configuration file management (may be added, see idioms CS-3 example)
- Plugin or extension system

### Architectural Constraints

**Technology:**
- MUST support Python 3.6+ (3.9+ recommended)
- MUST run on macOS, Linux (Windows support optional)
- MUST use FFmpeg as processing engine (no alternative backends)

**Performance:**
- SHOULD process video at reasonable speed (not real-time, depends on hardware)
- GPU acceleration SHOULD provide significant speedup (2-5x typical)
- Memory usage SHOULD be O(n) where n = number of segments (not video size)

**Security:**
- Input validation for file paths (prevent path traversal)
- No execution of user-provided code
- No network communication (local tool only)

---

## Anti-Patterns

### Code Organization

**AVOID:**
- Monolithic main() function with all logic
- Global state or mutable globals
- Tight coupling between FFmpeg command generation and execution

**PREFER:**
- Modular functions with single responsibilities
- Pure functions for calculations (speed, segments)
- Dependency injection for subprocess execution (testability)

### Error Handling

**AVOID:**
- Silent failures (catch without reporting)
- Generic error messages ("Processing failed")
- Continuing after unrecoverable errors

**PREFER:**
- Fail-fast for missing dependencies
- Actionable error messages with context
- Graceful degradation for optional features

### FFmpeg Integration

**AVOID:**
- Hardcoded FFmpeg paths (use shutil.which())
- Ignoring FFmpeg stderr output
- Assuming FFmpeg capabilities without detection

**PREFER:**
- Runtime FFmpeg capability detection
- Full error reporting from FFmpeg
- Fallback strategies for missing features

---

## Future Architecture Considerations

### Potential Extensions (Not Committed)

**Configuration Management:**
- Support for .videospeeder.json config files
- User profiles with saved presets
- See [Idioms CS-3 Example](idioms.md#example-3-cs-3-medium---add-configuration-file-support)

**Batch Processing:**
- Process multiple videos in sequence
- Directory watching for automated processing
- Job queue for background processing

**Alternative Processing Backends:**
- WebAssembly-based processing (browser support)
- GPU compute shaders (OpenCL/CUDA) for analysis
- Cloud processing integration (AWS MediaConvert, Azure Media Services)

**Plugin System:**
- Custom speed calculation algorithms
- Alternative silence detection methods
- Post-processing filters

**GUI/Web Interface:**
- Desktop GUI (Qt, Electron)
- Web interface with drag-and-drop
- See [Idioms CS-5 Example](idioms.md#example-5-cs-5-epic---rewrite-as-web-service-with-queue)

### Migration Paths

If transitioning from CLI tool to other architectures:
- Core algorithms (silence detection, speed calculation) are reusable
- Extract business logic into library modules
- Create adapters for different interfaces (CLI, Web, API)
- Maintain CLI as primary interface for backward compatibility

---

## Reviewer Checklist

When reviewing architectural changes, verify:

1. **Separation of Concerns:**
   - [ ] FFmpeg command generation separated from execution
   - [ ] Business logic (calculations) separated from I/O
   - [ ] Validation logic separated from processing

2. **Dependency Management:**
   - [ ] External dependencies detected and validated at startup
   - [ ] Graceful degradation for optional dependencies
   - [ ] No unnecessary dependencies added

3. **Error Handling:**
   - [ ] All subprocess calls have error handling
   - [ ] Errors include actionable messages
   - [ ] No silent failures

4. **Testability:**
   - [ ] Pure functions for calculations (no side effects)
   - [ ] Subprocess calls mockable (dependency injection or wrapper functions)
   - [ ] Test fixtures included for new features

5. **Maintainability:**
   - [ ] Functions under 50 lines (extract helpers if longer)
   - [ ] Descriptive function and variable names
   - [ ] Comments explain "why" not "what"
   - [ ] No magic numbers (use named constants)

6. **Alignment with Constitution:**
   - [ ] Change supports user workflow efficiency (§ 1)
   - [ ] Intelligent defaults with override options (§ 2, § 4)
   - [ ] Clear feedback and error messages (§ 3)
   - [ ] Performance considerations addressed (§ 5)

---

*This architecture serves as a living document. Update when significant structural changes occur, but maintain stability and backward compatibility.*
