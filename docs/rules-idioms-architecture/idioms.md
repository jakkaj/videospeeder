# VideoSpeeder Development Idioms

This document captures recurring patterns, conventions, and practical examples for VideoSpeeder development. While [Rules](rules.md) are enforceable, idioms are recommended patterns that embody project wisdom.

See also:
- [Constitution](../rules/constitution.md) - Guiding principles
- [Rules](rules.md) - Enforceable standards
- [Architecture](architecture.md) - System structure

---

## CLI Argument Patterns

### Standard Argument Structure

```python
import argparse

def parse_args():
    """Parse command-line arguments with consistent style."""
    parser = argparse.ArgumentParser(
        description="VideoSpeeder: Intelligently speed up silent portions of videos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -i input.mp4 -o output.mp4
  %(prog)s -i input.mp4 -o output.mp4 --threshold -35 --duration 3.0
  %(prog)s -i input.mp4 -o output.mp4 --gpu --indicator
        """
    )

    # Required arguments first
    parser.add_argument('-i', '--input', required=True,
                        help='Input video file path')
    parser.add_argument('-o', '--output', required=True,
                        help='Output video file path')

    # Optional parameters grouped logically
    parser.add_argument('-t', '--threshold', type=float, default=-30.0,
                        help='Silence detection threshold in dB (default: -30.0)')
    parser.add_argument('-d', '--duration', type=float, default=2.0,
                        help='Minimum silence duration in seconds (default: 2.0)')

    # Feature flags
    parser.add_argument('--indicator', action='store_true',
                        help='Show visual speed indicator overlay')
    parser.add_argument('--gpu', action='store_true',
                        help='Enable NVIDIA NVENC GPU encoding')

    return parser.parse_args()
```

**Pattern:**
1. Required arguments use `-short` and `--long` forms
2. Defaults in help text match code defaults
3. Include examples in epilog
4. Group related options together
5. Use action='store_true' for boolean flags

---

## FFmpeg Integration Patterns

### Subprocess Execution with Progress

```python
import subprocess
import sys
from tqdm import tqdm

def run_ffmpeg_with_progress(command: List[str], total_duration: float):
    """Execute FFmpeg command with real-time progress bar.

    Args:
        command: FFmpeg command as list of arguments
        total_duration: Expected video duration in seconds for progress calculation
    """
    # Add progress output
    command.extend(['-progress', 'pipe:1', '-nostats'])

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        bufsize=1
    )

    with tqdm(total=total_duration, unit='s', desc='Processing') as pbar:
        last_time = 0.0

        for line in process.stdout:
            if line.startswith('out_time_ms='):
                try:
                    time_ms = int(line.split('=')[1])
                    current_time = time_ms / 1_000_000.0
                    delta = current_time - last_time
                    if delta > 0:
                        pbar.update(delta)
                        last_time = current_time
                except ValueError:
                    pass

    stderr = process.stderr.read()
    returncode = process.wait()

    if returncode != 0:
        print(f"FFmpeg failed with exit code {returncode}", file=sys.stderr)
        print(stderr, file=sys.stderr)
        sys.exit(1)
```

**Pattern:**
- Use `-progress pipe:1` for parseable output
- Parse `out_time_ms=` for progress tracking
- Capture stderr for error reporting
- Provide visual feedback with tqdm
- Exit with non-zero on failure

### Filter Graph Construction

