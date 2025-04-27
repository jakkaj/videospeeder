# Plan: Video Speeder Initial Implementation

**GitHub Issue:** #1

**Project Goal:** Create a Python command-line tool (`videospeeder`) that takes a video file, identifies silent sections based on a volume threshold, speeds up those sections by a configurable factor, adds a visual indicator (">>") during sped-up parts, and outputs the modified video.

**Core Technologies:**

*   **Language:** Python 3.x
*   **Video Processing:** FFmpeg (called via Python's `subprocess`)
*   **Argument Parsing:** Python's `argparse` module
*   **Progress Reporting:** `tqdm` library

---

## Phase 1: Project Setup & CLI

*   **Task 1.1:** Create the main project directory structure (`videospeeder_project/`, `videospeeder.py`, `requirements.txt`, `README.md`) and add `tqdm` to `requirements.txt`.
    *   *Success Criteria:* Directory and files exist, `requirements.txt` lists `tqdm`.
*   **Task 1.2:** Implement CLI argument parsing using `argparse` in `videospeeder.py`.
    *   Define arguments: `--input`, `--output`, `--threshold`, `--duration`, `--speed`, `--indicator`.
    *   Set default values as specified in the plan.
    *   *Success Criteria:* Script can parse arguments correctly, providing help messages and handling missing required arguments.
*   **Task 1.3:** Add a Makefile to `videospeeder_project/` with targets for `run`, `install`, `clean`, and `help`.
    *   *Success Criteria:* Makefile exists and allows running, installing, and cleaning the tool easily.
*   **Task 1.4:** Add a Makefile `test` target to run the tool on `/mnt/c/Users/jorkni/Downloads/test speed upper.mp4`.
    *   *Success Criteria:* `make test` runs the tool on the provided file and produces `output_test.mp4`.

_Note: The Makefile enables easy running, installation, and cleaning of the tool. Use `make run ARGS="..."` for custom runs, `make test` for the provided test file, and `make install` to install dependencies._
## Phase 2: Silence Detection

*   **Task 2.1:** Implement a function to execute the FFmpeg `silencedetect` filter using `subprocess.run()`.
    *   Construct the command dynamically based on input file, threshold, and duration arguments.
    *   *Success Criteria:* Function correctly calls FFmpeg and captures its `stderr`.
*   **Task 2.2:** Implement parsing logic for the `silencedetect` output.
    *   Extract `silence_start` and `silence_end` timestamps from the captured `stderr`.
    *   Store these intervals in a suitable data structure (e.g., a list of tuples).
    *   *Success Criteria:* Function returns an accurate list of silent intervals.

## Phase 3: Video Processing Core Logic

*   **Task 3.1:** Calculate non-silent and silent segment timestamps.
    *   Based on the list of silent intervals and the video duration, determine the start/end times for all segments (silent and non-silent).
    *   *Success Criteria:* A correct list of all segments with their type (silent/non-silent) and timestamps is generated.
*   **Task 3.2:** Implement the dynamic FFmpeg filtergraph generation.
    *   Create logic to build the complex filter string using `trim`, `atrim`, `setpts`, `atempo`, `drawtext` (conditionally), and `concat`.
    *   Ensure correct calculation of sped-up segment durations for `drawtext` timing.
    *   Handle the `--indicator` flag to conditionally include `drawtext`.
    *   *Success Criteria:* A valid and correct FFmpeg filtergraph string is generated based on the calculated segments and arguments.
*   **Task 3.3:** Implement the function to execute the main FFmpeg processing command.
    *   Construct the final command using the input file, generated filtergraph, and output file path.
    *   Include standard encoding options (e.g., `-c:v libx264 -crf 23 -c:a aac -b:a 128k`).
    *   Use `subprocess.run()` to execute the command.
    *   *Success Criteria:* Function correctly calls FFmpeg with the complex filtergraph.

## Phase 4: Integration, Error Handling & Documentation

*   **Task 4.1:** Integrate all components in `videospeeder.py`.
    *   Orchestrate the flow: parse args -> detect silence -> calculate segments -> build filtergraph -> execute processing.
    *   *Success Criteria:* The script runs end-to-end for a sample video.
*   **Task 4.2:** Add basic error handling and user feedback.
    *   Check if FFmpeg command exists.
    *   Validate essential arguments (e.g., input file exists).
    *   Print informative messages during execution stages.
    *   Catch potential exceptions during subprocess calls.
    *   *Success Criteria:* Script provides helpful messages and handles common errors gracefully.
*   **Task 4.3:** Implement progress reporting using `tqdm`.
    *   Capture FFmpeg progress output (requires adding `-progress pipe:1` or similar to the FFmpeg command and reading `stdout`).
    *   Parse progress data (e.g., total duration, current time/frame).
    *   Update a `tqdm` progress bar based on the parsed progress.
    *   *Success Criteria:* A clear `tqdm` progress bar is displayed during the main FFmpeg processing step.
*   **Task 4.4:** Create the initial `README.md`.
    *   Explain the tool's purpose, prerequisites (Python 3, FFmpeg installation, `tqdm`), and basic usage instructions with CLI examples.
    *   *Success Criteria:* `README.md` provides clear instructions for users.

---

## High-Level Flow Diagram

```mermaid
graph TD
    A[Start: User runs `videospeeder.py` with args] --> B{Parse Arguments};
    B --> C[Run FFmpeg `silencedetect`];
    C --> D{Parse Silence Timestamps};
    D --> E[Calculate Segment Timestamps];
    E --> F[Build FFmpeg Filtergraph];
    F --> G[Run FFmpeg Processing];
    G --> H[Save Output Video];
    H --> I[End: Display Status];

    subgraph "FFmpeg Filtergraph Steps"
        F1[Split Segments (trim/atrim)] --> F2[Speed Up Silent (setpts/atempo)];
        F2 --> F3[Add Indicator (drawtext)];
        F3 --> F4[Rejoin Segments (concat)];
    end

    F --> G;
```

---

## Checklist

**Phase 1: Project Setup & CLI**
- [x] Task 1.1: Create project directory structure.
- [x] Task 1.2: Implement CLI argument parsing.
- [x] Task 1.3: Add Makefile with run/install/clean/help targets.
- [x] Task 1.4: Add Makefile test target for /mnt/c/Users/jorkni/Downloads/test speed upper.mp4.

**Phase 1: Project Setup & CLI**
- [x] Task 1.1: Create project directory structure.
- [x] Task 1.2: Implement CLI argument parsing.
- [x] Task 1.3: Add Makefile with run/install/clean/help targets.
- [x] Task 1.4: Add Makefile test target for /mnt/c/Users/jorkni/Downloads/test speed upper.mp4.
- [x] Task 1.5: Add optional GPU acceleration (--gpu flag) for video encoding.
- [x] Task 1.6: Add optional GPU-accelerated decoding (--gpu-decode flag, experimental, NVIDIA CUVID/NVDEC).

**Phase 2: Silence Detection**
- [x] Task 2.1: Implement FFmpeg `silencedetect` execution function.
- [x] Task 2.2: Implement `silencedetect` output parsing logic.

**Phase 3: Video Processing Core Logic**
- [x] Task 3.1: Calculate non-silent and silent segment timestamps.
- [x] Task 3.2: Implement dynamic FFmpeg filtergraph generation.
- [x] Task 3.3: Implement main FFmpeg processing execution function.

**Phase 4: Integration, Error Handling & Documentation**
- [x] Task 4.1: Integrate all components in `videospeeder.py`.
- [x] Task 4.2: Add basic error handling and user feedback.
- [x] Task 4.3: Implement progress reporting using `tqdm`.
- [x] Task 4.4: Create the initial `README.md`.

---

## Success Criteria

The implementation is complete when:

1.  The command-line tool can be executed successfully with valid arguments.
2.  The tool correctly identifies silent segments in a sample video based on the provided threshold and duration.
3.  The tool generates an output video where silent segments are sped up by the specified factor.
4.  The ">>" indicator is correctly displayed in the bottom-left corner during sped-up segments (unless disabled).
5.  The tool displays clear progress information using `tqdm` during video processing.
6.  The tool handles basic errors gracefully (e.g., missing input file, FFmpeg not found).
7.  The `README.md` provides clear instructions for installation and usage.
8.  The tool supports GPU acceleration for video encoding via the `--gpu` flag (NVIDIA NVENC).
9.  The tool supports experimental GPU-accelerated decoding via the `--gpu-decode` flag (NVIDIA CUVID/NVDEC).