# Mac GPU Acceleration Support

## Summary

Enable VideoSpeeder to utilize Apple's VideoToolbox hardware acceleration on macOS (particularly Apple Silicon M1/M2/M3 chips) for GPU-accelerated video encoding and improved power efficiency. Currently, GPU acceleration only works with NVIDIA GPUs via NVENC, leaving Mac users without hardware acceleration benefits.

**Value Proposition:** Mac users, especially those with Apple Silicon chips, gain GPU-accelerated encoding which is noticeably faster and more power-efficient than CPU encoding, making VideoSpeeder more practical for longer videos and laptop usage without draining battery.

## Goals

- **Hardware Acceleration Parity:** Mac users gain GPU acceleration capabilities equivalent to what NVIDIA users currently have
- **GPU Utilization:** Enable VideoToolbox GPU encoding on Apple Silicon for noticeably faster processing than CPU-only
- **Power Efficiency:** Reduce power consumption and heat during encoding for better battery life on MacBooks
- **Seamless Experience:** Auto-detect Mac hardware and use appropriate acceleration without requiring users to understand VideoToolbox vs NVENC
- **Quality Preservation:** Maintain acceptable video quality comparable to current GPU and CPU encoding paths
- **Backward Compatibility:** Ensure existing NVENC GPU acceleration for Windows/Linux NVIDIA users remains unchanged and functional
- **Explicit Failure:** Provide clear error messages when GPU acceleration unavailable rather than silent fallback

## Non-Goals

- GPU-accelerating filter operations (overlay, drawtext, concatenation) using Metal shaders - deferred as future enhancement (Phase 2)
- **Supporting Intel Macs with AMD GPUs** - explicitly excluded, focus on Apple Silicon M1/M2/M3 only for maximum performance gains
- Matching exact quality/compression ratio of CPU encoders like libx265 (VideoToolbox prioritizes speed over compression)
- Hardware decode acceleration (disabled when using software filters for overlays/text)
- Publishing standalone Mac-specific version of VideoSpeeder
- Supporting non-Mac platforms with VideoToolbox
- Replacing or removing NVENC support
- Automatic CPU fallback when --gpu flag is used (will fail explicitly with clear error instead)

## Complexity

**Score:** CS-3 (medium)

**Breakdown:**
- **Surface Area (S):** 1 - Multiple functions within videospeeder.py (hardware detection, codec mapping, encoder selection)
- **Integration Breadth (I):** 1 - One external dependency (VideoToolbox via FFmpeg, platform-specific)
- **Data & State (D):** 0 - No schema changes or data migrations, runtime configuration only
- **Novelty & Ambiguity (N):** 1 - Requirements fairly clear but some unknowns around quality tuning and edge cases
- **Non-Functional Constraints (F):** 1 - Moderate performance requirements (GPU utilization observable), power efficiency goals
- **Testing & Rollout (T):** 1 - Integration testing required on Apple Silicon, verify NVENC unchanged, CPU fallback testing

**Total Points:** P = 5 → **CS-3 (medium)**

**Confidence:** 0.80

**Assumptions:**
- FFmpeg on Mac already has VideoToolbox encoders compiled in (standard Homebrew build includes this)
- Users have macOS 11+ (Big Sur or later) for optimal VideoToolbox support
- Apple Silicon M1/M2/M3 chips provide VideoToolbox GPU acceleration
- Bitrate-based quality control is acceptable substitute for CRF (VideoToolbox limitation)
- CPU-based filtering + GPU encoding hybrid approach provides sufficient benefit
- Existing overlay/drawtext CPU filters remain acceptable

**Dependencies:**
- FFmpeg 4.x+ with VideoToolbox support (included in Homebrew builds)
- macOS 11+ (Big Sur) for stable VideoToolbox API
- Apple Silicon hardware for testing and validation (M1/M2/M3)
- Python `platform` and `subprocess` standard library modules for hardware detection

