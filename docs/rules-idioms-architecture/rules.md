# VideoSpeeder Development Rules

This document contains enforceable rules and standards for the VideoSpeeder project. All contributions MUST follow these rules unless explicitly documented deviations exist in the project plan.

See also:
- [Constitution](../rules/constitution.md) - Guiding principles and governance
- [Idioms](idioms.md) - Patterns and examples
- [Architecture](architecture.md) - System structure and boundaries

---

## Source Control Hygiene

### Branching

**MUST:**
- Branch from `main` for all new work
- Use naming convention: `issue-<number>-phase-<phase>` when working with GitHub issues
- Use descriptive names when working without issues: `feat/<feature-name>`, `fix/<bug-name>`
- Keep branches short-lived (merge within days, not weeks)
- Delete branches after successful merge

**SHOULD:**
- Rebase on main regularly to minimize merge conflicts
- Keep one feature/fix per branch

**MUST NOT:**
- Commit directly to `main` (use pull requests)
- Push force to shared branches
- Include WIP commits in final PR (squash or rebase)

### Commits

**MUST:**
- Use Conventional Commits format:
  ```
  <type>(<scope>): <description>

  [optional body]

  [optional footer]
  ```
- Valid types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`, `perf`
- Write commit messages in imperative mood ("add feature" not "added feature")
- Keep subject line under 72 characters
- Reference issues in footer: `Fixes #123`, `Closes #456`, `Refs #789`

**Breaking Changes:**
- Add `!` after type: `feat!: change API signature`
- OR include `BREAKING CHANGE:` in footer with description

**Examples:**
```
feat(silence-detection): add configurable threshold parameter

Allow users to customize silence detection threshold via --threshold flag.
Default remains -30dB for backward compatibility.

Fixes #42

---

fix(gpu): handle missing NVENC gracefully

Falls back to CPU encoding when NVENC unavailable instead of crashing.

Fixes #58

---

docs: update README with GPU installation instructions

Added section covering CUDA toolkit and NVENC driver requirements
for GPU-accelerated encoding on Linux and Windows.
```

**MUST NOT:**
- Commit without testing the change
- Commit secrets, credentials, or API keys
- Include unrelated changes in same commit

### Pull Requests

**MUST:**
- Open PR against `main` branch
- Include clear description of changes and motivation
- Link related issues
- Ensure all CI checks pass (when CI configured)
- Address reviewer feedback before merging
- Squash-merge to keep main history clean

**SHOULD:**
- Keep PRs focused and reasonably sized
- Include before/after examples for visual changes
- Add test results or validation evidence

---

## Coding Standards

### Python Style

**MUST:**
- Follow PEP 8 style guide
- Use 4 spaces for indentation (no tabs)
- Limit lines to 100 characters (flexible for readability)
- Use snake_case for functions and variables
- Use PascalCase for classes
- Use UPPER_CASE for constants

**Imports:**
- MUST group in order: standard library, third-party, local
- MUST sort alphabetically within groups
- SHOULD use absolute imports

**Example:**
```python
import argparse
import subprocess
import sys

from rich.console import Console
from tqdm import tqdm

from .utils import parse_timestamp
from .constants import DEFAULT_THRESHOLD
```

### Naming Conventions

**Functions:**
- MUST use descriptive verb phrases: `calculate_speed()`, `parse_silencedetect_output()`
- SHOULD be under 50 lines (extract helpers if longer)
- MUST document parameters and return values for public functions

**Variables:**
- MUST use descriptive names (avoid abbreviations except common ones: `fps`, `pts`, `dB`)
- MUST avoid single-letter names except loop counters and mathematical formulas

**Constants:**
- MUST define at module top
- MUST use UPPER_CASE: `DEFAULT_THRESHOLD = -30.0`

### Type Hints

**SHOULD:**
- Use type hints for function signatures (Python 3.6+)
- Use Optional[] for nullable types
- Use List[], Dict[], Tuple[] for collections

**Example:**
```python
from typing import List, Tuple, Optional

def calculate_segments(
    silence_intervals: List[Tuple[float, float]],
    video_duration: float,
    buffer_seconds: float = 1.0
) -> List[Tuple[float, float, str]]:
    """Calculate video segments from silence intervals.

    Args:
        silence_intervals: List of (start, end) tuples in seconds
        video_duration: Total video duration in seconds
        buffer_seconds: Buffer to add before non-silent segments

    Returns:
        List of (start, end, type) tuples where type is "silent" or "non-silent"
    """
    pass
```

### Error Handling

**MUST:**
- Check for required dependencies (FFmpeg, FFprobe) at startup
- Validate user inputs before processing
- Provide actionable error messages
- Catch subprocess exceptions and explain failures
- Exit with non-zero status code on errors