```python
def build_speed_filter(segment_start: float, segment_end: float, speed_factor: float) -> str:
    """Build filter graph for single speed-adjusted segment.

    Args:
        segment_start: Segment start time in seconds
        segment_end: Segment end time in seconds
        speed_factor: Speed multiplier (e.g., 4.0 for 4x speed)

    Returns:
        FFmpeg filter string for this segment
    """
    duration = segment_end - segment_start

    # Video speed adjustment
    video_pts = f"setpts={1.0/speed_factor:.6f}*PTS"

    # Audio speed adjustment (chain atempo filters for >2x)
    audio_filters = []
    remaining_speed = speed_factor
    while remaining_speed > 2.0:
        audio_filters.append("atempo=2.0")
        remaining_speed /= 2.0
    if remaining_speed > 1.0:
        audio_filters.append(f"atempo={remaining_speed:.6f}")

    audio_chain = ",".join(audio_filters) if audio_filters else "anull"

    # Combine into segment filter
    filter_complex = f"[0:v]trim={segment_start}:{segment_end},setpts=PTS-STARTPTS,{video_pts}[v{idx}];"
    filter_complex += f"[0:a]atrim={segment_start}:{segment_end},asetpts=PTS-STARTPTS,{audio_chain}[a{idx}]"

    return filter_complex
```

**Pattern:**
- Split video and audio processing
- Chain multiple atempo filters for >2x speed (FFmpeg limitation)
- Reset PTS with setpts=PTS-STARTPTS after trim
- Use descriptive stream labels ([v0], [a0])

---

## Error Handling Patterns

### Dependency Validation

```python
import shutil
import sys

def validate_environment():
    """Validate required dependencies before processing."""
    errors = []

    # Check FFmpeg tools
    if not shutil.which("ffmpeg"):
        errors.append("FFmpeg not found in PATH")
    if not shutil.which("ffprobe"):
        errors.append("FFprobe not found in PATH")

    # Verify FFmpeg capabilities (if needed)
    try:
        result = subprocess.run(
            ['ffmpeg', '-encoders'],
            capture_output=True,
            text=True,
            check=True
        )
        if 'h264_nvenc' not in result.stdout:
            print("Warning: NVENC hardware encoding not available", file=sys.stderr)
    except subprocess.CalledProcessError:
        errors.append("Unable to query FFmpeg encoders")

    if errors:
        print("Environment validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        print("\nInstall FFmpeg: https://ffmpeg.org/download.html", file=sys.stderr)
        sys.exit(1)
```

**Pattern:**
- Check all dependencies at startup (fail-fast)
- Collect all errors before exiting
- Provide actionable error messages with links
- Distinguish errors (missing tools) from warnings (missing features)

### Input Validation

```python
def validate_inputs(input_path: str, output_path: str, threshold: float, duration: float):
    """Validate user inputs before processing."""
    import os

    if not os.path.isfile(input_path):
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if os.path.exists(output_path):
        response = input(f"Warning: {output_path} exists. Overwrite? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled by user")
            sys.exit(0)

    if threshold > 0:
        print(f"Warning: Positive threshold ({threshold} dB) may not detect silence", file=sys.stderr)

    if duration < 0.1:
        print(f"Error: Duration too short ({duration}s). Must be >= 0.1s", file=sys.stderr)
        sys.exit(1)

    if duration > 60:
        print(f"Warning: Large duration ({duration}s) may miss shorter pauses", file=sys.stderr)
```

**Pattern:**
- Validate file existence before expensive operations
- Prompt for confirmation on destructive actions
- Warn for unusual-but-valid parameters
- Error for invalid parameters
- Provide context in error messages

---

## Output Formatting Patterns

### Rich Console Tables

```python
from rich.console import Console
from rich.table import Table

def print_video_stats(stats: dict):
    """Display video statistics in formatted table."""
    console = Console()

    table = Table(title="Video Statistics", show_header=True)
    table.add_column("Property", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")

    table.add_row("Duration", f"{stats['duration']:.2f} seconds")
    table.add_row("Resolution", f"{stats['width']}x{stats['height']}")
    table.add_row("Codec", stats['codec'])
    table.add_row("FPS", f"{stats['fps']:.2f}")
    table.add_row("Bitrate", f"{stats['bitrate'] / 1_000_000:.2f} Mbps")

    console.print(table)
```

**Pattern:**
- Use rich for formatted terminal output
- Tables for structured data
- Consistent color scheme (cyan for labels, magenta for values)
- Include units in output
- Round floats appropriately for readability

### Progress Reporting