**Risks:**
- **Quality variability:** VideoToolbox uses bitrate control instead of CRF, may produce inconsistent quality across different video types
- **File size increase:** VideoToolbox prioritizes speed, resulting in 2-3x larger files than CPU libx265 for equivalent quality
- **Platform fragmentation:** Different behavior between Apple Silicon and Intel Macs may complicate testing
- **Filter bottleneck:** CPU-based overlay/drawtext operations may become the new bottleneck after encoding is accelerated
- **FFmpeg version dependency:** Older FFmpeg versions or custom builds may lack VideoToolbox support
- **Pixel format issues:** VideoToolbox requires explicit pixel format specification which may cause encoding failures

**Phases:**
1. **Hardware Detection:** Implement macOS platform and Apple Silicon chip detection (M1/M2/M3)
2. **Encoder Integration:** Add VideoToolbox encoders to codec mapping alongside NVENC
3. **Selection Logic:** Update `--gpu` flag to auto-detect hardware (VideoToolbox on Apple Silicon, NVENC on NVIDIA)
4. **Quality Presets:** Implement `--quality` flag with three presets: fast (12Mbps), balanced (20Mbps, default), quality (30Mbps)
5. **Status Display:** Add encoder status message at processing start (e.g., "Using VideoToolbox on Apple M2")
6. **Error Handling:** Implement explicit failure with helpful error when GPU unavailable (no silent CPU fallback)
7. **Testing:** Manual validation on Apple Silicon with H.264/HEVC, various formats and resolutions
8. **Documentation:** Update README with Mac GPU acceleration section, requirements, and quality preset usage

## Acceptance Criteria

### 1. Auto-Detection and Hardware Selection
**Given** a user runs VideoSpeeder on an Apple Silicon Mac with the `--gpu` flag,
**When** processing begins,
**Then** the system automatically detects Apple Silicon and uses VideoToolbox encoding without requiring Mac-specific flags.

### 2. GPU Encoding Verification
**Given** a user processes a video on Apple Silicon with the `--gpu` flag,
**When** observing system activity (Activity Monitor GPU usage, processing speed, fan noise),
**Then** it's visually apparent that GPU encoding is active (high GPU utilization, noticeably faster than CPU, cooler/quieter system).

### 3. Power Efficiency Observable
**Given** a MacBook user processes videos with VideoToolbox encoding,
**When** observing system behavior (fan noise, battery drain, heat),
**Then** system runs cooler and quieter than CPU encoding, with noticeably slower battery drain during processing.

### 4. Quality Preservation
**Given** a user encodes a video with VideoToolbox,
**When** comparing output quality to NVENC or CPU encoding,
**Then** visual quality is acceptable for typical use cases despite larger file sizes (2-3x).

### 5. NVENC Compatibility Unchanged
**Given** a user with NVIDIA GPU on Windows/Linux runs VideoSpeeder with `--gpu`,
**When** processing a video,
**Then** NVENC path executes exactly as before with no behavioral changes or regressions.

### 6. Explicit Failure When GPU Unavailable
**Given** VideoToolbox is unavailable (old macOS, Intel Mac, or FFmpeg without VideoToolbox) and user specifies --gpu flag,
**When** attempting to start encoding,
**Then** system exits with clear error message explaining why GPU acceleration failed and suggesting retry without --gpu flag (CPU encoding).

### 7. Multi-Codec Support
**Given** a user processes H.264, HEVC, or AV1 video on Apple Silicon,
**When** using VideoToolbox acceleration,
**Then** appropriate VideoToolbox encoder (h264_videotoolbox, hevc_videotoolbox) is selected and encoding succeeds.

### 8. Explicit Control Option
**Given** a user wants to force VideoToolbox usage or explicitly disable it,
**When** using `--gpu-mac` flag,
**Then** VideoToolbox is used regardless of auto-detection (or error if unavailable).

### 9. Error Handling
**Given** VideoToolbox encoding fails mid-process (corrupted frames, unsupported format),
**When** error occurs,
**Then** user receives clear error message explaining the failure and suggesting CPU fallback retry.

### 10. Documentation Clarity
**Given** a new Mac user reads the README,
**When** looking for GPU acceleration instructions,
**Then** Mac-specific VideoToolbox acceleration is clearly documented with performance expectations and requirements.