**Example:**
```python
import shutil

def check_dependencies():
    """Verify FFmpeg and FFprobe are installed."""
    if not shutil.which("ffmpeg"):
        print("Error: FFmpeg not found. Install FFmpeg and add to PATH.", file=sys.stderr)
        print("Visit: https://ffmpeg.org/download.html", file=sys.stderr)
        sys.exit(1)

    if not shutil.which("ffprobe"):
        print("Error: FFprobe not found. Install FFmpeg suite.", file=sys.stderr)
        sys.exit(1)
```

### Documentation

**Docstrings:**
- MUST include for public functions and classes
- SHOULD use Google or NumPy docstring format
- MUST document all parameters and return values
- SHOULD include usage examples for complex functions

**Inline Comments:**
- SHOULD explain "why" not "what"
- MUST clarify non-obvious logic
- SHOULD reference external resources (docs, issues, specs)

---

## Testing & Verification

### Testing Philosophy

VideoSpeeder follows **Test-Assisted Development (TAD)** principles:
- Tests as executable documentation
- Quality over coverage - tests must "pay rent" via comprehension value
- Smart application of TDD (test-first when it adds value)
- Scratch → Promote workflow for exploratory testing

### Test Quality Standards

Every test MUST include Test Doc comment blocks with these fields:

1. **Why:** Business reason, bug reference, or regression guard
2. **Contract:** What invariant/behavior this test asserts (plain English)
3. **Usage Notes:** How to call the API, gotchas, edge cases
4. **Quality Contribution:** What failures this catches, what it documents
5. **Worked Example:** Sample inputs → outputs

**Python Format:**
```python
def test_given_iso_date_when_parsing_invoice_then_returns_normalized_cents():
    """
    Test Doc:
    - Why: Regression guard for rounding bug in AUD processing (#482)
    - Contract: Returns total_cents as int and timezone-aware datetime with exact cent accuracy
    - Usage Notes: Pass currency='AUD'; strict=True raises on unknown fields
    - Quality Contribution: Prevents silent money loss; showcases canonical call pattern
    - Worked Example: "1,234.56 AUD" -> 123_456 cents; "2025-10-11+10:00" -> aware datetime
    """
    # Arrange
    invoice_text = "1,234.56 AUD"
    invoice_date = "2025-10-11+10:00"

    # Act
    result = parse_invoice(invoice_text, invoice_date, currency='AUD', strict=True)

    # Assert
    assert result['total_cents'] == 123_456
    assert result['date'].tzinfo is not None
```

**Test Naming:**
- MUST use Given-When-Then format: `test_given_X_when_Y_then_Z()`
- OR use descriptive behavioral format: `test_silence_detection_with_multiple_intervals()`

### Scratch → Promote Workflow

**Scratch Tests (`tests/scratch/`):**
- MAY be written for fast exploration and iteration
- MUST be excluded from CI (via `.gitignore` or CI config)
- Are temporary learning tools, not durable test suite
- Can be messy, incomplete, or experimental

**Promotion Criteria (when to move from scratch/ to unit/):**
Keep tests that are:
- **Critical path** - core functionality that must always work
- **Opaque behavior** - non-obvious logic that needs explanation
- **Regression-prone** - areas with history of breaking
- **Edge cases** - boundary conditions and error handling

**Promotion Requirements:**
- MUST include complete Test Doc comment block (all 5 fields)
- MUST follow naming conventions
- MUST move to `tests/unit/` or `tests/integration/`
- MUST be deterministic and reliable

**Deletion:**
- Non-valuable scratch tests MUST be deleted
- Keep learning notes in PR description or commit message

### Test-Driven Development (TDD) Guidance

**TDD SHOULD be used for:**
- Complex algorithms (speed calculations, segment merging)
- API surface area (CLI argument parsing, function signatures)
- Critical business logic (silence detection, filter graph generation)
- Regression fixes (reproduce bug, write test, fix code)

**TDD MAY be skipped for:**
- Simple operations (file existence checks, string formatting)
- Configuration changes (default values, help text)
- Trivial wrappers around external libraries

**When using TDD:**
- Follow RED-GREEN-REFACTOR cycles
- Write failing test first
- Write minimal code to pass
- Refactor for clarity
- Tests document expected behavior clearly

**Avoid:**
- Dogmatic test-first for everything
- Tests that just verify mock calls
- Tests more complex than the code they test

### Test Organization

**Directory Structure:**
```
tests/
├── scratch/          # Temporary exploration (gitignored, not in CI)
├── unit/             # Isolated component tests
├── integration/      # Multi-component tests
├── e2e/              # Full-system tests (optional)
└── fixtures/         # Shared test data (sample videos, expected outputs)
```

**MUST:**
- Keep `tests/scratch/` excluded from CI
- Name test files: `test_<module>.py`
- Mirror source structure in test structure