```python
from tqdm import tqdm

def process_segments(segments: List[Segment], total_duration: float):
    """Process segments with progress tracking."""
    with tqdm(total=len(segments), unit='segment', desc='Processing segments') as pbar:
        for segment in segments:
            process_segment(segment)
            pbar.update(1)
            pbar.set_postfix({
                'type': segment.type,
                'speed': f'{segment.speed}x' if segment.type == 'silent' else '1x'
            })
```

**Pattern:**
- Use tqdm for long-running operations
- Show meaningful units (segments, seconds, frames)
- Update postfix with current context
- Nest progress bars for multi-stage processes

---

## Testing Patterns

### Test Doc Examples

#### Unit Test (Isolated Logic)

```python
def test_given_10sec_silence_when_calculating_speed_then_returns_4x():
    """
    Test Doc:
    - Why: Fixed speed for silences ≤10s is core business rule from speed calculation spec
    - Contract: calculate_speed(duration) returns 4.0 when duration ≤ 10.0 seconds
    - Usage Notes: Pass duration in seconds; returns float multiplier
    - Quality Contribution: Documents the 10-second threshold rule; catches boundary condition bugs
    - Worked Example: 5.0s → 4.0x, 10.0s → 4.0x, 10.1s → variable speed
    """
    # Arrange
    durations = [1.0, 5.0, 10.0]  # All at or below threshold

    # Act & Assert
    for duration in durations:
        speed = calculate_speed(duration)
        assert speed == 4.0, f"Expected 4.0x for {duration}s, got {speed}x"
```

#### Integration Test (Multi-Component)

```python
def test_given_real_video_when_detecting_silence_then_finds_expected_intervals():
    """
    Test Doc:
    - Why: End-to-end validation that silence detection works with real FFmpeg output
    - Contract: run_silencedetect() returns list of (start, end) tuples matching actual silence
    - Usage Notes: Requires FFmpeg installed; uses fixture video with known silence at 5.0-10.0s
    - Quality Contribution: Validates FFmpeg integration; documents expected output format
    - Worked Example: test_silence.mp4 (10s, silence at 5.0-10.0s) → [(5.0, 10.0)]
    """
    # Arrange
    fixture_path = "tests/fixtures/test_silence.mp4"  # Known silence at 5.0-10.0s
    threshold = -30.0
    duration = 2.0

    # Act
    intervals = run_silencedetect(fixture_path, threshold, duration)

    # Assert
    assert len(intervals) == 1, f"Expected 1 interval, found {len(intervals)}"
    start, end = intervals[0]
    assert abs(start - 5.0) < 0.1, f"Start time {start} not close to 5.0"
    assert abs(end - 10.0) < 0.1, f"End time {end} not close to 10.0"
```

#### Scratch Test (Exploration)

```python
# tests/scratch/explore_atempo_chaining.py
def test_atempo_chain_experiments():
    """Quick exploration of FFmpeg atempo filter chaining.

    This is a scratch test to understand atempo behavior:
    - Can we chain multiple atempo filters?
    - What's the max multiplier per filter?
    - Does order matter?

    Findings:
    - atempo limited to 0.5-2.0 range per filter
    - Can chain: atempo=2.0,atempo=2.0 for 4x total
    - Order doesn't matter for multiplication

    TODO: Promote to unit test if atempo logic moves to separate function
    """
    # Experimental code here...
    pass
```

**Pattern:**
- Unit tests: Isolated, fast, test single function
- Integration tests: Multi-component, may use real dependencies
- Scratch tests: Temporary exploration, document findings in docstring

### Fixture Organization

```
tests/fixtures/
├── videos/
│   ├── test_silence_5s.mp4         # Short clip with known silence
│   ├── test_no_silence.mp4         # Continuous speech
│   └── test_all_silence.mp4        # Silent video
├── ffmpeg_outputs/
│   ├── silencedetect_sample.txt    # Sample FFmpeg silencedetect output
│   └── ffprobe_sample.json         # Sample ffprobe JSON output
└── expected_outputs/
    └── segments_expected.json      # Expected segment calculations
```

