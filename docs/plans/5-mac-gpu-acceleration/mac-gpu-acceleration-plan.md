# Mac GPU Acceleration Support Implementation Plan

**Plan Version**: 1.0.1
**Created**: 2025-11-09
**Updated**: 2025-11-10
**Spec**: [mac-gpu-acceleration-spec.md](/Users/jordanknight/github/videospeeder/docs/plans/5-mac-gpu-acceleration/mac-gpu-acceleration-spec.md)
**Research**: [research.md](/Users/jordanknight/github/videospeeder/docs/plans/5-mac-gpu-acceleration/research.md)
**Status**: READY

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Technical Context](#technical-context)
3. [Critical Research Findings](#critical-research-findings)
4. [Testing Philosophy](#testing-philosophy)
5. [Implementation Phases](#implementation-phases)
   - [Phase 0: Baseline Validation](#phase-0-baseline-validation)
   - [Phase 1: Hardware Detection Infrastructure](#phase-1-hardware-detection-infrastructure)
   - [Phase 2: Codec Mapping Extension](#phase-2-codec-mapping-extension)
   - [Phase 3: Quality Preset System](#phase-3-quality-preset-system)
   - [Phase 4: Encoder Selection Logic](#phase-4-encoder-selection-logic)
   - [Phase 5: VideoToolbox Parameter Integration](#phase-5-videotoolbox-parameter-integration)
   - [Phase 6: Error Handling & Validation](#phase-6-error-handling--validation)
   - [Phase 7: Status Display](#phase-7-status-display)
   - [Phase 8: Manual Testing & Validation](#phase-8-manual-testing--validation)
   - [Phase 9: Documentation](#phase-9-documentation)
6. [Cross-Cutting Concerns](#cross-cutting-concerns)
7. [Complexity Tracking](#complexity-tracking)
8. [Progress Tracking](#progress-tracking)
9. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

### Problem Statement

VideoSpeeder currently supports GPU acceleration only via NVIDIA NVENC, leaving macOS users without hardware encoding benefits. Apple Silicon (M1/M2/M3) Macs have powerful VideoToolbox hardware encoders, but VideoSpeeder cannot utilize them.

### Solution Approach

- **Extend codec mapping** to include VideoToolbox encoders (`h264_videotoolbox`, `hevc_videotoolbox`) alongside existing NVENC entries
- **Auto-detect Apple Silicon** using `sysctl` probes to determine hardware capability
- **Add `--quality` presets** (fast/balanced/quality) mapping to bitrate targets (12/20/30 Mbps @ 1080p)
- **Preserve NVENC path** completely unchanged - all VideoToolbox logic branches separately
- **Explicit failure mode** when `--gpu` used on unsupported hardware (no silent CPU fallback)
- **Hybrid approach** (Phase 1): CPU filtering + GPU encoding (Metal filters deferred to future)

### Expected Outcomes

- Mac users with Apple Silicon can run `videospeeder --gpu` and get hardware-accelerated encoding
- Observable GPU usage in Activity Monitor, faster processing, lower power consumption
- Clear status messages showing which encoder/chip is active
- No behavioral changes for existing NVENC users on Windows/Linux
- Quality presets provide easy control over bitrate/file-size trade-off

### Success Metrics

- VideoToolbox encoding functional on M1/M2/M3 with `--gpu` flag
- NVENC regression test passes (identical behavior on NVIDIA hardware)
- Manual validation shows GPU utilization in Activity Monitor
- Error messages clearly explain failures (no silent fallback)
- README documentation enables new users to use Mac GPU acceleration

---

## Technical Context

### Current System State

**Architecture**: Single Python CLI script (`videospeeder.py`, 620 lines) orchestrating FFmpeg

**Processing Pipeline**:
1. Silence detection via FFmpeg silencedetect filter
2. Segment calculation (silent vs non-silent)
3. Complex filter graph generation (overlay, drawtext, concat, speed adjustment)
4. FFmpeg encoding with progress tracking

**GPU Support**: NVIDIA NVENC only
- Codec mapping (lines 410-431) defines `gpu_encoder` and `gpu_decoder` keys
- Encoder selection (lines 433-446) chooses NVENC if `use_gpu=True`
- CRF quality control (line 461): `-crf 23` (CPU) or `-crf 18` (GPU)

**Key Constraints**:
- Filters run on CPU always (overlay/drawtext/concat)
- `--gpu-decode` disabled when filters active (line 529)
- NVENC CRF parameters not compatible with VideoToolbox (VT uses bitrate control)

### Integration Requirements

**FFmpeg VideoToolbox**:
- Encoder names: `h264_videotoolbox`, `hevc_videotoolbox` (no AV1 encoder available)
- Quality control: `-b:v` bitrate (no CRF support)
- Pixel format: `-pix_fmt yuv420p` required (filters may output `yuva420p`)
- Disable software fallback: `-allow_sw 0` (ensures explicit failure vs silent CPU fallback)
- HEVC tag: `-tag:v hvc1` for MP4 QuickTime/Safari compatibility

**Platform Detection**:
- `hw.optional.arm64 == 1` identifies Apple Silicon (even under Rosetta)
- `sysctl.proc_translated == 1` detects Rosetta 2 translation
- `system_profiler SPHardwareDataType -json` gets chip marketing name ("Apple M2")

**Bitrate Targets** (per spec):
- Fast: 12 Mbps @ 1080p
- Balanced: 20 Mbps @ 1080p (default, YouTube-optimized)
- Quality: 30 Mbps @ 1080p
- Optional: scale by resolution (1.0x at 1920×1080)

### Constraints and Limitations

**Architectural**:
- Must preserve NVENC code path completely unchanged
- Single `codec_map` structure shared by NVENC and VideoToolbox
- No refactoring of existing `run_ffmpeg_processing()` signature
- Must maintain backward compatibility with existing CLI arguments

**Technical**:
- VideoToolbox doesn't support CRF (must use bitrate control)
- VideoToolbox H.264/HEVC only (no AV1 encoder in FFmpeg)
- Hybrid approach only (CPU filters, GPU encoding) - Metal filters out of scope
- Apple Silicon only (M1/M2/M3) - Intel Macs explicitly excluded

**Quality**:
- VideoToolbox prioritizes speed over compression (2-3x larger files than libx265)
- Bitrate control less consistent than CRF across different content types
- Manual testing only (no automated test suite per spec)

### Assumptions

1. FFmpeg on Mac has VideoToolbox support compiled in (Homebrew standard build)
2. macOS 11+ provides stable VideoToolbox API
3. Users accept larger file sizes (2-3x) for GPU acceleration benefits
4. Bitrate-based quality is acceptable substitute for CRF
5. CPU filtering + GPU encoding provides sufficient performance benefit
6. Explicit failure preferable to silent CPU fallback when `--gpu` requested

---

## Critical Research Findings

### 🚨 Critical Discovery 01: VideoToolbox CRF Incompatibility
**Impact**: Critical
**Sources**: [Research § 3 VideoToolbox Parameter Reference]

**Problem**: VideoToolbox encoders do NOT support `-crf` (constant rate factor) parameter. Current code applies CRF universally at line 461.

**Root Cause**: VideoToolbox uses bitrate-based rate control (`-b:v`, `-maxrate`, `-bufsize`), not quality-based CRF like x264/x265.

**Solution**: Conditional parameter application:
```python
# videospeeder.py lines ~461
if vt_active:  # VideoToolbox path
    cmd += ["-b:v", str(target), "-maxrate", str(maxrate), "-bufsize", str(bufsize)]
else:  # NVENC/CPU path (unchanged)
    cmd += ["-crf", "23" if not use_gpu else "18"]
```

**Action Required**: Modify command construction in `run_ffmpeg_processing()` to branch on encoder type before adding quality parameters.

**Affects Phases**: Phase 5 (VideoToolbox Parameter Integration)

---

### 🚨 Critical Discovery 02: Silent Software Fallback Risk
**Impact**: Critical
**Sources**: [Research § 3, § 7 Pitfalls]

**Problem**: FFmpeg VideoToolbox encoders silently fall back to software encoding when hardware unavailable, violating spec requirement for explicit failure.

**Root Cause**: Default VideoToolbox behavior without `-allow_sw 0` parameter.

**Solution**: Add `-allow_sw 0` to VideoToolbox commands:
```python
cmd += ["-allow_sw", "0", "-b:v", str(target), ...]  # Hardware-only enforcement
```

**Expected Error**: `"Try -allow_sw 1. The hardware encoder may be busy, or not supported."`

**Action Required**:
1. Add `-allow_sw 0` to VideoToolbox encoding commands
2. Parse this specific error message in stderr
3. Convert to user-friendly error with guidance (close apps, check permissions, reboot)

**Affects Phases**: Phase 5 (Parameter Integration), Phase 6 (Error Handling)

---

### 🚨 Critical Discovery 03: Platform Detection Must Handle Rosetta
**Impact**: Critical
**Sources**: [Research § 1 Hardware Detection]

**Problem**: Standard `platform.machine()` returns `x86_64` when Python runs under Rosetta 2, causing false negative for Apple Silicon detection.

**Root Cause**: Rosetta 2 translates x86_64 binaries, making process appear Intel-based.

**Solution**: Use `sysctl hw.optional.arm64` instead of `platform.machine()`:
```python
hw_arm64 = _sysctl_int("hw.optional.arm64") == 1  # Works even under Rosetta
rosetta = _sysctl_int("sysctl.proc_translated") == 1  # Detects translation
```

**Evidence**: `hw.optional.arm64 == 1` on Apple Silicon hosts, even when process runs translated. Officially documented by Apple.

**Action Required**: Implement `detect_apple_silicon()` function using `sysctl` probes (not `platform` module).

**Affects Phases**: Phase 1 (Hardware Detection Infrastructure)

---

### ⚠️ High Discovery 04: AV1 Not Available via VideoToolbox
**Impact**: High
**Sources**: [Research § 2, § 10 Compatibility Matrix]

**Problem**: FFmpeg does not expose AV1 encoding via VideoToolbox, only H.264 and HEVC.

**Root Cause**: VideoToolbox AV1 encode support not available or not exposed in FFmpeg builds.

**Solution**: Explicit error when AV1 + --gpu on Mac:
```python
codec_map = {
    "av1": {
        "apple_encoder": None,  # No AV1 VT encoder
        # ... NVENC entries unchanged
    }
}

if codec_key == "av1" and use_gpu and is_apple_silicon:
    raise SystemExit("ERROR: AV1 hardware encoding not available via VideoToolbox. Use CPU (libsvtav1) or NVIDIA.")
```

**Action Required**: Set `apple_encoder: None` for AV1 in codec_map and add explicit error handling.

**Affects Phases**: Phase 2 (Codec Mapping), Phase 6 (Error Handling)

---

### ⚠️ High Discovery 05: Pixel Format Mismatch from Filters
**Impact**: High
**Sources**: [Research § 3, § 7 Pitfalls]

**Problem**: CPU filters (overlay with PNG alpha) may output `yuva420p` or `bgra`, incompatible with VideoToolbox input.

**Root Cause**: VideoToolbox requires explicit `yuv420p` (8-bit) or `p010le` (10-bit) pixel formats.

**Solution**: Force pixel format for VideoToolbox:
```python
if vt_active:
    cmd += ["-pix_fmt", "yuv420p"]  # 8-bit default
```

**Fallback**: If errors persist, insert `format=yuv420p` filter in filtergraph before encoding.

**Expected Errors**: `"Incompatible pixel format"` or `"auto-selecting format"` in stderr.

**Action Required**:
1. Add `-pix_fmt yuv420p` to VideoToolbox commands
2. Parse pixel format errors and suggest filtergraph insertion if needed

**Affects Phases**: Phase 5 (Parameter Integration), Phase 6 (Error Handling)

---

### ⚠️ High Discovery 06: HEVC MP4 Requires hvc1 Tag
**Impact**: High
**Sources**: [Research § 3, § 7 Pitfalls]

**Problem**: HEVC in MP4 container may not play in QuickTime/Safari without proper tag.

**Root Cause**: HEVC MP4 requires `hvc1` tag for Apple platform compatibility (vs default `hev1`).

**Solution**: Add tag for HEVC VideoToolbox:
```python
if codec_key == "hevc" and vt_active:
    cmd += ["-tag:v", "hvc1"]
```

**Action Required**: Conditional tag application for HEVC VideoToolbox encoding.

**Affects Phases**: Phase 5 (Parameter Integration)

---

### Medium Discovery 07: Bitrate Scaling by Resolution
**Impact**: Medium
**Sources**: [Research § 3 Bitrate Presets, § 7 Pitfalls]

**Problem**: Fixed bitrates (12/20/30 Mbps) may be wasteful for 720p or insufficient for 4K.

**Root Cause**: Spec specifies bitrates at 1080p baseline, but users process various resolutions.

**Solution**: Optional bitrate scaling by pixel count:
```python
def _vt_target_bitrate_bits(quality: str, width: int, height: int) -> int:
    base = {"fast": 12_000_000, "balanced": 20_000_000, "quality": 30_000_000}[quality]
    scale = max(1.0, (width * height) / (1920 * 1080))  # 1.0x at 1080p
    return int(base * scale)
```

**Examples**:
- 720p (1280×720): 0.44× → 5.3 / 8.8 / 13.2 Mbps
- 4K (3840×2160): 4.0× → 48 / 80 / 120 Mbps

**Action Required**: Implement optional scaling in bitrate helper function. Can be enabled/disabled based on testing results.

**Affects Phases**: Phase 3 (Quality Presets), Phase 5 (Parameter Integration)

---

### Medium Discovery 08: FFmpeg Availability Detection
**Impact**: Medium
**Sources**: [Research § 2 Encoder Selection, § 4 Error Handling]

**Problem**: Not all FFmpeg builds include VideoToolbox support (conda builds often exclude it).

**Root Cause**: VideoToolbox is macOS-specific, some custom builds omit platform-specific encoders.

**Solution**: Pre-flight check before encoding:
```python
def ffmpeg_has_videotoolbox_encoders() -> bool:
    try:
        out = subprocess.check_output(["ffmpeg", "-hide_banner", "-encoders"], stderr=subprocess.STDOUT)
        return ("h264_videotoolbox" in out.decode("utf-8", "ignore"))
    except Exception:
        return False
```

**Error Message**: "FFmpeg was built without VideoToolbox encoders. Install Homebrew ffmpeg (brew install ffmpeg)."

**Action Required**: Implement availability check and call before constructing VideoToolbox commands.

**Affects Phases**: Phase 4 (Encoder Selection), Phase 6 (Error Handling)

---

### Medium Discovery 09: VBV Constrained Bitrate Pattern
**Impact**: Medium
**Sources**: [Research § 3 VBV Suggestion]

**Problem**: Simple `-b:v X` bitrate may produce uneven quality across variable content.

**Root Cause**: Unconstrained bitrate allows large spikes, depleting bitrate budget unevenly.

**Solution**: Use constrained VBR with VBV (Video Buffering Verifier):
```python
target = 20_000_000  # 20 Mbps balanced
maxrate = int(target * 1.25)   # 25 Mbps peak
bufsize = int(target * 2.5)    # 50 Mbit buffer
cmd += ["-b:v", str(target), "-maxrate", str(maxrate), "-bufsize", str(bufsize)]
```

**Rationale**: Constrains bitrate spikes while allowing flexibility, produces smoother quality.

**Action Required**: Use VBV parameters (maxrate, bufsize) with all VideoToolbox bitrate settings.

**Affects Phases**: Phase 5 (Parameter Integration)

---

### Medium Discovery 10: Hardware Busy Error Pattern
**Impact**: Medium
**Sources**: [Research § 4 Error Handling, § 8 Validation]

**Problem**: VideoToolbox can fail with "cannot create compression session" when hardware busy (camera app, screen recording, another encode).

**Root Cause**: Limited hardware encoder contexts, shared across system.

**Solution**: Parse specific error pattern:
```python
def parse_vt_error(stderr: str) -> str | None:
    if "cannot create compression session" in stderr.lower():
        return ("VideoToolbox hardware encoder unavailable or busy. "
                "Close apps using video encode/camera, ensure Screen Recording permissions, "
                "and try again. If issue persists, reboot macOS.")
```

**Action Required**: Implement error parser for common VideoToolbox failure patterns.

**Affects Phases**: Phase 6 (Error Handling)

---

### Low Discovery 11: system_profiler for Chip Marketing Name
**Impact**: Low
**Sources**: [Research § 1 Hardware Detection, § 6 Status Display]

**Problem**: `sysctl` provides CPU brand string but not clean marketing name ("Apple M2").

**Root Cause**: Marketing names stored differently than technical CPU identifiers.

**Solution**: Call `system_profiler SPHardwareDataType -json` and parse `chip` field:
```python
out = subprocess.check_output(["system_profiler", "SPHardwareDataType", "-json"], timeout=5)
data = json.loads(out.decode("utf-8", "ignore"))
chip = data["SPHardwareDataType"][0].get("chip") or "Unknown Apple Silicon"
```

**Fallback**: If parsing fails, use "Unknown Apple Silicon" (still functional).

**Action Required**: Enhance `detect_apple_silicon()` to optionally fetch chip name for status display.

**Affects Phases**: Phase 1 (Hardware Detection), Phase 7 (Status Display)

---

### Low Discovery 12: NVENC Profile Selection
**Impact**: Low
**Sources**: [Research § 5d Encoder Selection, videospeeder.py context]

**Problem**: Current code doesn't set video profile for encoders (relies on FFmpeg defaults).

**Root Cause**: Profiles not critical for basic encoding, but can optimize compatibility/efficiency.

**Solution**: Add profile selection for VideoToolbox (NVENC unchanged):
```python
if vt_active:
    if codec_key == "h264":
        cmd += ["-profile:v", "high"]  # H.264 High Profile (widely compatible)
    elif codec_key == "hevc":
        cmd += ["-profile:v", "main"]  # HEVC Main Profile (8-bit, standard)
```

**Future**: Add Main10 profile for 10-bit HEVC if HDR support added.

**Action Required**: Add profile selection for VideoToolbox encoders (low priority, can defer to Phase 5).

**Affects Phases**: Phase 5 (Parameter Integration)

---

### Low Discovery 13: Rosetta Translation Warning
**Impact**: Low
**Sources**: [Research § 1 Hardware Detection]

**Problem**: VideoToolbox may work under Rosetta but with performance penalty (translation overhead).

**Root Cause**: Rosetta 2 adds translation layer for x86_64 → arm64 instruction conversion.

**Solution**: Detect and warn if running under Rosetta:
```python
if asi.is_apple_silicon and asi.under_rosetta:
    print("Warning: Running under Rosetta 2 translation. Use native arm64 Python for best performance.")
```

**Action Required**: Optional warning in status display (not blocking).

**Affects Phases**: Phase 7 (Status Display)

---

### Deduplication Log

**Merged Discoveries**:
- S1-02 (Pattern: codec mapping structure) + S2-01 (API: VideoToolbox encoder names) → Discovery 02 (Codec Mapping Extension)
- S3-04 (Implication: CRF compatibility) + S2-03 (Constraint: no CRF support) → Discovery 01 (CRF Incompatibility)
- S4-01 (Dependency: FFmpeg with VT) + S3-02 (Edge case: missing VT) → Discovery 08 (FFmpeg Availability Detection)

**Discovery Count**: 13 final discoveries (3 Critical, 5 High, 4 Medium, 1 Low)

---

## Testing Philosophy

### Testing Approach

**Selected Approach**: Manual Only

**Rationale** (from spec):
> "non needed this is just a small util"

VideoSpeeder is a focused utility tool with manual testing appropriate for:
- Platform-specific hardware integration (requires real Apple Silicon hardware)
- GPU acceleration validation (observable via system monitoring tools)
- FFmpeg integration (real-world video processing validation)
- Quality assessment (visual inspection of output)

### Manual Testing Strategy

**Pre-Implementation Validation**:
- Verify FFmpeg with VideoToolbox available: `ffmpeg -encoders | grep videotoolbox`
- Test hardware detection on multiple Mac types (M1, M2, M3, Intel)
- Validate baseline NVENC functionality remains unchanged

**Per-Phase Validation**:
Each phase includes explicit manual test steps in task success criteria.

**Post-Implementation Validation** (Phase 8):
- Functional tests with real videos (H.264, HEVC, multiple resolutions)
- GPU utilization verification via Activity Monitor
- Observational validation (speed, power consumption, heat, fan noise)
- Error path testing (unsupported hardware, busy encoder, missing FFmpeg support)
- NVENC regression testing (Windows/Linux if available, or code review confirmation)

### Test Scenarios

**Normal Cases**:
- Apple Silicon + `--gpu` + H.264 → VideoToolbox encoding successful
- Apple Silicon + `--gpu` + HEVC → VideoToolbox encoding successful
- Apple Silicon + `--gpu --quality fast` → 12 Mbps bitrate observed
- Apple Silicon + `--gpu --quality balanced` → 20 Mbps bitrate observed
- Apple Silicon + `--gpu --quality quality` → 30 Mbps bitrate observed
- NVIDIA GPU + `--gpu` → NVENC encoding unchanged (if testable)

**Edge Cases**:
- Intel Mac + `--gpu` → Clear error: "requires Apple Silicon"
- Apple Silicon + old FFmpeg (no VT) + `--gpu` → Error: "FFmpeg missing VideoToolbox"
- Apple Silicon + AV1 + `--gpu` → Error: "AV1 not available via VideoToolbox"
- VideoToolbox hardware busy → Error: "encoder busy, close apps"
- No `--gpu` flag → CPU encoding (libx264/libx265) unchanged

**Boundary Cases**:
- Very short videos (< 10s)
- Very long videos (> 1 hour)
- Low resolution (480p) with default bitrate
- High resolution (4K) with default bitrate (observe file size)
- Complex overlays/indicators with VideoToolbox encoding

### Success Criteria for Manual Testing

**Functional**:
- [ ] VideoToolbox encoding produces valid playable video
- [ ] Output quality acceptable for intended use (YouTube upload)
- [ ] Processing completes without crashes or hangs
- [ ] Error messages are clear and actionable
- [ ] Status display shows correct encoder and chip model

**Observable Performance**:
- [ ] Activity Monitor shows GPU utilization during encoding
- [ ] Processing noticeably faster than CPU encoding (subjective observation)
- [ ] System runs cooler/quieter than CPU encoding (fan noise, heat)
- [ ] Battery drain slower than CPU encoding (on MacBook)

**Regression**:
- [ ] NVENC code path unchanged (code review or testing on NVIDIA hardware)
- [ ] CPU encoding still works without `--gpu` flag
- [ ] Existing CLI arguments function identically
- [ ] Error handling for non-GPU cases unchanged

### Documentation of Test Results

Test results will be documented in Phase 8 execution log with:
- Video file details (codec, resolution, duration, file size)
- Command executed
- Observed GPU usage (screenshot or numeric values)
- Processing time (for comparison reference, not performance benchmark)
- Output quality assessment (visual inspection notes)
- Any errors encountered and resolution

---

## Implementation Phases

### Phase 0: Baseline Validation

**Objective**: Verify current VideoSpeeder functionality and FFmpeg VideoToolbox availability using scratch folder test videos before beginning implementation, establishing a working baseline.

**Deliverables**:
- Confirmation that existing VideoSpeeder CPU encoding works
- Verification that FFmpeg has VideoToolbox encoders compiled in
- Simple manual VideoToolbox encoding test with FFmpeg CLI
- Test video in scratch folder for validation

**Dependencies**: None (pre-implementation validation)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| FFmpeg missing VideoToolbox | Medium | Critical | Install Homebrew FFmpeg before proceeding |
| No test video available | Low | Low | Use any short video from scratch folder or create simple test |
| Current VideoSpeeder broken | Low | High | Fix baseline issues before adding new features |

### Tasks (Manual Testing Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 0.1 | [ ] | Verify FFmpeg installation | 1 | `ffmpeg -version` shows version 4.x+ and build info | - | Check FFmpeg present and functional |
| 0.2 | [ ] | Check VideoToolbox encoder availability | 1 | `ffmpeg -encoders \| grep videotoolbox` shows h264_videotoolbox and hevc_videotoolbox | - | Critical pre-requisite per Discovery 08 |
| 0.3 | [ ] | List available test videos in scratch folder | 1 | `ls -lh scratch/*.mp4` (or similar) shows at least one video file | - | Identify test asset |
| 0.4 | [ ] | Test current VideoSpeeder CPU encoding | 2 | `python3 videospeeder.py -i scratch/<video> -o scratch/test-cpu-output.mp4` completes successfully | - | Baseline functionality check |
| 0.5 | [ ] | Verify output video playable | 1 | Open `scratch/test-cpu-output.mp4` in QuickTime/VLC, plays correctly | - | Sanity check encoding works |
| 0.6 | [ ] | Test VideoToolbox directly with FFmpeg CLI | 2 | `ffmpeg -i scratch/<video> -c:v h264_videotoolbox -b:v 10M scratch/test-vt-direct.mp4` succeeds | - | Prove VideoToolbox functional before integration |
| 0.7 | [ ] | Verify VideoToolbox output playable | 1 | Open `scratch/test-vt-direct.mp4` in QuickTime, plays correctly | - | Validate VT encoding produces valid output |
| 0.8 | [ ] | Check for pixel format warnings | 1 | Review FFmpeg output from 0.6, note any pixel format warnings or auto-conversion messages | - | Preview Discovery 05 issues |
| 0.9 | [ ] | Document baseline system information | 1 | Record: macOS version, chip model (M1/M2/M3 or Intel), FFmpeg version, Python version | - | Environment documentation |
| 0.10 | [ ] | Clean up test outputs | 1 | `rm scratch/test-*.mp4` to remove test files | - | Keep scratch folder clean |

### Non-Happy-Path Coverage
- [ ] FFmpeg not installed (error with installation instructions)
- [ ] FFmpeg without VideoToolbox support (error, suggest Homebrew install)
- [ ] No test video in scratch (create simple test or skip to Phase 1)
- [ ] Current VideoSpeeder broken (fix before proceeding)

### Acceptance Criteria
- [ ] All 10 tasks completed successfully
- [ ] FFmpeg with VideoToolbox confirmed available
- [ ] Current VideoSpeeder CPU encoding functional (baseline)
- [ ] Direct VideoToolbox encoding via FFmpeg CLI successful
- [ ] Test video identified and validated
- [ ] System information documented for reference
- [ ] No blocking issues preventing implementation

### Commands to Run

Execute these commands in order to complete Phase 0 validation:

**1. Verify FFmpeg Installation (Task 0.1)**:
```bash
ffmpeg -version
# Expected: FFmpeg version 4.x or higher
```

**2. Check VideoToolbox Availability (Task 0.2)**:
```bash
ffmpeg -encoders | grep videotoolbox
# Expected output:
#  V..... h264_videotoolbox    VideoToolbox H.264 Encoder (codec h264)
#  V..... hevc_videotoolbox    VideoToolbox H.265 Encoder (codec hevc)
```

**3. List Test Videos (Task 0.3)**:
```bash
ls -lh scratch/*.mp4
# Or: ls -lh scratch/*.mov
# Expected: At least one video file listed
```

**4. Test Current VideoSpeeder CPU Encoding (Task 0.4)**:
```bash
# Test current CPU encoding (should work before any changes)
python3 /Users/jordanknight/github/videospeeder/videospeeder_project/videospeeder.py \
  -i scratch/<input-video>.mp4 \
  -o scratch/test-baseline-output.mp4
# Expected: Command completes successfully
```

**5. Verify Baseline Output Playable (Task 0.5)**:
```bash
# Open in QuickTime (macOS)
open scratch/test-baseline-output.mp4

# Or VLC (cross-platform)
vlc scratch/test-baseline-output.mp4
# Expected: Video plays correctly
```

**6. Test VideoToolbox Directly (Task 0.6)**:
```bash
# Simple H.264 VideoToolbox encode (10 Mbps)
ffmpeg -i scratch/<input-video>.mp4 \
  -c:v h264_videotoolbox \
  -b:v 10M \
  -pix_fmt yuv420p \
  -c:a aac \
  scratch/test-vt-direct.mp4
# Expected: Command completes successfully
```

**7. Verify VideoToolbox Output Playable (Task 0.7)**:
```bash
open scratch/test-vt-direct.mp4
# Expected: Video plays correctly in QuickTime
```

**8. Check for Pixel Format Warnings (Task 0.8)**:
```bash
# Re-run Task 0.6 command and review output
# Look for lines like:
#   "Incompatible pixel format"
#   "auto-selecting format"
# Document any warnings found
```

**9. Document System Information (Task 0.9)**:
```bash
# macOS version
sw_vers

# Chip model
sysctl -n machdep.cpu.brand_string
# Or: system_profiler SPHardwareDataType | grep "Chip:"

# FFmpeg version
ffmpeg -version | head -1

# Python version
python3 --version
```

**10. Clean Up Test Outputs (Task 0.10)**:
```bash
rm scratch/test-baseline-output.mp4 scratch/test-vt-direct.mp4
# Expected: Test files removed, scratch folder clean
```

---

### Phase 1: Hardware Detection Infrastructure

**Objective**: Implement robust Apple Silicon detection that works under Rosetta, provides chip marketing name, and serves as foundation for encoder selection.

**Deliverables**:
- `AppleSiliconInfo` data class
- `detect_apple_silicon()` function with `sysctl` probes
- Helper functions: `_sysctl_str()`, `_sysctl_int()`
- Optional: chip marketing name from `system_profiler`

**Dependencies**: None (foundational phase)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `sysctl` unavailable on old macOS | Low | Medium | Graceful fallback to "Unknown" chip name, detection still works |
| `system_profiler` slow/timeout | Medium | Low | 5-second timeout, use "Unknown Apple Silicon" fallback |
| Rosetta detection key missing | Low | Low | Treat as "not translated" (default False) |

### Tasks (Manual Testing Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 1.1 | [ ] | Add `AppleSiliconInfo` class definition | 1 | Class with `is_apple_silicon`, `chip`, `under_rosetta` attributes defined at module top | - | Simple data container, no behavior |
| 1.2 | [ ] | Implement `_sysctl_str()` helper function | 1 | Returns sysctl string value or empty string on error, no exceptions raised | - | Uses `/usr/sbin/sysctl -n <key>` subprocess call |
| 1.3 | [ ] | Implement `_sysctl_int()` helper function | 1 | Returns sysctl integer value or -1 on error, handles non-numeric strings | - | Calls `_sysctl_str()` and converts to int |
| 1.4 | [ ] | Implement `detect_apple_silicon()` core logic | 2 | Returns `AppleSiliconInfo(True, ...)` on M1/M2/M3, `(False, ...)` on Intel/non-Mac | - | Uses `hw.optional.arm64` and `sysctl.proc_translated` per Discovery 03 |
| 1.5 | [ ] | Add `system_profiler` chip name fetching | 2 | Parses JSON from `system_profiler SPHardwareDataType -json`, extracts `chip` field, falls back to "Unknown Apple Silicon" | - | 5-second timeout, graceful failure per Discovery 11 |
| 1.6 | [ ] | Manual test: run on Apple Silicon native | 1 | `detect_apple_silicon()` returns `is_apple_silicon=True`, `chip="Apple M*"`, `under_rosetta=False` | - | Test on M1/M2/M3 Mac |
| 1.7 | [ ] | Manual test: run under Rosetta (if possible) | 1 | Returns `is_apple_silicon=True`, `under_rosetta=True` even when Python is x86_64 | - | Run with Rosetta-translated Python binary |
| 1.8 | [ ] | Manual test: run on Intel Mac | 1 | Returns `is_apple_silicon=False`, `chip=""`, `under_rosetta=False` | - | Test on Intel Mac or verify code logic |

### Non-Happy-Path Coverage
- [ ] `sysctl` command not found (return default values)
- [ ] `system_profiler` timeout (use fallback chip name)
- [ ] Non-Darwin platform (return False early)
- [ ] Missing sysctl keys on old macOS (graceful default to -1 or "")

### Acceptance Criteria
- [ ] All 8 tasks completed with success criteria met
- [ ] Detection works on Apple Silicon (M1/M2/M3)
- [ ] Detection correctly identifies Intel Macs as not Apple Silicon
- [ ] Rosetta detection functional (tested if possible, code-reviewed otherwise)
- [ ] No exceptions raised for any platform or configuration
- [ ] Chip marketing name retrieved when available, fallback when not

---

### Phase 2: Codec Mapping Extension

**Objective**: Extend existing `codec_map` dictionary with `apple_encoder` keys for VideoToolbox support without modifying NVENC entries.

**Deliverables**:
- Extended `codec_map` with `apple_encoder` keys
- Documentation comments explaining VideoToolbox limitations

**Dependencies**: None (isolated data structure change)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Typo in encoder names | Low | High | Manual verification against `ffmpeg -encoders` output |
| Breaking existing NVENC keys | Low | Critical | Code review: verify no modifications to `gpu_encoder` or `gpu_decoder` entries |

### Tasks (Manual Testing Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 2.1 | [ ] | Add `apple_encoder` key to H.264 entry | 1 | `codec_map["h264"]["apple_encoder"] = "h264_videotoolbox"` | - | Per Discovery 04 (Research § 2) |
| 2.2 | [ ] | Add `apple_encoder` key to HEVC entry | 1 | `codec_map["hevc"]["apple_encoder"] = "hevc_videotoolbox"` | - | Same for "h265" alias |
| 2.3 | [ ] | Add `apple_encoder` key to AV1 entry | 1 | `codec_map["av1"]["apple_encoder"] = None` | - | No AV1 VT encoder per Discovery 04 |
| 2.4 | [ ] | Add documentation comments | 1 | Comments above `codec_map` explain: VT encoders for Mac, None for AV1, NVENC unchanged | - | Inline docstring or block comment |
| 2.5 | [ ] | Code review: verify NVENC keys unchanged | 1 | `gpu_encoder`, `gpu_decoder` entries identical to pre-modification state | - | Diff review |
| 2.6 | [ ] | Manual test: verify structure valid Python | 1 | Script parses without syntax errors, `codec_map` accessible | - | Run `python3 -m py_compile videospeeder.py` |

### Non-Happy-Path Coverage
- [ ] Missing `apple_encoder` key (handled by later phases with `.get("apple_encoder")`)
- [ ] Invalid encoder name (will fail in Phase 4 validation check)

### Acceptance Criteria
- [ ] All 6 tasks completed
- [ ] `codec_map` contains `apple_encoder` keys for h264, hevc, h265, av1
- [ ] NVENC entries (`gpu_encoder`, `gpu_decoder`) completely unchanged
- [ ] Documentation clearly explains new keys
- [ ] No syntax errors, code still executable

---

### Phase 3: Quality Preset System

**Objective**: Add `--quality` CLI argument and bitrate calculation helper function supporting fast/balanced/quality presets with optional resolution scaling.

**Deliverables**:
- `--quality` argument in `parse_args()`
- `_vt_target_bitrate_bits()` helper function
- `_probe_stream()` helper to get width/height (if not already present)

**Dependencies**: None (isolated CLI and calculation logic)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Bitrate values inappropriate for content | Medium | Medium | Use researched values (12/20/30 Mbps), allow user override in future |
| Resolution scaling too aggressive | Low | Medium | Make scaling optional/configurable, test with multiple resolutions |

### Tasks (Manual Testing Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 3.1 | [ ] | Add `--quality` argument to parser | 1 | `parser.add_argument("--quality", choices=["fast", "balanced", "quality"], default="balanced", help=...)` | - | Default "balanced" (20 Mbps) per spec |
| 3.2 | [ ] | Implement `_vt_target_bitrate_bits()` function | 2 | Returns 12M/20M/30M (bits/sec) for fast/balanced/quality, accepts width/height params | - | Per Discovery 07, scaling optional initially |
| 3.3 | [ ] | Add optional resolution scaling logic | 2 | Scales bitrate proportionally to (width×height)/(1920×1080), min 1.0× | - | Example: 4K (4.0×) → 48/80/120 Mbps |
| 3.4 | [ ] | Verify/create `_probe_stream()` helper | 1 | Returns tuple: `(codec_name, width, height, pix_fmt)` from ffprobe | - | May already exist partially in `get_video_codec()` |
| 3.5 | [ ] | Manual test: `--quality fast` sets bitrate correctly | 1 | Bitrate helper returns 12_000_000 for 1080p fast preset | - | Unit calculation test |
| 3.6 | [ ] | Manual test: `--quality balanced` default behavior | 1 | No `--quality` flag → balanced preset → 20_000_000 bits/sec | - | Verify default argument |
| 3.7 | [ ] | Manual test: `--quality quality` sets bitrate correctly | 1 | Bitrate helper returns 30_000_000 for 1080p quality preset | - | Unit calculation test |
| 3.8 | [ ] | Manual test: resolution scaling (if enabled) | 1 | 720p fast → ~6 Mbps, 4K quality → ~120 Mbps (proportional scaling) | - | Verify scaling formula |

### Non-Happy-Path Coverage
- [ ] Missing width/height from ffprobe (use fallback 1920×1080 or error)
- [ ] Invalid quality value (argparse choices validation handles this)
- [ ] Zero or negative resolution (clamp scale to 1.0 minimum)

### Acceptance Criteria
- [ ] All 8 tasks completed
- [ ] `--quality` argument available in CLI help
- [ ] Three presets functional (fast/balanced/quality)
- [ ] Bitrate values match spec (12/20/30 Mbps @ 1080p)
- [ ] Resolution scaling functional if enabled
- [ ] Help text clearly explains preset options

---

### Phase 4: Encoder Selection Logic

**Objective**: Implement platform-aware encoder selection functions that choose VideoToolbox on Apple Silicon, NVENC on NVIDIA, and provide clear errors when GPU unavailable.

**Deliverables**:
- `ffmpeg_has_videotoolbox_encoders()` availability check
- `choose_encoder()` platform-aware selection function
- Integration into existing `run_ffmpeg_processing()` flow

**Dependencies**:
- Phase 1 (Hardware Detection) - uses `detect_apple_silicon()`
- Phase 2 (Codec Mapping) - reads `apple_encoder` keys

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking NVENC logic | Low | Critical | Preserve existing non-Darwin path completely unchanged |
| False positive VT availability | Low | High | Validate both h264 and hevc encoders present |
| Incorrect error returns | Medium | High | Return sentinel None for errors, validate in Phase 6 |

### Tasks (Manual Testing Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 4.1 | [ ] | Implement `ffmpeg_has_videotoolbox_encoders()` | 2 | Runs `ffmpeg -hide_banner -encoders`, returns True if "h264_videotoolbox" present | - | Per Discovery 08 (Research § 2) |
| 4.2 | [ ] | Implement `choose_encoder()` function skeleton | 2 | Function signature: `choose_encoder(codec_name: str, use_gpu: bool) -> Tuple[str, List[str]]` | - | Returns (encoder, decoder_args) |
| 4.3 | [ ] | Add non-GPU path (unchanged behavior) | 1 | `if not use_gpu: return entry["cpu_encoder"], []` | - | Preserve existing CPU encoding logic |
| 4.4 | [ ] | Add non-Darwin GPU path (NVENC unchanged) | 2 | `if platform.system() != "Darwin": return entry["gpu_encoder"], entry.get("gpu_decoder", [])` | - | Exact replica of existing NVENC logic |
| 4.5 | [ ] | Add Darwin Apple Silicon detection | 2 | Calls `detect_apple_silicon()`, checks `is_apple_silicon` | - | Intel Mac returns None for encoder (explicit failure) |
| 4.6 | [ ] | Add FFmpeg VT availability check | 1 | Calls `ffmpeg_has_videotoolbox_encoders()`, returns None if False | - | Enables error in Phase 6 |
| 4.7 | [ ] | Add AV1 special case handling | 1 | `if ckey == "av1": return None, []` on Darwin | - | Per Discovery 04, no AV1 VT encoder |
| 4.8 | [ ] | Return VideoToolbox encoder | 1 | `return entry["apple_encoder"], []` (no VT decode) | - | Filters on CPU by design |
| 4.9 | [ ] | Integrate `choose_encoder()` into `run_ffmpeg_processing()` | 2 | Replace lines ~433-446 encoder selection with `choose_encoder()` call | - | Preserve variable names (`vcodec`, `decoder_args`) |
| 4.10 | [ ] | Manual test: Apple Silicon + GPU → VT selected | 1 | `choose_encoder("h264", True)` returns `("h264_videotoolbox", [])` on M1/M2/M3 | - | Verify with print statement |
| 4.11 | [ ] | Manual test: Intel Mac + GPU → None returned | 1 | `choose_encoder("h264", True)` returns `(None, [])` on Intel Mac | - | Code review or Intel Mac test |
| 4.12 | [ ] | Manual test: NVENC path unchanged | 1 | Non-Darwin platform returns `("h264_nvenc", [...])` unchanged | - | Code review confirms no modifications |

### Non-Happy-Path Coverage
- [ ] Codec not in `codec_map` (return CPU fallback)
- [ ] Apple Silicon + AV1 + GPU (return None)
- [ ] Intel Mac + GPU (return None)
- [ ] FFmpeg without VT + GPU (return None)
- [ ] Non-Darwin + GPU (use existing NVENC logic)

### Acceptance Criteria
- [ ] All 12 tasks completed
- [ ] `choose_encoder()` returns correct encoder for all platform/codec combinations
- [ ] NVENC logic completely unchanged (code review confirmation)
- [ ] Apple Silicon correctly selects VideoToolbox
- [ ] Intel Mac correctly returns None (will error in Phase 6)
- [ ] No regressions in existing encoder selection behavior

---

### Phase 5: VideoToolbox Parameter Integration

**Objective**: Integrate VideoToolbox-specific FFmpeg parameters (bitrate, pixel format, profile, tag) into command construction, replacing CRF for VT path while preserving NVENC/CPU CRF logic.

**Deliverables**:
- Modified command construction in `run_ffmpeg_processing()`
- Conditional parameter application based on encoder type
- VBV constrained bitrate configuration

**Dependencies**:
- Phase 3 (Quality Presets) - uses `_vt_target_bitrate_bits()`
- Phase 4 (Encoder Selection) - determines `vcodec` value

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking CRF for NVENC/CPU | Low | Critical | Use strict conditional: only apply VT params when `vt_active=True` |
| Pixel format incompatibility | Medium | High | Force yuv420p, monitor for errors in Phase 8 |
| Incorrect bitrate units | Low | Medium | Use bits (not kbits): 20M → 20_000_000 |

### Tasks (Manual Testing Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 5.1 | [ ] | Add encoder type detection variable | 1 | `vt_active = (vcodec is not None) and vcodec.endswith("_videotoolbox")` after encoder selection | - | Boolean flag for conditional logic |
| 5.2 | [ ] | Probe input video for width/height | 1 | Call `_probe_stream(input_file)` to get `(codec, w, h, pix_fmt)` | - | Needed for bitrate scaling |
| 5.3 | [ ] | Calculate target bitrate for VT path | 1 | `target = _vt_target_bitrate_bits(args.quality, w, h)` | - | Uses Phase 3 helper |
| 5.4 | [ ] | Calculate VBV parameters | 1 | `maxrate = int(target * 1.25)`, `bufsize = int(target * 2.5)` | - | Per Discovery 09 (Research § 3) |
| 5.5 | [ ] | Add VideoToolbox parameter block | 3 | Conditional block: `if vt_active: cmd += [...]` with all VT params | - | Critical Discovery 01 - replaces CRF |
| 5.6 | [ ] | Add bitrate control params | 1 | `-allow_sw 0 -b:v <target> -maxrate <maxrate> -bufsize <bufsize>` | - | Per Discoveries 02, 09 |
| 5.7 | [ ] | Add pixel format param | 1 | `-pix_fmt yuv420p` | - | Per Discovery 05 |
| 5.8 | [ ] | Add H.264 profile (if h264) | 1 | `if codec == "h264": cmd += ["-profile:v", "high"]` | - | Per Discovery 12 |
| 5.9 | [ ] | Add HEVC profile and tag (if hevc) | 1 | `if codec == "hevc": cmd += ["-profile:v", "main", "-tag:v", "hvc1"]` | - | Per Discoveries 06, 12 |
| 5.10 | [ ] | Preserve existing CRF logic for non-VT | 2 | `else: cmd += ["-crf", "23" if not use_gpu else "18"]` (exact replica of line 461) | - | NVENC/CPU paths unchanged |
| 5.11 | [ ] | Manual test: verify VT command construction | 1 | Print constructed command, verify VT params present, no `-crf` | - | `--gpu --quality balanced` on Mac |
| 5.12 | [ ] | Manual test: verify NVENC command unchanged | 1 | Print command on non-Darwin, verify `-crf 18` present, no VT params | - | Code review or NVIDIA test |

### Non-Happy-Path Coverage
- [ ] Missing width/height (use default 1920×1080 or error)
- [ ] Unknown codec (vt_active=False, falls through to CRF path)
- [ ] Encoder is None (handled in Phase 6 pre-flight check)

### Acceptance Criteria
- [ ] All 12 tasks completed
- [ ] VideoToolbox commands include: `-allow_sw 0`, `-b:v`, `-maxrate`, `-bufsize`, `-pix_fmt yuv420p`
- [ ] H.264 VT commands include: `-profile:v high`
- [ ] HEVC VT commands include: `-profile:v main`, `-tag:v hvc1`
- [ ] NVENC/CPU commands still use `-crf` (unchanged)
- [ ] No CRF parameter when VideoToolbox active
- [ ] Command construction tested via print/logging

---

### Phase 6: Error Handling & Validation

**Objective**: Implement pre-flight validation checks and FFmpeg error parsing to provide explicit, actionable error messages when GPU encoding unavailable or fails.

**Deliverables**:
- Pre-flight validation before FFmpeg execution
- `parse_vt_error()` function for stderr parsing
- User-friendly error messages for common failure modes

**Dependencies**:
- Phase 1 (Hardware Detection) - uses `detect_apple_silicon()`
- Phase 4 (Encoder Selection) - handles `encoder=None` cases

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Missing error pattern | Medium | Medium | Log all unhandled errors, update patterns based on testing |
| Over-broad error matching | Low | Medium | Use specific patterns, test against varied stderr output |

### Tasks (Manual Testing Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 6.1 | [ ] | Implement `parse_vt_error()` skeleton | 2 | Function signature: `parse_vt_error(stderr: str) -> Optional[str]`, returns None for unrecognized errors | - | Returns user-friendly message or None |
| 6.2 | [ ] | Add "hardware busy" error pattern | 1 | Detects "cannot create compression session" or "hardware encoder may be busy" | - | Per Discovery 10 (Research § 4) |
| 6.3 | [ ] | Add "missing encoder" error pattern | 1 | Detects "no such encoder" + "videotoolbox" | - | Per Discovery 08 (Research § 4) |
| 6.4 | [ ] | Add "pixel format" error pattern | 1 | Detects "incompatible pixel format" or "auto-selecting format" | - | Per Discovery 05 (Research § 4) |
| 6.5 | [ ] | Add pre-flight validation block in `run_ffmpeg_processing()` | 2 | `if vcodec is None and use_gpu: raise SystemExit(...)` before command execution | - | Lines before `cmd = ["ffmpeg", ...]` |
| 6.6 | [ ] | Add Intel Mac error message | 1 | `if not asi.is_apple_silicon: SystemExit("ERROR: --gpu requires Apple Silicon...")` | - | Uses `detect_apple_silicon()` |
| 6.7 | [ ] | Add missing VT error message | 1 | `if not ffmpeg_has_videotoolbox_encoders(): SystemExit("ERROR: FFmpeg missing VT...")` | - | Suggests Homebrew install |
| 6.8 | [ ] | Add AV1 not supported error | 1 | `if codec_key == "av1": SystemExit("ERROR: AV1 not available via VideoToolbox...")` | - | Per Discovery 04 |
| 6.9 | [ ] | Wrap FFmpeg execution with error parsing | 2 | `except CalledProcessError: hint = parse_vt_error(stderr); raise SystemExit(hint or generic)` | - | Enhances existing error handling |
| 6.10 | [ ] | Manual test: Intel Mac + --gpu triggers error | 1 | Running with `--gpu` on Intel Mac shows: "requires Apple Silicon" and exits | - | Code review or Intel test |
| 6.11 | [ ] | Manual test: missing VT in FFmpeg triggers error | 1 | Temporarily rename encoder in codec_map, verify error: "FFmpeg missing VideoToolbox" | - | Simulate missing encoder |
| 6.12 | [ ] | Manual test: AV1 + --gpu triggers error | 1 | `--input av1.mp4 --gpu` shows: "AV1 not available via VideoToolbox" | - | Need AV1 test file |

### Non-Happy-Path Coverage
- [ ] Intel Mac + --gpu (explicit error)
- [ ] Apple Silicon + missing VT in FFmpeg (explicit error)
- [ ] AV1 codec + --gpu on Mac (explicit error)
- [ ] Hardware busy during encoding (parsed error with guidance)
- [ ] Pixel format mismatch (parsed error with filter suggestion)
- [ ] Unknown VT error (generic error with full stderr)

### Acceptance Criteria
- [ ] All 12 tasks completed
- [ ] Pre-flight validation catches all known incompatibilities before FFmpeg runs
- [ ] `parse_vt_error()` recognizes common VideoToolbox error patterns
- [ ] Error messages are actionable (suggest fixes, not just state problem)
- [ ] No silent failures or generic "processing failed" errors
- [ ] All error paths tested manually or via code review

---

### Phase 7: Status Display

**Objective**: Add clear status messages showing which encoder and chip are being used, confirming GPU acceleration to users.

**Deliverables**:
- Status message for VideoToolbox encoding
- Status message for NVENC encoding (informational, optional)
- Optional Rosetta warning

**Dependencies**:
- Phase 1 (Hardware Detection) - provides chip name
- Phase 5 (Parameter Integration) - defines `vt_active` flag

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Chip name parsing fails | Low | Low | Fallback to "Unknown Apple Silicon" acceptable |
| Message clutters output | Low | Low | Single line, clear formatting |

### Tasks (Manual Testing Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 7.1 | [ ] | Add VideoToolbox status message | 2 | After encoder selection, `if vt_active: print(f"Using VideoToolbox on {asi.chip}")` | - | Per Discovery 11 (Research § 6) |
| 7.2 | [ ] | Add Rosetta detection to status | 1 | Append `(Rosetta)` if `asi.under_rosetta=True` | - | Per Discovery 13 (optional warning) |
| 7.3 | [ ] | Add NVENC status message (optional) | 1 | `elif use_gpu and "nvenc" in vcodec: print("Using NVIDIA NVENC")` | - | Informational parity |
| 7.4 | [ ] | Manual test: status message on Apple Silicon | 1 | `--gpu` on M2 shows: "Using VideoToolbox on Apple M2" | - | Verify correct chip name |
| 7.5 | [ ] | Manual test: Rosetta warning if applicable | 1 | If under Rosetta, message shows: "Using VideoToolbox on Apple M2 (Rosetta)" | - | Optional test if Rosetta available |
| 7.6 | [ ] | Manual test: NVENC status (if testable) | 1 | `--gpu` on NVIDIA shows: "Using NVIDIA NVENC" | - | Code review if NVIDIA unavailable |

### Non-Happy-Path Coverage
- [ ] Chip name unavailable (show "Unknown Apple Silicon")
- [ ] `system_profiler` timeout (fallback name, message still displays)

### Acceptance Criteria
- [ ] All 6 tasks completed
- [ ] Status message displays before encoding starts
- [ ] Chip model correctly identified (M1/M2/M3) when available
- [ ] Rosetta status shown if detected
- [ ] Message formatting clean and non-intrusive
- [ ] NVENC status message functional if added

---

### Phase 8: Manual Testing & Validation

**Objective**: Comprehensive end-to-end validation of all VideoToolbox functionality, error paths, and NVENC regression testing through manual execution scenarios.

**Deliverables**:
- Test execution log with results for all scenarios
- Verification of GPU utilization via Activity Monitor
- Observational validation of performance/power improvements
- Confirmation of NVENC path unchanged

**Dependencies**:
- Phases 1-7 all complete (full implementation)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Insufficient test coverage | Medium | High | Follow comprehensive test checklist from spec |
| No NVIDIA hardware for regression test | High | Medium | Code review confirmation of NVENC unchanged |
| Quality issues discovered late | Medium | Medium | Test multiple resolutions/codecs, iterate if needed |

### Tasks (Manual Testing Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 8.1 | [ ] | Verify FFmpeg VideoToolbox availability | 1 | `ffmpeg -encoders \| grep videotoolbox` shows h264_videotoolbox and hevc_videotoolbox | - | Pre-flight check |
| 8.2 | [ ] | Test H.264 encoding with balanced preset | 2 | `--gpu --quality balanced` with H.264 input → successful encode, ~20 Mbps bitrate | - | Core functionality |
| 8.3 | [ ] | Test HEVC encoding with quality preset | 2 | `--gpu --quality quality` with HEVC input → successful encode, ~30 Mbps bitrate | - | HEVC + tag validation |
| 8.4 | [ ] | Test fast preset (12 Mbps) | 2 | `--gpu --quality fast` → successful encode, ~12 Mbps bitrate | - | Low bitrate validation |
| 8.5 | [ ] | Verify GPU utilization in Activity Monitor | 2 | During encode, Activity Monitor → GPU tab shows spike in GPU usage | - | Screenshot or observation notes |
| 8.6 | [ ] | Observe system behavior (heat/fans/battery) | 2 | System cooler/quieter than CPU encoding, slower battery drain on MacBook | - | Subjective validation |
| 8.7 | [ ] | Test with overlays/indicators enabled | 2 | `--gpu --indicator` → overlays render correctly, no pixel format errors | - | Filter compatibility |
| 8.8 | [ ] | Test multiple resolutions (720p, 1080p, 4K) | 2 | All resolutions encode successfully, file sizes proportional to resolution | - | Bitrate scaling validation |
| 8.9 | [ ] | Test error: Intel Mac + --gpu | 2 | Running on Intel Mac with `--gpu` → error: "requires Apple Silicon" | - | Pre-flight validation check |
| 8.10 | [ ] | Test error: AV1 + --gpu | 2 | AV1 input + `--gpu` → error: "AV1 not available via VideoToolbox" | - | AV1 exclusion check |
| 8.11 | [ ] | Test CPU fallback (no --gpu flag) | 2 | Process video without `--gpu` → libx264/libx265 encoding, no changes from baseline | - | Regression: CPU path unchanged |
| 8.12 | [ ] | NVENC regression test (or code review) | 2 | On NVIDIA system, `--gpu` uses NVENC with `-crf 18`, identical to pre-modification | - | Code review if hardware unavailable |
| 8.13 | [ ] | Document all test results in execution log | 1 | Log contains: commands, outcomes, GPU usage observations, errors encountered | - | Evidence for acceptance |

### Non-Happy-Path Coverage
- [ ] Very short video (< 10 seconds)
- [ ] Very long video (> 1 hour)
- [ ] Low resolution (480p) - check bitrate scaling
- [ ] Multiple silence segments
- [ ] No silence segments (all normal speed)
- [ ] Complex overlay graphics

### Acceptance Criteria
- [ ] All 13 tasks completed with documented results
- [ ] H.264 and HEVC VideoToolbox encoding functional
- [ ] All three quality presets produce expected bitrates
- [ ] GPU utilization observable in Activity Monitor
- [ ] System observably cooler/quieter than CPU encoding
- [ ] Error messages tested and confirmed actionable
- [ ] NVENC path confirmed unchanged (test or review)
- [ ] No regressions in CPU encoding or core functionality
- [ ] Test log provides evidence for all success criteria

---

### Phase 9: Documentation

**Objective**: Update README.md with Mac GPU acceleration usage instructions, requirements, troubleshooting, and quality preset guidance.

**Deliverables**:
- New "GPU Acceleration" section in README.md
- Mac-specific subsection with requirements
- `--quality` flag documentation
- Troubleshooting section for common errors

**Dependencies**:
- Phase 8 (Testing) - provides validated usage patterns and tested commands

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Documentation drift | Medium | Low | Review README during future changes |
| Unclear instructions | Low | Medium | Use tested commands verbatim, include examples |

### Tasks (Manual Testing Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 9.1 | [ ] | Create "GPU Acceleration" section outline | 1 | Section includes: Overview, Requirements, Usage, Quality Presets, Troubleshooting | - | Use existing README structure |
| 9.2 | [ ] | Document Mac requirements | 1 | Lists: Apple Silicon (M1/M2/M3), macOS 11+, FFmpeg with VideoToolbox | - | Per spec requirements |
| 9.3 | [ ] | Document `--gpu` flag usage | 1 | Explains auto-detection (VT on Mac, NVENC on NVIDIA), provides example command | - | `videospeeder -i input.mp4 -o output.mp4 --gpu` |
| 9.4 | [ ] | Document `--quality` presets | 2 | Table or list: fast (12 Mbps), balanced (20 Mbps, default), quality (30 Mbps) | - | Per spec clarifications |
| 9.5 | [ ] | Add example commands | 1 | At least 3 examples: basic GPU, GPU + quality preset, GPU + indicator | - | Use tested commands from Phase 8 |
| 9.6 | [ ] | Document GPU utilization benefits | 1 | Explains: faster encoding, lower power consumption, GPU usage observable in Activity Monitor | - | Per spec value proposition |
| 9.7 | [ ] | Add troubleshooting subsection | 2 | Covers: checking FFmpeg VT support, Intel Mac error, hardware busy error, pixel format issues | - | Based on Phase 6 error patterns |
| 9.8 | [ ] | Document explicit failure behavior | 1 | Explains: `--gpu` on unsupported hardware fails with error (no silent CPU fallback) | - | Per spec requirement |
| 9.9 | [ ] | Add note about file sizes | 1 | Warns: VideoToolbox files 2-3x larger than CPU libx265 for equivalent quality | - | Manage expectations |
| 9.10 | [ ] | Review documentation for clarity | 1 | Peer review or self-review: clear flow, tested commands, no broken links | - | Final polish |

### Non-Happy-Path Coverage
- [ ] Documented troubleshooting covers all common error scenarios from Phase 6
- [ ] Includes FFmpeg version compatibility notes

### Acceptance Criteria
- [ ] All 10 tasks completed
- [ ] README.md contains complete GPU Acceleration section
- [ ] Mac requirements clearly listed
- [ ] `--gpu` and `--quality` flags documented with examples
- [ ] Troubleshooting section addresses common errors
- [ ] Commands tested in Phase 8 and verified accurate
- [ ] Documentation reviewed for clarity and completeness
- [ ] No broken links or formatting issues

---

## Cross-Cutting Concerns

### Security Considerations

**Input Validation**:
- File path validation already handled by existing code
- `--quality` choices constrained by argparse
- No user-provided code execution risk

**Command Injection**:
- All FFmpeg parameters constructed programmatically (no string concatenation of user input)
- File paths passed as separate arguments to subprocess (shell=False)
- No risk from new VideoToolbox parameters (all hard-coded or calculated)

**Sensitive Data**:
- No credentials, API keys, or secrets involved
- Local processing only (no network communication)
- No changes to data handling model

### Observability

**Logging Strategy**:
- Status messages show encoder selection and chip model
- Existing FFmpeg stderr output preserved for debugging
- Success/failure clearly indicated via exit codes

**Metrics to Capture** (manual observation):
- GPU utilization (Activity Monitor)
- Encoding speed (subjective comparison)
- Power consumption (battery drain, heat, fan noise)
- Output file size (bitrate verification)

**Error Tracking**:
- VideoToolbox-specific errors parsed and surfaced with guidance
- Unknown errors reported with full FFmpeg stderr
- Exit codes: 0 (success), 1 (error)

### Documentation

**Location**: README.md only (per spec)

**Content Structure**:
1. GPU Acceleration overview
2. Platform requirements (Mac/Windows/Linux)
3. Mac-specific setup (VideoToolbox)
4. NVIDIA-specific setup (NVENC) - already exists
5. Usage examples with `--gpu` and `--quality`
6. Troubleshooting guide

**Target Audience**:
- Mac users with Apple Silicon wanting hardware acceleration
- Existing NVIDIA users (no changes, informational only)
- New users discovering GPU capabilities

**Maintenance**:
- Update when new Mac chips released (M4, M5, etc.)
- Update if FFmpeg VideoToolbox capabilities change
- Update troubleshooting based on user-reported issues

---

## Complexity Tracking

| Component | CS | Label | Breakdown (S,I,D,N,F,T) | Justification | Mitigation |
|-----------|-----|-------|------------------------|---------------|------------|
| Overall Feature | 3 | Medium | S=1,I=1,D=0,N=1,F=1,T=1 | Multi-function changes, platform-specific integration, moderate constraints | Phased implementation, manual testing, explicit error handling |
| Baseline Validation (Phase 0) | 1 | Trivial | S=0,I=1,D=0,N=0,F=0,T=0 | Testing only, no code changes, FFmpeg availability check | Pre-implementation validation, establish working baseline |
| Hardware Detection (Phase 1) | 2 | Small | S=1,I=0,D=0,N=0,F=0,T=1 | New module with helpers, well-understood sysctl API, manual testing | Use proven research patterns, graceful fallbacks |
| Codec Mapping Extension (Phase 2) | 1 | Trivial | S=0,I=0,D=0,N=0,F=0,T=0 | Single dict modification, no behavior change | Code review for NVENC preservation |
| Quality Preset System (Phase 3) | 2 | Small | S=1,I=0,D=0,N=0,F=0,T=1 | CLI arg + helper function, straightforward calculation | Test calculations, validate argparse |
| Encoder Selection Logic (Phase 4) | 3 | Medium | S=1,I=1,D=0,N=1,F=0,T=1 | Platform branching, FFmpeg detection, sentinel returns | Preserve NVENC path, thorough error handling in Phase 6 |
| VideoToolbox Parameters (Phase 5) | 3 | Medium | S=1,I=1,D=0,N=1,F=1,T=1 | Command construction changes, bitrate vs CRF, pixel format compatibility | Conditional branching, extensive manual testing |
| Error Handling (Phase 6) | 3 | Medium | S=1,I=1,D=0,N=1,F=0,T=1 | Error parsing, pre-flight validation, actionable messages | Pattern-based parsing, comprehensive error scenarios |
| Status Display (Phase 7) | 1 | Trivial | S=0,I=0,D=0,N=0,F=0,T=0 | Single print statement enhancement | Simple message formatting |
| Manual Testing (Phase 8) | 2 | Small | S=0,I=1,D=0,N=0,F=0,T=2 | Multi-scenario validation, GPU observation, regression testing | Checklist-driven testing, documented evidence |
| Documentation (Phase 9) | 2 | Small | S=0,I=0,D=0,N=0,F=0,T=1 | README updates, examples, troubleshooting | Use tested commands, clear structure |

**Note**: No CS ≥ 4 components, so no feature flags or staged rollout required.

---

## Progress Tracking

### Phase Completion Checklist

- [ ] Phase 0: Baseline Validation - PENDING
- [ ] Phase 1: Hardware Detection Infrastructure - PENDING
- [ ] Phase 2: Codec Mapping Extension - PENDING
- [ ] Phase 3: Quality Preset System - PENDING
- [ ] Phase 4: Encoder Selection Logic - PENDING
- [ ] Phase 5: VideoToolbox Parameter Integration - PENDING
- [ ] Phase 6: Error Handling & Validation - PENDING
- [ ] Phase 7: Status Display - PENDING
- [ ] Phase 8: Manual Testing & Validation - PENDING
- [ ] Phase 9: Documentation - PENDING

### STOP Rule

**IMPORTANT**: This plan must be validated before creating tasks.

**Next Steps**:
1. Run `/plan-4-complete-the-plan` to validate readiness
2. Only proceed to `/plan-5-phase-tasks-and-brief` after validation passes
3. Each phase implementation should follow plan order (Phase 0 → 1 → 2 → 3 → ... → 9)

**Validation Criteria**:
- [ ] All phases have explicit objectives and deliverables
- [ ] All tasks have clear success criteria
- [ ] Dependencies between phases documented
- [ ] Risks identified with mitigations
- [ ] Testing approach aligns with spec (Manual Only)
- [ ] Documentation strategy aligns with spec (README.md only)
- [ ] No time estimates present (only CS complexity scores)
- [ ] All research findings incorporated into appropriate phases

---

## Change Footnotes Ledger

**NOTE**: This section will be populated during implementation by plan-6a-update-progress.

**Footnote Numbering Authority**: plan-6a-update-progress is the **single source of truth** for footnote numbering across the entire plan.

**Initial State** (before implementation begins):

[^1]: [To be added during implementation via plan-6a]
[^2]: [To be added during implementation via plan-6a]
[^3]: [To be added during implementation via plan-6a]
[^4]: [To be added during implementation via plan-6a]
[^5]: [To be added during implementation via plan-6a]

---

## Appendix A: Research Summary

Complete research findings available in [research.md](/Users/jordanknight/github/videospeeder/docs/plans/5-mac-gpu-acceleration/research.md).

**Key Takeaways**:
1. Production-ready hardware detection code using `sysctl` (handles Rosetta)
2. Extend codec_map, don't rewrite (NVENC preservation)
3. VideoToolbox uses bitrate control (`-b:v`), NOT CRF
4. Explicit failure mode with `-allow_sw 0`
5. Pixel format must be `yuv420p` for compatibility
6. HEVC requires `-tag:v hvc1` for QuickTime/Safari
7. No AV1 encoder via VideoToolbox in FFmpeg
8. VBV constrained bitrate pattern recommended (maxrate, bufsize)
9. Error patterns documented for hardware busy, missing VT, pixel format
10. YouTube bitrate recommendations: 8-12 Mbps (1080p H.264), 15-20 Mbps (HEVC)

---

## Appendix B: Anchor Naming Conventions

All deep links in the FlowSpace provenance graph use kebab-case anchors:

### Phase Anchors
**Format**: `phase-{number}-{slug}`
**Examples**:
- `phase-1-hardware-detection-infrastructure`
- `phase-5-videotoolbox-parameter-integration`

### Task Anchors (Plan)
**Format**: `task-{number}-{slug}` (use flattened number: 2.3 → 23)
**Examples**:
- `task-11-add-applesiliconinfo-class-definition`
- `task-56-add-bitrate-control-params`

### Slugification Rules
1. Convert to lowercase
2. Replace spaces with hyphens
3. Replace non-alphanumeric (except hyphens) with hyphens
4. Collapse multiple hyphens to single hyphen
5. Trim leading/trailing hyphens

**Command**:
```bash
ANCHOR=$(echo "${INPUT}" | tr ' ' '-' | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')
```

---

**Plan Status**: DRAFT - Ready for validation via `/plan-4-complete-the-plan`