### 11. Quality Preset Functionality
**Given** a user wants to control output quality/file size tradeoff,
**When** using `--quality fast`, `--quality balanced`, or `--quality quality` flags,
**Then** VideoToolbox encoding uses 12Mbps, 20Mbps, or 30Mbps bitrate respectively, with balanced as the default when no flag specified.

### 12. Encoder Status Display
**Given** a user starts video processing with --gpu flag on Apple Silicon,
**When** encoding begins,
**Then** a status message displays showing "Using VideoToolbox on Apple [M1/M2/M3]" to confirm GPU acceleration is active.

## Risks & Assumptions

### Risks

1. **Inconsistent Quality Output**
   - VideoToolbox uses bitrate control rather than constant quality (CRF)
   - May produce variable quality across different video types and motion profiles
   - **Mitigation:** Provide recommended bitrate presets for common resolutions; allow user override

2. **Large File Sizes**
   - VideoToolbox prioritizes speed over compression efficiency
   - Files may be 2-3x larger than CPU libx265 at equivalent visual quality
   - **Mitigation:** Document trade-off clearly; users can choose CPU for size-critical workflows

3. **Platform Fragmentation**
   - Apple Silicon vs Intel Mac behavior differs
   - Older macOS versions may have limited or buggy VideoToolbox support
   - **Mitigation:** Target macOS 11+ and Apple Silicon primarily; test on multiple macOS versions

4. **Filter Bottleneck Shift**
   - After accelerating encoding, overlay/drawtext CPU operations become dominant bottleneck
   - Users may expect further acceleration that requires Metal shader implementation
   - **Mitigation:** Set expectations clearly; document that filtering remains CPU-bound in Phase 1

5. **FFmpeg Dependency Variability**
   - Not all FFmpeg builds include VideoToolbox support
   - Custom/older builds may fail silently or with cryptic errors
   - **Mitigation:** Document required FFmpeg version and recommend Homebrew installation

6. **Pixel Format Compatibility**
   - VideoToolbox requires explicit pixel format specification
   - Some source videos may have incompatible pixel formats requiring conversion
   - **Mitigation:** Auto-detect and convert pixel formats with helpful error messages

### Assumptions

1. **FFmpeg Availability:** macOS users installing VideoSpeeder have or can easily install FFmpeg via Homebrew with VideoToolbox support
2. **GPU Acceleration:** VideoToolbox provides GPU-accelerated encoding on Apple Silicon that is observably faster and more efficient than CPU
3. **User Acceptance:** Users accept larger file sizes (2-3x) in exchange for GPU acceleration and lower power consumption
4. **Backward Compatibility:** Changes to videospeeder.py can cleanly separate NVENC and VideoToolbox paths without refactoring
5. **CPU Filtering Acceptable:** Users are satisfied with Phase 1 (GPU encoding only) without requiring Metal-based GPU filtering
6. **Quality Sufficient:** Bitrate-based quality control produces acceptable output for most VideoSpeeder use cases
7. **Apple Silicon Focus:** Majority of Mac users benefiting from this feature are on Apple Silicon (M1/M2/M3) rather than Intel Macs

## Open Questions

### Resolved (Session 2025-11-09)

1. ✅ **Quality Parameter Mapping:** RESOLVED - Use 20Mbps bitrate (YouTube-optimized) as balanced default. Add --quality preset flags (fast=12Mbps, balanced=20Mbps, quality=30Mbps).

2. ✅ **Intel Mac Support Priority:** RESOLVED - Apple Silicon only (M1/M2/M3). Intel Macs fall back to CPU encoding.

3. ✅ **Flag Naming Convention:** RESOLVED - `--gpu` auto-detects hardware (NVENC on NVIDIA, VideoToolbox on Mac). Single flag for simplest UX.

4. ✅ **Fallback Behavior:** RESOLVED - Fail with helpful error when `--gpu` flag used but GPU unavailable. No silent CPU fallback. Exit explicitly with clear error message.

5. ✅ **Performance Metrics Display:** RESOLVED - Show acceleration status at start of processing (e.g., "Using VideoToolbox on Apple M2"). Helps users confirm GPU active.