**Pattern:**
- Group fixtures by type (videos, outputs, expected results)
- Use descriptive, scenario-based names
- Keep fixtures small (< 1MB for videos)
- Document what each fixture represents
- Include realistic samples, not synthetic data

---

## Complexity Calibration Examples

These examples illustrate how to score the Complexity Score (CS) factors.

### Example 1: CS-1 (Trivial) - Update Help Text

**Task:** Fix typo in `--threshold` argument help text

**Scoring:**
- **S (Surface):** 0 - One file (videospeeder.py)
- **I (Integration):** 0 - No external dependencies
- **D (Data/State):** 0 - No data changes
- **N (Novelty):** 0 - Well-specified (clear typo fix)
- **F (NFR):** 0 - No performance/security concerns
- **T (Testing):** 0 - Visual verification only

**Total:** P = 0 → **CS-1 (Trivial)**

**Breakdown:**
```json
{
  "complexity": {
    "score": "CS-1",
    "label": "trivial",
    "breakdown": {"S": 0, "I": 0, "D": 0, "N": 0, "F": 0, "T": 0},
    "confidence": 1.0
  },
  "assumptions": ["No behavior change, text only"],
  "dependencies": [],
  "risks": [],
  "phases": ["Edit help text"]
}
```

### Example 2: CS-2 (Small) - Add Debug Logging

**Task:** Add optional `--verbose` flag with debug output for silence detection

**Scoring:**
- **S (Surface):** 1 - Two files (main script, possibly utils)
- **I (Integration):** 0 - Internal only
- **D (Data/State):** 0 - No data changes
- **N (Novelty):** 0 - Well-understood logging pattern
- **F (NFR):** 0 - Standard logging, no strict constraints
- **T (Testing):** 1 - Manual testing, verify log output

**Total:** P = 2 → **CS-2 (Small)**

**Breakdown:**
```json
{
  "complexity": {
    "score": "CS-2",
    "label": "small",
    "breakdown": {"S": 1, "I": 0, "D": 0, "N": 0, "F": 0, "T": 1},
    "confidence": 0.9
  },
  "assumptions": ["Logging library (Python logging) is standard"],
  "dependencies": [],
  "risks": ["Log verbosity may impact performance slightly"],
  "phases": ["Add CLI flag", "Add log statements", "Test output"]
}
```

### Example 3: CS-3 (Medium) - Add Configuration File Support

**Task:** Allow users to save/load settings from JSON config file

**Scoring:**
- **S (Surface):** 1 - Multiple files (main script, new config module)
- **I (Integration):** 1 - JSON library (stdlib, stable)
- **D (Data/State):** 1 - Config file format is new data structure
- **N (Novelty):** 1 - Some design decisions (config location, precedence)
- **F (NFR):** 0 - Standard file I/O
- **T (Testing):** 1 - Integration tests for config loading

**Total:** P = 5 → **CS-3 (Medium)**

**Breakdown:**
```json
{
  "complexity": {
    "score": "CS-3",
    "label": "medium",
    "breakdown": {"S": 1, "I": 1, "D": 1, "N": 1, "F": 0, "T": 1},
    "confidence": 0.8
  },
  "assumptions": ["JSON format is sufficient", "No migration from existing configs"],
  "dependencies": [],
  "risks": ["Config precedence (CLI vs file) needs clear rules"],
  "phases": ["Design config schema", "Implement loading/saving", "Update CLI parsing", "Test scenarios"]
}
```

### Example 4: CS-4 (Large) - Add Cloud Processing Backend

**Task:** Add option to offload video processing to cloud service (AWS MediaConvert)

**Scoring:**
- **S (Surface):** 2 - Many files (new cloud module, modified main script, config)
- **I (Integration):** 2 - AWS SDK (new external dependency, API may change)
- **D (Data/State):** 1 - Configuration for AWS credentials and settings
- **N (Novelty):** 2 - Significant discovery (pricing, API limits, error handling)
- **F (NFR):** 1 - Cost optimization, security (credential management)
- **T (Testing):** 2 - Mock AWS calls, integration tests, cost testing

