# Converting VAD Frame-Level Output to Timestamp Intervals

## Silero VAD Output Format

`get_speech_timestamps()` returns a list of dictionaries:

```python
[
    {'start': 0.5, 'end': 5.2},
    {'start': 7.8, 'end': 12.1},
    {'start': 14.5, 'end': 19.3}
]
```

When `return_seconds=True`, values are in seconds. Otherwise, they're sample indices.

## Converting Sample Indices to Seconds

```python
# Frame duration at 16kHz: 32ms (512 samples per frame)
frame_duration_sec = 512 / 16000  # = 0.032 seconds

# Convert frame index to seconds
seconds = frame_index * frame_duration_sec
```

## Hysteresis Thresholding (Jitter Reduction)

Prevents rapid on/off switching near threshold:

```python
def apply_hysteresis_threshold(
    probabilities: np.ndarray,
    on_threshold: float = 0.6,
    off_threshold: float = 0.4
) -> np.ndarray:
    """
    Apply hysteresis: requires strong signal to switch states.
    on_threshold > off_threshold (e.g., 0.6 vs 0.4)
    """
    binary = np.zeros(len(probabilities), dtype=np.uint8)
    state = 0  # Start in non-speech

    for i in range(len(probabilities)):
        if state == 0 and probabilities[i] >= on_threshold:
            state = 1
        elif state == 1 and probabilities[i] < off_threshold:
            state = 0
        binary[i] = state

    return binary
```

## Frame-to-Segment Conversion

```python
from typing import List, Tuple

def frames_to_segments(
    binary_frames: np.ndarray,
    frame_duration_sec: float
) -> List[Tuple[float, float]]:
    """Convert binary frame labels to (start, end) tuples."""

    diffs = np.diff(binary_frames)
    transitions = np.where(diffs != 0)[0] + 1

    # Handle boundaries
    if binary_frames[0] == 1:
        transitions = np.concatenate(([0], transitions))
    if binary_frames[-1] == 1:
        transitions = np.concatenate((transitions, [len(binary_frames)]))

    # Pair transitions into segments
    segments = []
    for i in range(0, len(transitions), 2):
        if i + 1 < len(transitions):
            start = transitions[i] * frame_duration_sec
            end = transitions[i + 1] * frame_duration_sec
            segments.append((start, end))

    return segments
```

## Merging Short Gaps

Natural speech has brief pauses (200-500ms). Merge segments separated by short gaps:

```python
def merge_short_gaps(
    segments: List[Tuple[float, float]],
    max_gap_sec: float = 0.3
) -> List[Tuple[float, float]]:
    """Merge segments separated by gaps shorter than max_gap_sec."""

    if not segments:
        return segments

    merged = [segments[0]]

    for current_start, current_end in segments[1:]:
        last_start, last_end = merged[-1]
        gap = current_start - last_end

        if gap <= max_gap_sec:
            merged[-1] = (last_start, current_end)  # Extend last segment
        else:
            merged.append((current_start, current_end))

    return merged
```

**Recommended gap thresholds**:
- Contact center: 0.2-0.4 seconds
- Conversational: 0.3-0.5 seconds
- Medical dictation: 0.5-1.0 seconds

## Filtering Short Segments

Remove spurious detections (coughs, clicks):

```python
def filter_short_segments(
    segments: List[Tuple[float, float]],
    min_duration_sec: float = 0.25
) -> List[Tuple[float, float]]:
    """Remove segments shorter than minimum duration."""
    return [
        (start, end) for start, end in segments
        if (end - start) >= min_duration_sec
    ]
```

**Recommended minimum durations**:
- Contact center: 0.1-0.25 seconds (capture "yes", "no")
- General: 0.25-0.5 seconds
- IVR systems: 0.5-1.0 seconds

## Adding Padding to Segments

Prevent clipping word beginnings/endings:

```python
def pad_segments(
    segments: List[Tuple[float, float]],
    pad_sec: float = 0.1,
    max_duration: float = None
) -> List[Tuple[float, float]]:
    """Add padding to segment boundaries."""

    padded = []
    for start, end in segments:
        new_start = max(0, start - pad_sec)
        new_end = end + pad_sec

        if max_duration is not None:
            new_end = min(new_end, max_duration)

        padded.append((new_start, new_end))

    return padded
```

After padding, merge any overlapping segments:

```python
def merge_overlapping(segments: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Merge overlapping segments after padding."""
    if not segments:
        return segments

    sorted_segs = sorted(segments)
    merged = [sorted_segs[0]]

    for start, end in sorted_segs[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    return merged
```

## Converting Speech to Silence Intervals

For VideoSpeeder, we need SILENCE intervals (to speed up):

```python
def speech_to_silence(
    speech_segments: List[Tuple[float, float]],
    total_duration: float
) -> List[Tuple[float, float]]:
    """Convert speech intervals to silence intervals."""

    if not speech_segments:
        return [(0.0, total_duration)]  # All silence

    sorted_segs = sorted(speech_segments)
    silence = []

    # Silence before first speech
    if sorted_segs[0][0] > 0:
        silence.append((0, sorted_segs[0][0]))

    # Silence between speech segments
    for i in range(len(sorted_segs) - 1):
        gap_start = sorted_segs[i][1]
        gap_end = sorted_segs[i + 1][0]
        if gap_end > gap_start:
            silence.append((gap_start, gap_end))

    # Silence after last speech
    if sorted_segs[-1][1] < total_duration:
        silence.append((sorted_segs[-1][1], total_duration))

    return silence
```

## Complete Production Pipeline

```python
def process_vad_output(
    speech_timestamps: List[dict],
    audio_duration: float,
    sample_rate: int = 16000,
    min_speech_duration: float = 0.25,
    min_silence_duration: float = 0.3,
    merge_gap_sec: float = 0.3,
    padding_sec: float = 0.1
) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
    """
    Process raw Silero VAD output into clean speech and silence intervals.

    Returns:
        (speech_segments, silence_segments)
    """

    # Convert timestamps to tuples
    segments = []
    for ts in speech_timestamps:
        start = ts.get('start', 0)
        end = ts.get('end', 0)

        # If values are in samples, convert to seconds
        if start > 1000 or end > 1000:
            start = start / sample_rate
            end = end / sample_rate

        if 0 <= start < end <= audio_duration:
            segments.append((start, end))

    if not segments:
        return [], [(0.0, audio_duration)]

    # 1. Merge short gaps
    segments = merge_short_gaps(segments, max_gap_sec=merge_gap_sec)

    # 2. Filter short segments
    segments = filter_short_segments(segments, min_duration_sec=min_speech_duration)

    # 3. Add padding
    segments = pad_segments(segments, pad_sec=padding_sec, max_duration=audio_duration)

    # 4. Merge overlapping (from padding)
    segments = merge_overlapping(segments)

    # 5. Compute silence intervals
    silence = speech_to_silence(segments, audio_duration)

    # 6. Filter short silences
    silence = [(s, e) for s, e in silence if (e - s) >= min_silence_duration]

    return segments, silence
```

## Edge Cases

| Case | Handling |
|------|----------|
| Empty audio | Return empty speech, full silence |
| All speech | Return full segment, empty silence |
| All silence | Return empty speech, full duration as silence |
| Very short audio (<1s) | Process normally, may have no valid segments |
| Overlapping after padding | Merge into single segment |

## Performance

- Frame-level operations: O(n) where n = number of frames
- Segment operations: O(m log m) where m = number of segments
- Processing 1-hour video: <100ms for all post-processing

## Sources

- Silero VAD Utils: https://github.com/snakers4/silero-vad/blob/master/src/silero_vad/utils_vad.py
- SpeechBrain VAD Tutorial: https://speechbrain.readthedocs.io/en/latest/tutorials/tasks/voice-activity-detection.html