6. ✅ **Preset Profiles:** RESOLVED - Add `--quality` flag with three presets: fast (12Mbps), balanced (20Mbps, default), quality (30Mbps).

### Deferred

7. **Future Metal Filter Path:** DEFERRED - Metal-based GPU filtering (Phase 2) is out of scope for initial implementation. Focus on VideoToolbox encoding only in Phase 1.

## ADR Seeds (Optional)

### Decision Drivers

- **GPU Utilization:** Enable VideoToolbox GPU encoding on Apple Silicon (observable via Activity Monitor)
- **Power Efficiency:** Important for MacBook users to enable practical video processing on battery
- **Compatibility:** Cannot break existing NVENC paths or regress functionality for Windows/Linux users
- **Maintainability:** Code changes must be clean and separable without major refactoring
- **User Experience:** Mac users should get GPU acceleration with minimal configuration (auto-detect preferred)
- **Quality Acceptable:** Output quality must be acceptable even if compression ratio is worse than CPU
- **Reliability:** Must provide clear error messages when GPU unavailable

### Candidate Alternatives

**A. Hybrid CPU Filter + VideoToolbox Encode (Recommended)**
- Keep all filtering (overlay, drawtext, concat) on CPU
- Use VideoToolbox only for video encoding
- Pros: Proven reliable, minimal changes, no hwdownload/hwupload complexity
- Cons: Filtering remains bottleneck (~45% of time), leaves performance on table

**B. Full GPU Pipeline with Metal Shaders**
- Implement custom Metal shaders for overlay, drawtext operations
- End-to-end GPU processing (Metal filters → VideoToolbox encode)
- Pros: Maximum GPU utilization, complete hardware acceleration pipeline
- Cons: Very high complexity, significant custom code, maintenance burden, testing complexity

**C. VideoToolbox Decode + Encode**
- Use VideoToolbox for both decoding and encoding
- Requires hwdownload filter for CPU-based overlays
- Pros: Theoretically faster decode
- Cons: hwdownload negates most decode benefits, adds complexity, already disabled in current code

**D. Separate videospeeder_mac.py Script**
- Create Mac-specific script with VideoToolbox-only code
- Pros: Clean separation, no NVENC code mixing
- Cons: Code duplication, maintenance burden, confusing UX (which script to use?)

**E. Do Nothing / Wait for ffmpeg Metal Filters**
- Wait for FFmpeg to add Metal-based overlay/drawtext filters natively
- Pros: Zero implementation effort, future-proof
- Cons: Uncertain timeline (may never happen), Mac users miss out on current benefits

### Stakeholders

- **Mac Users (especially Apple Silicon):** Primary beneficiaries, want fast processing and good battery life
- **Existing NVENC Users:** Must not experience regressions or behavior changes
- **Project Maintainers:** Want clean, maintainable code without excessive complexity
- **Future Contributors:** Need clear architecture to add AMD/Intel GPU support later
- **Performance-Conscious Users:** Want fastest possible processing regardless of platform

---

## Clarifications

### Session 2025-11-09

**Q1: Testing Strategy**
- **Answer:** Manual Only
- **Rationale:** "non needed this is just a small util"

**Q2: Documentation Strategy**
- **Answer:** README.md only
- **Rationale:** User selected README.md only for documentation

**Q3: Flag Naming Convention**
- **Answer:** --gpu auto-detects (Recommended)
- **Rationale:** Single --gpu flag automatically detects hardware (NVENC on NVIDIA, VideoToolbox on Mac). Simplest UX.

**Q4: Fallback Behavior**
- **Answer:** Fail with helpful error
- **Rationale:** "we want to crash out if gpu flag was used. If no gpu flag then it will have just done cpu anyway right?" - When --gpu is explicitly used, failure should be explicit with clear error message. No silent fallback.

**Q5: Performance Metrics Display**
- **Answer:** Show acceleration status
- **Rationale:** Display which encoder is being used at start of processing to help users confirm GPU is active.

**Q6: Quality Parameters for VideoToolbox**
- **Answer:** Start with 20Mbps bitrate (YouTube-optimized)
- **Rationale:** User asked "What would be best for youtube?" - 20Mbps is at the high end of YouTube's recommended bitrate range for 1080p (8-12Mbps H.264, 15-20Mbps HEVC). This ensures good quality even after YouTube's reencoding while keeping file sizes reasonable.

