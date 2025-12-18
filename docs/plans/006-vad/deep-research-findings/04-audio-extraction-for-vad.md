# Audio Extraction from Video for VAD Processing

## Required Audio Format

For Silero VAD:
- **Sample Rate**: 16000 Hz (or 8000 Hz)
- **Channels**: Mono (1 channel)
- **Bit Depth**: 16-bit signed PCM or 32-bit float
- **Normalization**: Float samples in range [-1.0, 1.0]

## FFmpeg Commands

### Basic Extraction to WAV File

```bash
ffmpeg -i input_video.mp4 \
  -vn \                      # No video
  -acodec pcm_s16le \        # 16-bit PCM
  -ar 16000 \                # 16kHz sample rate
  -ac 1 \                    # Mono
  output_audio.wav
```

### Extraction with Time Offset

```bash
ffmpeg -ss 60.0 \            # Start at 60 seconds
  -i input_video.mp4 \
  -t 300.0 \                 # Extract 5 minutes
  -vn -acodec pcm_s16le -ar 16000 -ac 1 \
  output_segment.wav
```

### Select Specific Audio Track

```bash
ffmpeg -i input_video.mp4 \
  -map 0:a:0 \               # First audio stream (0-indexed)
  -vn -acodec pcm_s16le -ar 16000 -ac 1 \
  output_audio.wav
```

## Python Subprocess Integration

### Piping Audio Directly (No Temp Files)

```python
import subprocess
import numpy as np
import torch

def extract_audio_to_numpy(video_path: str, sample_rate: int = 16000) -> np.ndarray:
    """Extract audio from video file and return as numpy array."""
    command = [
        'ffmpeg',
        '-i', video_path,
        '-vn',                      # No video
        '-acodec', 'pcm_s16le',     # 16-bit PCM
        '-ar', str(sample_rate),    # Target sample rate
        '-ac', '1',                 # Mono
        '-f', 's16le',              # Raw output format
        '-loglevel', 'error',       # Suppress info messages
        'pipe:1'                    # Output to stdout
    ]

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=10**6  # 1MB buffer
    )

    # Read all audio data
    audio_bytes, stderr = process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {stderr.decode()}")

    # Convert bytes to int16 array
    audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)

    # Normalize to float32 [-1, 1]
    audio_float32 = audio_int16.astype(np.float32) / 32768.0

    return audio_float32
```

### Streaming Extraction for Long Videos

```python
from typing import Generator

def stream_audio_chunks(video_path: str, chunk_seconds: float = 30.0,
                        sample_rate: int = 16000) -> Generator[np.ndarray, None, None]:
    """Stream audio chunks from video without loading entire file."""

    chunk_samples = int(chunk_seconds * sample_rate)
    bytes_per_chunk = chunk_samples * 2  # 2 bytes per int16

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
        bufsize=bytes_per_chunk * 2
    )

    try:
        while True:
            data = process.stdout.read(bytes_per_chunk)
            if not data:
                break

            audio_int16 = np.frombuffer(data, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            yield audio_float32
    finally:
        process.stdout.close()
        process.wait()
```

### Extraction with Offset and Duration

```python
def extract_audio_segment(video_path: str, start_seconds: float = 0.0,
                         duration_seconds: float = None,
                         sample_rate: int = 16000) -> np.ndarray:
    """Extract specific segment from video."""

    command = ['ffmpeg']

    if start_seconds > 0:
        command.extend(['-ss', str(start_seconds)])

    command.extend(['-i', video_path])

    if duration_seconds is not None:
        command.extend(['-t', str(duration_seconds)])

    command.extend([
        '-vn', '-acodec', 'pcm_s16le',
        '-ar', str(sample_rate), '-ac', '1',
        '-f', 's16le', '-loglevel', 'error',
        'pipe:1'
    ])

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    audio_bytes, stderr = process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {stderr.decode()}")

    audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
    return audio_int16.astype(np.float32) / 32768.0
```

## Memory Considerations

| Video Duration | Audio Size (16kHz mono) |
|----------------|-------------------------|
| 1 minute | 1.92 MB |
| 30 minutes | 57.6 MB |
| 1 hour | 115 MB |
| 2 hours | 230 MB |

For videos > 30 minutes, use streaming extraction.

## Error Handling

```python
import shutil

def extract_audio_safely(video_path: str, sample_rate: int = 16000) -> np.ndarray:
    """Extract audio with comprehensive error handling."""

    # Check FFmpeg availability
    if shutil.which('ffmpeg') is None:
        raise RuntimeError("FFmpeg not found in PATH")

    # Check file exists
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    try:
        command = [
            'ffmpeg', '-i', video_path, '-vn',
            '-acodec', 'pcm_s16le', '-ar', str(sample_rate),
            '-ac', '1', '-f', 's16le', '-loglevel', 'error',
            'pipe:1'
        ]

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=10**8
        )

        audio_bytes, stderr = process.communicate(timeout=300)

        if process.returncode != 0:
            error_msg = stderr.decode('utf-8', errors='ignore')
            raise RuntimeError(f"FFmpeg error: {error_msg}")

        if len(audio_bytes) == 0:
            raise ValueError("No audio data extracted (video may have no audio track)")

        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)

        if len(audio_int16) < sample_rate:  # Less than 1 second
            raise ValueError("Extracted audio too short (< 1 second)")

        return audio_int16.astype(np.float32) / 32768.0

    except subprocess.TimeoutExpired:
        process.kill()
        raise RuntimeError("FFmpeg extraction timeout (300s)")
```

## Resampling Quality

FFmpeg uses swr (SoX Resampler successor) by default. For highest quality:

```bash
# Use soxr resampler with high precision
ffmpeg -i input.mp4 \
  -af "aresample=resampler=soxr:precision=20" \
  -ar 16000 -ac 1 output.wav
```

For VAD, default resampling quality is sufficient.

## Platform Notes

- **macOS**: `brew install ffmpeg`
- **Ubuntu**: `apt-get install ffmpeg`
- **Windows**: Download from ffmpeg.org, add to PATH

## Sources

- FFmpeg Documentation: https://ffmpeg.org/ffmpeg.html
- FFmpeg Resampler: https://ffmpeg.org/ffmpeg-resampler.html
