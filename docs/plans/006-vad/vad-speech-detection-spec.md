# Voice Activity Detection (VAD) for Speech-Based Silence Detection

**Mode**: Simple

📚 This specification incorporates findings from `deep-research-findings/` (5 research documents).

## Research Context

**Key Findings from Deep Research:**

- **Current Limitation**: FFmpeg's `silencedetect` filter uses amplitude-based detection (-30dB threshold), which cannot distinguish keyboard typing, mouse clicks, or background noise from actual human speech
- **Recommended Solution**: Silero VAD provides 87.7% TPR at 5% FPR with 14.4 seconds processing per hour of audio
- **Expected Accuracy**: 92-96% on mixed audio (speech + keyboard), with 88-92% correct rejection of keyboard-only segments
- **Integration Point**: Clean separation exists in codebase—VAD can replace `run_silencedetect()` and `parse_silencedetect_output()` without modifying downstream segment processing

**Components Affected:**
- `videospeeder.py`: CLI arguments, detection pipeline, audio extraction
- `requirements.txt`: New dependencies (torch, torchaudio, silero-vad)

**Critical Dependencies:**
- Silero VAD (MIT license, 2MB model)
- PyTorch/torchaudio for model inference
- FFmpeg for audio extraction (already present)

**Modification Risks:**
- New Python dependencies increase package size significantly (~500MB for PyTorch)
- Model loading adds ~1-2 second startup overhead
- Users without PyTorch will need to install it

See `deep-research-findings/` for full analysis.

---

## Summary

VideoSpeeder currently detects "silence" using FFmpeg's amplitude-based `silencedetect` filter. This approach fails for screencast and tutorial videos because keyboard typing, mouse clicks, and background noise register as "content" (not sped up), while the user only wants to preserve actual speech.

**Voice Activity Detection (VAD)** solves this by using machine learning to detect actual human speech characteristics (formants, pitch, harmonic structure) regardless of amplitude. With VAD, typing sounds and background noise are correctly classified as non-speech and sped up, while spoken narration plays at normal speed.

---

## Goals

1. **Accurate Speech Detection**: Users can speed up non-speech segments (keyboard typing, silence, background noise) while preserving all spoken content at normal speed

2. **Seamless User Experience**: A simple `--vad` flag enables VAD mode without requiring users to understand the underlying technology

3. **Backward Compatibility**: Existing `silencedetect` behavior remains available and unchanged for users who prefer it or cannot install VAD dependencies

4. **Screencast Optimization**: Default parameters tuned for the common use case of tutorial/screencast videos with keyboard sounds

5. **Transparency**: Users can see which detection method is active and understand the tradeoff (VAD = better accuracy, silencedetect = fewer dependencies)

---

## Non-Goals

1. **Real-time/streaming VAD**: This feature is for offline video processing only, not live audio streams

2. **Speaker diarization**: We detect speech vs. non-speech, not "who is speaking"

3. **Transcription/speech-to-text**: VAD detects speech presence, not speech content

4. **GPU-accelerated VAD inference**: CPU processing is sufficient (14 seconds per hour of audio)

5. **Custom VAD model training**: We use pre-trained Silero VAD as-is

6. **Noise reduction/audio enhancement**: VAD classifies audio; it does not modify the audio content itself

7. **Automatic threshold tuning**: Users manually adjust threshold if needed (sensible defaults provided)

---

## Complexity

**Score**: CS-3 (medium)

**Breakdown**:
| Dimension | Score | Rationale |
|-----------|-------|-----------|
| **Surface Area (S)** | 1 | Multiple functions in videospeeder.py (detection, audio extraction, CLI args) |
| **Integration (I)** | 1 | One external dependency ecosystem (PyTorch + Silero VAD) |
| **Data/State (D)** | 0 | No schema changes, no persistent state |
| **Novelty (N)** | 1 | Clear requirements from research, some parameter tuning needed |
| **Non-Functional (F)** | 1 | Moderate performance expectations (processing time, memory) |
| **Testing/Rollout (T)** | 1 | Integration testing needed, manual validation on real videos |

**Total Points**: P = 5 → **CS-3 (medium)**

**Confidence**: 0.85

**Assumptions**:
- Users can install PyTorch via pip (standard Python environment)
- Silero VAD accuracy metrics from research hold for typical screencast content
- FFmpeg can extract audio in format suitable for VAD (16kHz mono PCM)
- Memory overhead acceptable (~100MB for model + audio)