**SHOULD:**
- Use realistic fixtures (actual video clips, real FFmpeg output)
- Prefer test data over mocks when practical

### Test Reliability

**MUST:**
- NOT use network calls (use fixtures for external data)
- NOT use sleep/timers (use time mocking if needed)
- Be deterministic (no random behavior, no flaky tests)
- Be reasonably fast (unit tests < 1s each)

**MUST handle:**
- Platform differences (macOS, Linux, Windows paths)
- FFmpeg version variations (detect capabilities)
- Missing optional dependencies gracefully

### Mock Usage Policy

**Default: Targeted Mocking**
- Prefer real data and fixtures over mocks
- Mock only when necessary (external services, slow operations, unavailable resources)

**When mocking:**
- MUST document WHY real dependency isn't used
- SHOULD keep mocks simple and behavior-focused
- MUST NOT test mock implementation details
- SHOULD verify mocks match real behavior

**Example:**
```python
def test_ffmpeg_processing_handles_codec_detection():
    """
    Test Doc:
    - Why: Ensure correct encoder selection without running full FFmpeg
    - Contract: get_video_codec() returns codec string from ffprobe JSON
    - Usage Notes: Mocking ffprobe because running on real video is slow
    - Quality Contribution: Documents codec detection logic, fast unit test
    - Worked Example: h264 -> "h264", hevc -> "hevc", av1 -> "av1"

    Mock Rationale: Running ffprobe on real videos adds 500ms+ per test.
    Mock behavior verified against real ffprobe output in integration tests.
    """
    # Test implementation with mocked subprocess call
```

### Manual Testing Requirements

**Before marking task complete:**
- MUST test with representative video samples
- MUST verify across at least 2 resolutions (e.g., 720p, 1080p)
- MUST check visual elements if UI changes involved
- MUST verify error messages are helpful

**Test Scenarios:**
- Normal case: typical video with clear speech and silences
- Edge case: very short silences, very long silences
- Boundary case: no silences, all silence
- Format variations: different codecs, aspect ratios, frame rates

**Makefile Targets:**
- MUST provide `make test` for primary test suite
- SHOULD provide scenario-specific targets (`make test-segment`, `make test-gpu`)

---

## Tooling & Automation

### Required Tools

**MUST have installed:**
- Python 3.6+ (3.9+ recommended)
- FFmpeg 4.x+ with ffprobe
- pip or pip3 for dependency management

**SHOULD have installed:**
- make (for standardized commands)
- Git 2.x+ (for version control)

**MAY have installed:**
- NVIDIA CUDA Toolkit (for GPU acceleration)
- NVENC/CUVID drivers (for hardware encoding/decoding)

### Dependency Management

**MUST:**
- List all Python dependencies in `requirements.txt`
- Pin major versions: `tqdm>=4.0,<5.0`
- Keep dependencies minimal (justify each addition)

**SHOULD:**
- Use virtual environments for development
- Document system dependencies in README
- Test dependency installation on clean system

### Linting & Formatting

**SHOULD:**
- Use `black` for Python code formatting
- Use `flake8` for linting
- Use `mypy` for type checking (when type hints present)

**Configuration:**
- Keep configuration in `pyproject.toml` or `setup.cfg`
- Enforce in CI when configured

### Makefile Standards

**MUST provide:**
- `make install` - Install dependencies
- `make test` - Run primary test suite
- `make clean` - Remove generated files
- `make help` - Show available targets

**Example:**
```makefile
.PHONY: install test clean help

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	pip3 install -r requirements.txt

test: ## Run test with sample video
	python3 videospeeder.py -i samples/input.mp4 -o output.mp4 --gpu

clean: ## Remove generated files
	rm -f *.mp4 *.vtt

.DEFAULT_GOAL := help
```

---

## Complexity Assessment

All features and tasks MUST be assessed using the Complexity Score (CS 1-5) system defined in the [Constitution § Complexity-First Estimation Policy](../rules/constitution.md#complexity-first-estimation-policy).

**MUST:**
- Score all 6 factors (S, I, D, N, F, T) on 0-2 scale
- Sum to total P (0-12) and map to CS-1 through CS-5
- Include confidence score (0.00-1.00)
- List assumptions, dependencies, and risks
- Define phases for CS ≥ 4 (including flags, rollout, rollback)

**MUST NOT:**
- Use time-based estimates (hours, days, "quick", "fast")
- Imply duration or deadlines
- Commit to completion dates

**SHOULD:**
- Ask clarifying questions when novelty (N) is high
- Break CS-5 epic tasks into multiple smaller features
- Document why each factor received its score

See [Idioms § Complexity Calibration Examples](idioms.md#complexity-calibration-examples) for reference scoring.

---

*These rules are authoritative and enforceable. Deviations must be documented in project plans with clear rationale and approval.*
