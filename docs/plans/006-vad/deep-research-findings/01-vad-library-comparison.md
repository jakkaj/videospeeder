# VAD Library Comparison for Python Video Processing (2024-2025)

## Research Summary

This research compares Voice Activity Detection libraries for Python video processing, specifically for distinguishing human speech from keyboard typing and background noise.

## Key Findings

### Recommendation: Silero VAD

**Silero VAD emerges as the optimal choice** for the VideoSpeeder application, offering:
- 87.7% True Positive Rate at 5% False Positive Rate
- Processing speed: 0.004 RTF (14.4 seconds per hour of audio)
- MIT License (no commercial restrictions)
- 2 MB model size
- Supports 8kHz and 16kHz audio

### Comparison Table

| Metric | Silero VAD | WebRTC VAD | pyannote-audio | SpeechBrain | Cobra VAD |
|--------|------------|------------|----------------|-------------|-----------|
| **Accuracy (TPR @ 5% FPR)** | 87.7% | 50.0% | ~85% | ~82% | 98.9% |
| **Real-Time Factor** | 0.004 | 0.0003 | 0.037-0.15 | 0.08-0.2 | 0.0005 |
| **Model Size** | 2 MB | <1 MB | 50-200 MB | 20-100 MB | 1 MB |
| **License** | MIT | BSD | MIT | Apache 2.0 | Commercial |
| **Sample Rate** | 8kHz, 16kHz | 8-48kHz | Flexible | Flexible | 16kHz |

### Why NOT WebRTC VAD

Despite being fast, WebRTC VAD:
- Achieves only 50% TPR (misses half of all speech frames)
- Has documented false positive problems with keyboard typing
- Was designed for low-latency real-time communication, not batch processing

### Silero VAD Installation

```bash
# Install dependencies
pip install torch>=1.12.0 torchaudio>=0.12.0
pip install silero-vad

# Optional: ONNX runtime for faster inference
pip install onnxruntime>=1.16.1
```

### Basic Usage

```python
import torch
from silero_vad import load_silero_vad, read_audio, get_speech_timestamps

torch.set_num_threads(1)
model = load_silero_vad()

wav = read_audio('video_audio.wav')
speech_timestamps = get_speech_timestamps(
    wav,
    model,
    return_seconds=True
)

for segment in speech_timestamps:
    print(f"Speech: {segment['start']:.2f}s to {segment['end']:.2f}s")
```

### Key Parameters

- `threshold`: Speech probability threshold (default 0.5, use 0.7-0.8 for noisy audio)
- `min_speech_duration_ms`: Minimum speech segment (default 250ms)
- `min_silence_duration_ms`: Required silence to end segment (default 100ms)
- `speech_pad_ms`: Padding at segment boundaries (default 30ms)

## Cobra VAD Alternative

For maximum accuracy (98.9% TPR), consider Cobra VAD from Picovoice:
- 8.6x faster than Silero
- Commercial license required
- Best for professional video production

## Sources

- Silero VAD GitHub: https://github.com/snakers4/silero-vad
- Picovoice VAD Benchmark: https://picovoice.ai/blog/best-voice-activity-detection-vad-2025/
- PyPI: https://pypi.org/project/silero-vad/