**Q7: Intel Mac Support**
- **Answer:** Apple Silicon only (M1/M2/M3)
- **Rationale:** Focus on Apple Silicon where performance gains are significant. Simpler implementation and testing.

**Q8: Quality Presets**
- **Answer:** Preset flags (--quality fast/quality)
- **Rationale:** Add --quality flag with presets: fast (12Mbps), balanced (20Mbps, default), quality (30Mbps). Provides easy control over quality/size tradeoff.

## Testing Strategy

**Approach:** Manual Only

**Rationale:** This is a small utility feature adding GPU acceleration. The scope is limited to hardware detection and encoder selection, which can be validated through manual testing with real videos on Apple Silicon hardware.

**Manual Verification Steps:**
1. Test VideoToolbox encoding on Apple Silicon with `--gpu` flag
2. Verify GPU utilization in Activity Monitor during processing
3. Observe system behavior (fan noise, heat, battery drain) compared to CPU encoding
4. Confirm NVENC path unchanged on NVIDIA hardware (if available)
5. Test CPU fallback when VideoToolbox unavailable
6. Verify H.264 and HEVC encoding with various video formats
7. Visual quality comparison between VideoToolbox and CPU/NVENC output

**Focus Areas:**
- Hardware auto-detection works correctly on M1/M2/M3
- VideoToolbox encoder selected and functional
- Explicit failure with clear error when GPU unavailable (no silent fallback)
- NVENC paths remain unaffected

**Excluded:**
- Automated unit tests for hardware detection
- Integration tests for encoder selection
- Performance benchmarking automation

## Documentation Strategy

**Location:** README.md only

**Rationale:** Keep documentation simple and centralized in the main README where users first look for usage instructions.

**Content to Add:**
- GPU Acceleration section in README
- Mac-specific requirements (macOS 11+, Apple Silicon M1/M2/M3)
- `--gpu` flag usage for automatic hardware detection
- GPU utilization benefits (faster encoding, lower power consumption)
- Power efficiency benefits for MacBooks
- Troubleshooting: FFmpeg VideoToolbox support verification
- Note about explicit error when GPU unavailable (no silent CPU fallback)
- `--quality` preset options (fast/balanced/quality)

**Target Audience:** Mac users wanting to accelerate video processing, particularly those on Apple Silicon

**Maintenance:** Update README when VideoToolbox quality parameters are tuned or new Mac hardware support is added

---

## Clarification Coverage Summary

**Session Date:** 2025-11-09
**Questions Asked:** 8/8 (maximum)
**Status:** All critical ambiguities resolved

| Category | Status | Decision |
|----------|--------|----------|
| **Testing Strategy** | ✅ Resolved | Manual Only - no automated tests needed for this utility feature |
| **Documentation Strategy** | ✅ Resolved | README.md only - centralized documentation approach |
| **Flag Naming** | ✅ Resolved | --gpu auto-detects hardware (NVENC/VideoToolbox) |
| **Fallback Behavior** | ✅ Resolved | Explicit failure with error when --gpu used but unavailable |
| **Performance Metrics** | ✅ Resolved | Show encoder status at start (e.g., "Using VideoToolbox on Apple M2") |
| **Quality Parameters** | ✅ Resolved | 20Mbps default (YouTube-optimized) with --quality presets |
| **Intel Mac Support** | ✅ Resolved | Apple Silicon only (M1/M2/M3), Intel Macs use CPU |
| **Quality Presets** | ✅ Resolved | Add --quality flag: fast (12Mbps), balanced (20Mbps), quality (30Mbps) |
| **Metal Filters (Phase 2)** | 🔄 Deferred | Out of scope for initial implementation |

**Ready for:** `/plan-3-architect` to generate phase-based implementation plan

---

**Next Steps:**
- Run `/plan-3-architect` to generate the phase-based implementation plan with detailed tasks
- Create ADR for Hybrid CPU Filter + VideoToolbox Encode approach if needed
- Begin Phase 1 implementation once plan approved