**Dependencies**:
- PyTorch >= 1.12.0 (or ONNX runtime as alternative)
- torchaudio >= 0.12.0
- silero-vad package
- FFmpeg (already required)

**Risks**:
- PyTorch installation can be problematic on some systems
- Model download on first run may fail without internet
- Processing time increases slightly compared to silencedetect
- False positives on sustained loud typing may still occur (8-12% rate)

**Phases**:
1. **Phase 1**: Core VAD integration (audio extraction, Silero VAD, segment conversion)
2. **Phase 2**: CLI integration (`--vad` flag, parameter exposure)
3. **Phase 3**: Documentation and testing

---

## Acceptance Criteria

### 1. VAD Flag Enables Speech Detection
**Given** a user runs VideoSpeeder with the `--vad` flag,
**When** processing a video with keyboard typing during silent periods,
**Then** the typing-only segments are sped up while speech segments play at normal speed.

### 2. Keyboard Sounds Correctly Classified as Non-Speech
**Given** a screencast video where the presenter types on a mechanical keyboard during pauses,
**When** processed with `--vad` flag,
**Then** at least 85% of keyboard-only segments are correctly identified as non-speech and sped up.

### 3. Speech Segments Preserved
**Given** a video with mixed speech and keyboard sounds,
**When** processed with `--vad` flag,
**Then** at least 95% of speech segments are correctly identified and play at normal speed.

### 4. Silencedetect Remains Default
**Given** a user runs VideoSpeeder without the `--vad` flag,
**When** processing any video,
**Then** the existing silencedetect behavior is used unchanged (backward compatible).

### 5. Clear Status Message
**Given** a user runs VideoSpeeder with `--vad` flag,
**When** processing begins,
**Then** a status message displays indicating VAD mode is active (e.g., "Using Voice Activity Detection (Silero VAD)").

### 6. Graceful Dependency Error
**Given** a user runs VideoSpeeder with `--vad` flag but VAD dependencies are not installed,
**When** attempting to start,
**Then** the system exits with a clear error message explaining which packages to install.

### 7. VAD Threshold Configurable
**Given** a user wants to tune VAD sensitivity,
**When** using `--vad-threshold 0.8` (or similar parameter),
**Then** the VAD uses the specified threshold instead of the default.

### 8. Processing Completes in Reasonable Time
**Given** a 1-hour video processed with `--vad` flag,
**When** on typical consumer hardware (modern CPU),
**Then** VAD processing adds no more than 30 seconds to total processing time.

### 9. Output Video Quality Unchanged
**Given** a video processed with `--vad` flag,
**When** comparing to the same video processed with `silencedetect`,
**Then** the output video quality (resolution, codec, audio) is identical—only segment timing differs.

### 10. Indicator Overlay Works with VAD
**Given** a user runs VideoSpeeder with both `--vad` and `--indicator` flags,
**When** processing a video,
**Then** the fast-forward indicator overlay appears correctly on sped-up segments identified by VAD.

---

## Risks & Assumptions

### Risks

1. **Dependency Size**: PyTorch adds ~500MB to the installation, which may concern users with limited disk space or bandwidth
   - *Mitigation*: Document ONNX runtime as lighter alternative; make VAD optional

2. **Model Download**: Silero VAD model downloads on first use; may fail without internet
   - *Mitigation*: Document offline model installation; cache model in user directory

3. **False Positives on Loud Typing**: Sustained loud mechanical keyboard typing may still trigger false positives (8-12% rate per research)
   - *Mitigation*: Document threshold tuning; provide `--vad-threshold` parameter

4. **Memory Usage**: Long videos may require chunked processing to avoid memory issues
   - *Mitigation*: Implement streaming audio extraction for videos > 30 minutes

5. **Processing Time**: VAD adds overhead compared to FFmpeg's native silencedetect
   - *Mitigation*: Research shows 14 seconds per hour of audio—acceptable for offline processing

### Assumptions

1. Users have Python 3.8+ with pip access for installing dependencies
2. Typical screencast/tutorial content matches characteristics in VAD research
3. Single-speaker content is the primary use case (not multi-speaker conversations)
4. Users accept the tradeoff of larger dependencies for better accuracy
5. CPU-only processing is acceptable (no GPU required)

---

## Open Questions

1. ~~**[RESOLVED: Threshold Default]**~~ Default threshold is **0.75** (optimized for keyboard noise per research). Users can tune with `--vad-threshold`.

2. ~~**[RESOLVED: Optional Dependencies]**~~ Dependencies **bundled in requirements.txt**. VAD always available after install.

