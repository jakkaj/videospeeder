# Silero VAD Complete Implementation Guide

## Audio Requirements

- **Sample Rate**: 8kHz or 16kHz (16kHz recommended)
- **Channels**: Mono only
- **Format**: 16-bit PCM or 32-bit float, normalized to [-1.0, 1.0]
- **Frame Size**: 512 samples for 16kHz (32ms), 256 samples for 8kHz

## Installation

```bash
pip install silero-vad torch>=1.12.0 torchaudio>=0.12.0

# FFmpeg backend for audio I/O
# macOS: brew install ffmpeg
# Ubuntu: apt-get install ffmpeg
```

## FFmpeg Audio Extraction Command

```bash
ffmpeg -i input_video.mp4 \
  -vn \
  -acodec pcm_s16le \
  -ar 16000 \
  -ac 1 \
  output_audio.wav
```

## Complete Implementation

```python
import subprocess
import numpy as np
import torch
from silero_vad import load_silero_vad, get_speech_timestamps
from typing import List, Tuple

def extract_audio_from_video(video_path: str, sample_rate: int = 16000) -> torch.Tensor:
    """Extract audio from video file using FFmpeg pipe."""
    command = [
        'ffmpeg',
        '-i', video_path,
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', str(sample_rate),
        '-ac', '1',
        '-f', 's16le',
        '-loglevel', 'error',
        'pipe:1'
    ]

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=10**8
    )

    audio_data, stderr = process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {stderr.decode()}")

    # Convert to float32 normalized [-1, 1]
    audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
    return torch.from_numpy(audio_np)


def detect_speech_segments(
    video_path: str,
    threshold: float = 0.5,
    min_speech_duration_ms: int = 250,
    min_silence_duration_ms: int = 100
) -> List[Tuple[float, float]]:
    """Detect speech segments in video using Silero VAD."""

    # Extract audio
    audio = extract_audio_from_video(video_path, sample_rate=16000)

    # Load model (single-threaded for best performance)
    torch.set_num_threads(1)
    model = load_silero_vad()

    # Get speech timestamps
    speech_timestamps = get_speech_timestamps(
        audio,
        model,
        threshold=threshold,
        sampling_rate=16000,
        min_speech_duration_ms=min_speech_duration_ms,
        min_silence_duration_ms=min_silence_duration_ms,
        return_seconds=True
    )

    # Convert to list of tuples
    return [(ts['start'], ts['end']) for ts in speech_timestamps]


# Usage
segments = detect_speech_segments("screencast.mp4", threshold=0.75)
for start, end in segments:
    print(f"Speech: {start:.2f}s - {end:.2f}s")
```

## Streaming Processing for Long Videos

For videos > 30 minutes, process in chunks to manage memory:

```python
class StreamingSpeechDetector:
    def __init__(self, sample_rate: int = 16000, chunk_seconds: float = 30.0):
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * chunk_seconds)
        torch.set_num_threads(1)
        self.model = load_silero_vad()

    def stream_audio_chunks(self, video_path: str):
        """Yield audio chunks from video."""
        command = [
            'ffmpeg', '-i', video_path, '-vn',
            '-acodec', 'pcm_s16le', '-ar', str(self.sample_rate),
            '-ac', '1', '-f', 's16le', '-loglevel', 'error', 'pipe:1'
        ]

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        bytes_per_chunk = self.chunk_size * 2  # 2 bytes per int16

        while True:
            data = process.stdout.read(bytes_per_chunk)
            if not data:
                break
            audio_np = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            yield torch.from_numpy(audio_np)

        process.wait()

    def detect_all(self, video_path: str, threshold: float = 0.5):
        """Process entire video with streaming."""
        all_segments = []
        time_offset = 0.0

        for chunk in self.stream_audio_chunks(video_path):
            timestamps = get_speech_timestamps(
                chunk, self.model, threshold=threshold,
                sampling_rate=self.sample_rate, return_seconds=True
            )

            for ts in timestamps:
                all_segments.append((
                    ts['start'] + time_offset,
                    ts['end'] + time_offset
                ))

            time_offset += len(chunk) / self.sample_rate

        return self._merge_segments(all_segments)

    def _merge_segments(self, segments):
        """Merge overlapping/adjacent segments."""
        if not segments:
            return []

        sorted_segs = sorted(segments, key=lambda x: x[0])
        merged = [sorted_segs[0]]

        for start, end in sorted_segs[1:]:
            if start <= merged[-1][1] + 0.1:  # 100ms tolerance
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        return merged
```

## Recommended Parameters for Screencasts

```python
# For screencast with keyboard sounds
speech_timestamps = get_speech_timestamps(
    audio,
    model,
    threshold=0.75,           # Higher threshold reduces keyboard false positives
    sampling_rate=16000,
    min_speech_duration_ms=200,  # Allow shorter utterances
    min_silence_duration_ms=100,  # Standard separation
    speech_pad_ms=50,            # Extra padding for transients
    return_seconds=True
)
```

## Performance

- Processing time: ~14.4 seconds per hour of audio on CPU
- Memory usage: ~100MB for model + audio
- Supports ONNX for 4-5x faster inference

## Thread Safety

Silero VAD is NOT thread-safe. Use separate model instances for parallel processing:

```python
from concurrent.futures import ThreadPoolExecutor

def process_video(video_path):
    model = load_silero_vad()  # New instance per thread
    audio = extract_audio_from_video(video_path)
    return get_speech_timestamps(audio, model, return_seconds=True)

with ThreadPoolExecutor(max_workers=4) as executor:
    results = executor.map(process_video, video_paths)
```

## Sources

- https://github.com/snakers4/silero-vad
- https://pypi.org/project/silero-vad/
- https://pytorch.org/hub/snakers4_silero-vad_vad/
