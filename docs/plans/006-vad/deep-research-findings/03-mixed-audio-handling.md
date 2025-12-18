# Handling Mixed Audio: Speech Detection with Background Noise

## The Core Challenge

Screencast/tutorial videos contain:
- **Speech**: Formant structure, harmonic coherence, 85Hz-8kHz range
- **Keyboard clicks**: Percussive transients, 300Hz-4kHz+ range, 1-5ms rise time
- **Background noise**: Fan hum (50/60Hz), HVAC, room tone

**Why amplitude-based detection fails**: Keyboard clicks at -15 to -20dB can exceed quiet speech at -25dB.

## How VAD Distinguishes Speech from Keyboard

Modern VAD models analyze multiple acoustic dimensions:

1. **Spectral Content**: Speech has formant resonances; keyboards have narrow-band transients
2. **Temporal Evolution**: Speech has smooth phoneme transitions; keyboards have sharp attack/decay
3. **Harmonic Structure**: Voiced speech has pitch harmonics; keyboards have no harmonic organization
4. **Zero-Crossing Rate**: Voiced speech has stable patterns; keyboards have high rates

## Expected Accuracy

- **Silero VAD**: 92-96% accuracy on mixed audio
- **Speech detection**: 95%+ of speech segments correctly identified
- **Keyboard rejection**: 88-92% of keyboard-only segments correctly identified as non-speech
- **False positives**: 8-12% (loud sustained typing may trigger)

## Preprocessing Pipeline

### 1. High-Pass Filtering (Optional)
Removes low-frequency rumble without affecting speech:

```python
from scipy.signal import butter, filtfilt

def apply_highpass(audio, cutoff_hz=80, sample_rate=16000, order=4):
    nyquist = sample_rate / 2
    b, a = butter(order, cutoff_hz / nyquist, btype='high')
    return filtfilt(b, a, audio)
```

### 2. Neural Denoising (Optional)
For very noisy audio, use RNNoise or DeepFilterNet:

```python
# RNNoise: Real-time CPU denoising
# https://github.com/xiph/rnnoise
# Provides 3-5dB SNR improvement without severe speech distortion
```

### 3. VAD with Tuned Threshold

```python
# Higher threshold for keyboard-heavy audio
speech_timestamps = get_speech_timestamps(
    audio,
    model,
    threshold=0.75,  # Default 0.5, raise to reduce keyboard false positives
    return_seconds=True
)
```

## Parameter Tuning Strategy

### Threshold Selection
| Audio Type | Recommended Threshold |
|------------|----------------------|
| Clean speech only | 0.5 (default) |
| Speech + light typing | 0.6-0.7 |
| Speech + heavy typing | 0.75-0.85 |
| Very noisy environment | 0.4-0.5 (prioritize recall) |

### Duration Parameters
| Parameter | Recommended | Purpose |
|-----------|-------------|---------|
| `min_speech_duration_ms` | 100-200ms | Capture brief "um", "uh" |
| `min_silence_duration_ms` | 100-150ms | Standard phrase separation |
| `speech_pad_ms` | 50-100ms | Prevent clipping word boundaries |

## Edge Cases

### Quiet Speech During Typing
- VAD detects speech formants even at -25dB
- Keyboard clicks lack formant structure
- Expected accuracy: 85-90% when overlapping

### Typing-Only Sections
- Keyboard clicks lack harmonic structure
- Sharp transients rejected by temporal analysis
- False positive rate: 8-12%

### Brief Vocalizations ("um", "uh")
- Set `min_speech_duration_ms=100-150ms` to capture
- May need to merge nearby segments

## Post-Processing for Clean Segments

```python
def postprocess_segments(segments, min_duration_ms=100, merge_gap_ms=200):
    """Clean up VAD output for better segment quality."""
    if not segments:
        return []

    # Filter short segments
    filtered = [s for s in segments if (s['end'] - s['start']) >= min_duration_ms / 1000]

    if not filtered:
        return []

    # Merge close segments
    merged = [filtered[0]]
    for current in filtered[1:]:
        gap = current['start'] - merged[-1]['end']
        if gap < merge_gap_ms / 1000:
            merged[-1]['end'] = current['end']
        else:
            merged.append(current)

    return merged
```

## Complete Screencast Processing Pipeline

```python
def process_screencast_audio(video_path, threshold=0.75):
    """Optimized pipeline for screencast speech detection."""

    # 1. Extract audio
    audio = extract_audio_from_video(video_path)

    # 2. Optional: Apply high-pass filter
    audio_filtered = apply_highpass(audio, cutoff_hz=80)

    # 3. Load VAD model
    torch.set_num_threads(1)
    model = load_silero_vad()

    # 4. Detect speech with tuned parameters
    speech_timestamps = get_speech_timestamps(
        audio_filtered,
        model,
        threshold=threshold,
        sampling_rate=16000,
        min_speech_duration_ms=200,
        min_silence_duration_ms=100,
        speech_pad_ms=50,
        return_seconds=True
    )

    # 5. Post-process for clean segments
    clean_segments = postprocess_segments(speech_timestamps)

    return [(s['start'], s['end']) for s in clean_segments]
```

## Two-Pass Detection (Advanced)

For maximum accuracy on difficult audio:

1. **Pass 1**: Permissive threshold (0.3-0.4) to catch all speech
2. **Pass 2**: Require temporal consistency (multiple consecutive high-prob frames)

This rejects isolated keyboard transients while preserving sustained speech.

## Sources

- Picovoice VAD Guide: https://picovoice.ai/blog/complete-guide-voice-activity-detection-vad/
- RNNoise: https://jmvalin.ca/demo/rnnoise/
- DeepFilterNet: https://github.com/Rikorose/DeepFilterNet