3. ~~**[RESOLVED: ONNX Support]**~~ **Deferred to future enhancement**. PyTorch only for initial implementation.

4. ~~**[RESOLVED: Preprocessing]**~~ **Keep simple** - no high-pass filter. Silero VAD handles noise robustly.

---

## ADR Seeds (Optional)

### Decision Drivers
- User experience: Simple flag to enable better detection
- Accuracy: Must correctly classify keyboard sounds as non-speech
- Compatibility: Cannot break existing silencedetect workflow
- Dependencies: Balance accuracy vs. installation complexity

### Candidate Alternatives

**A. Silero VAD (Recommended)**
- Open-source, MIT license, 87.7% TPR, 2MB model, PyTorch-based

**B. WebRTC VAD**
- Lightweight (<1MB), but only 50% TPR—inadequate for keyboard rejection

**C. Cobra VAD (Picovoice)**
- 98.9% TPR, commercial license required—not suitable for open-source tool

**D. pyannote-audio**
- Research-grade, 50-200MB models, more complex—overkill for binary speech/non-speech

### Stakeholders
- VideoSpeeder users creating screencast/tutorial content
- Developers maintaining the VideoSpeeder codebase
- Users with limited disk space or offline environments (affected by dependencies)

---

## External Research

**Incorporated**:
- `deep-research-findings/01-vad-library-comparison.md`
- `deep-research-findings/02-silero-vad-implementation.md`
- `deep-research-findings/03-mixed-audio-handling.md`
- `deep-research-findings/04-audio-extraction-for-vad.md`
- `deep-research-findings/05-vad-output-to-timestamps.md`

**Key Findings**:
- Silero VAD is the optimal balance of accuracy, speed, and licensing
- 92-96% accuracy on mixed audio (speech + keyboard)
- 14.4 seconds processing per hour of audio
- Threshold 0.75 recommended for screencast content
- Clean integration possible via replacement of detection functions

**Applied To**:
- Goals (accuracy expectations from research)
- Complexity (integration points from research)
- Acceptance Criteria (accuracy thresholds from research)
- Risks (false positive rates from research)

---

## Documentation Strategy

**Location**: README.md only

**Rationale**: Simple feature addition with straightforward usage. Project already documents CLI flags in README.

**Content to Add**:
- `--vad` flag description in usage section
- Note about optional PyTorch/Silero dependencies
- Brief explanation of VAD vs silencedetect tradeoff

**Target Audience**: VideoSpeeder users creating screencast/tutorial content

**Maintenance**: Update README when VAD parameters change

---

## Testing Strategy

**Approach**: Manual Only

**Rationale**: Simple mode feature with clear research backing. Core integration is wiring Silero VAD to replace silencedetect—straightforward with well-documented library.

**Focus Areas**:
- Verify `--vad` flag activates VAD detection
- Confirm keyboard-only segments are sped up
- Confirm speech segments preserved at normal speed
- Test graceful error when dependencies missing

**Excluded**:
- Automated unit tests for VAD wrapper
- Integration test suites
- Performance benchmarks

**Manual Verification Steps**:
1. Process test screencast with keyboard typing using `--vad`
2. Visually confirm typing sections sped up, speech normal
3. Test without VAD dependencies installed (expect clear error)
4. Test with `--indicator` to confirm overlay works

---

## Clarifications

### Session 2025-12-18

| Question | Answer | Rationale |
|----------|--------|-----------|
| **Q1: Workflow Mode** | Simple | Clear research, straightforward integration path |
| **Q2: Testing Strategy** | Manual Only | Simple feature, visual verification sufficient |
| **Q3: Documentation Strategy** | README.md only | Existing pattern for CLI flags |
| **Q4: Threshold Default** | 0.75 | Optimized for keyboard noise per research |
| **Q5: Optional Dependencies** | Bundled | VAD always available after install |
| **Q6: ONNX Support** | Deferred | Keep initial implementation simple |
| **Q7: Preprocessing** | Keep simple | No high-pass filter, Silero handles noise |

**Coverage Summary**:
- ✅ **Resolved**: 7/7 questions (Mode, Testing, Docs, Threshold, Dependencies, ONNX, Preprocessing)
- 🔄 **Deferred**: 1 (ONNX runtime support - future enhancement)
- ❓ **Outstanding**: 0

---

## Next Steps

1. ~~Run `/plan-2-clarify` to resolve open questions~~ ✅ Complete
2. Run `/plan-3-architect` to generate single-phase implementation plan
3. Implement with `--vad` flag as alternative detection backend