**Total:** P = 10 → **CS-4 (Large)**

**Breakdown:**
```json
{
  "complexity": {
    "score": "CS-4",
    "label": "large",
    "breakdown": {"S": 2, "I": 2, "D": 1, "N": 2, "F": 1, "T": 2},
    "confidence": 0.6
  },
  "assumptions": ["AWS MediaConvert API suits our needs", "Users have AWS accounts"],
  "dependencies": ["boto3 (AWS SDK)", "AWS MediaConvert service"],
  "risks": ["Cost overruns if not managed", "API rate limits", "Credential security"],
  "phases": [
    "Research AWS MediaConvert capabilities",
    "Design cloud/local abstraction",
    "Implement AWS integration with feature flag",
    "Add cost estimation and limits",
    "Comprehensive testing (local + cloud)",
    "Gradual rollout with flag"
  ]
}
```

**Note:** CS-4 requires staged rollout and feature flags.

### Example 5: CS-5 (Epic) - Rewrite as Web Service with Queue

**Task:** Transform VideoSpeeder from CLI tool to web service with job queue, API, and web UI

**Scoring:**
- **S (Surface):** 2 - Entire architecture changes (new web server, API layer, frontend, worker processes)
- **I (Integration):** 2 - Multiple new dependencies (web framework, message queue, database)
- **D (Data/State):** 2 - Database schema for jobs, user data, processing state
- **N (Novelty):** 2 - Major architectural shift, many unknowns (scaling, queuing, auth)
- **F (NFR):** 2 - Performance at scale, security (auth, file uploads), compliance
- **T (Testing):** 2 - Unit, integration, e2e, load testing, staged rollout

**Total:** P = 12 → **CS-5 (Epic)**

**Breakdown:**
```json
{
  "complexity": {
    "score": "CS-5",
    "label": "epic",
    "breakdown": {"S": 2, "I": 2, "D": 2, "N": 2, "F": 2, "T": 2},
    "confidence": 0.4
  },
  "assumptions": ["Need to support concurrent users", "Cloud hosting acceptable"],
  "dependencies": [
    "Web framework (Flask/Django)",
    "Message queue (Redis/RabbitMQ)",
    "Database (PostgreSQL)",
    "Object storage (S3)",
    "Frontend framework (React)"
  ],
  "risks": [
    "Massive scope increase",
    "Infrastructure costs",
    "Security vulnerabilities",
    "Scaling challenges",
    "Multi-month timeline"
  ],
  "phases": [
    "Architecture design and ADR",
    "Database schema design",
    "API design and spec",
    "Backend implementation (flagged by endpoint)",
    "Worker queue implementation",
    "Frontend implementation (flagged by feature)",
    "Integration testing",
    "Security audit",
    "Load testing",
    "Staged rollout (alpha → beta → GA)",
    "Monitoring and rollback plan"
  ]
}
```

**Note:** CS-5 requires comprehensive planning, feature flags, staged rollout, and rollback strategy.

---

## Common Workflows

### Adding a New CLI Parameter

1. Add argument to `parse_args()` with default value
2. Document parameter in help text and README
3. Pass parameter through function calls
4. Update affected functions to use parameter
5. Test with various parameter values
6. Add example usage to README

### Adding a New FFmpeg Filter

1. Research FFmpeg filter documentation
2. Prototype filter string manually with FFmpeg CLI
3. Create helper function to generate filter string
4. Write tests with expected filter output
5. Integrate into main filter graph construction
6. Test with real video samples
7. Document filter purpose and parameters

### Investigating FFmpeg Issues

1. Run FFmpeg command manually with `-v debug`
2. Examine full stderr output for warnings/errors
3. Simplify command to minimal reproducible case
4. Test with different input files
5. Check FFmpeg version and capabilities
6. Search FFmpeg documentation and mailing lists
7. Document findings and workarounds

---

*These idioms represent accumulated project wisdom. Adapt patterns to specific needs, but maintain consistency with project conventions.*
