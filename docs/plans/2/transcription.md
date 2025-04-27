# Plan: Add Whisper Transcription Capability (Issue #2)

This plan outlines the steps to add video transcription functionality to the `videospeeder` project using OpenAI's Whisper model.

## Phase 1: Setup Dependencies

**Goal:** Add the necessary library and ensure it's installed correctly.

*   **Task 1.1: Add `openai-whisper` to `requirements.txt`**
    *   **Description:** Add the `openai-whisper` package to the project's dependencies file.
    *   **Success Criteria:** `openai-whisper` is listed in `videospeeder_project/requirements.txt`.
*   **Task 1.2: Update `Makefile`'s `install` target**
    *   **Description:** Ensure the `install` target in the Makefile correctly installs all dependencies listed in `requirements.txt`, including the newly added `openai-whisper`.
    *   **Success Criteria:** Running `make install` successfully installs `openai-whisper` along with other dependencies.

## Phase 2: Implement Transcription Script

**Goal:** Create a standalone Python script for performing transcription.

*   **Task 2.1: Create `videospeeder_project/transcribe.py`**
    *   **Description:** Create a new Python file to house the transcription logic.
    *   **Success Criteria:** The file `videospeeder_project/transcribe.py` exists.
*   **Task 2.2: Implement basic Whisper transcription logic**
    *   **Description:** Add Python code to load a Whisper model, transcribe an input audio/video file, and save the output as a VTT file. Use the code snippet provided in the initial request as a starting point.
    *   **Success Criteria:** The script can successfully transcribe a sample media file and produce a VTT output file.
*   **Task 2.3: Add command-line argument parsing**
    *   **Description:** Use `argparse` to allow users to specify the input video file path, the desired output VTT file path, and optionally the Whisper model size (e.g., "tiny", "base", "small", "medium", "large"). Default to "large" if not specified.
    *   **Success Criteria:** The script accepts `--input`, `--output`, and `--model` command-line arguments.

## Phase 3: Integrate with Makefile

**Goal:** Make the transcription script easily runnable via the Makefile.

*   **Task 3.1: Add `transcribe` target to `Makefile`**
    *   **Description:** Add a new target named `transcribe` to `videospeeder_project/Makefile`. This target should execute the `videospeeder_project/transcribe.py` script. It should require input and output file paths as arguments (e.g., `make transcribe INPUT=input.mp4 OUTPUT=subs.vtt`).
    *   **Success Criteria:** Running `make transcribe INPUT=<path> OUTPUT=<path>` executes the transcription script with the specified files.
*   **Task 3.2: Update `Makefile`'s `help` target**
    *   **Description:** Add information about the new `transcribe` target to the `help` target output in the Makefile.
    *   **Success Criteria:** Running `make help` displays usage instructions for the `transcribe` target.

## Phase 4: Documentation & Memory

**Goal:** Update project documentation and memory graph.

*   **Task 4.1: Add Plan to Memory Graph**
    *   **Description:** Add this plan document as a 'Plan' entity in the project's memory knowledge graph.
    *   **Success Criteria:** The plan exists as an entity in the memory graph.
*   **Task 4.2: Update README (Optional)**
    *   **Description:** Consider adding a section to the main `README.md` or `videospeeder_project/README.md` briefly describing the new transcription feature and how to use it via the Makefile.
    *   **Success Criteria:** README is updated if deemed necessary.
*   **Task 4.3: Update `.gitignore`**
    *   **Description:** Add `videospeeder_project/*.vtt` to `.gitignore` to prevent generated subtitle files from being committed.
    *   **Success Criteria:** `.gitignore` includes the pattern `videospeeder_project/*.vtt`.

## Checklist

*   [ ] **Phase 1: Setup Dependencies**
    *   [ ] Task 1.1: Add `openai-whisper` to `requirements.txt`
    *   [ ] Task 1.2: Update `Makefile`'s `install` target
*   [ ] **Phase 2: Implement Transcription Script**
    *   [ ] Task 2.1: Create `videospeeder_project/transcribe.py`
    *   [ ] Task 2.2: Implement basic Whisper transcription logic
    *   [ ] Task 2.3: Add command-line argument parsing
*   [ ] **Phase 3: Integrate with Makefile**
    *   [ ] Task 3.1: Add `transcribe` target to `Makefile`
    *   [ ] Task 3.2: Update `Makefile`'s `help` target
*   [ ] **Phase 4: Documentation & Memory**
    *   [ ] Task 4.1: Add Plan to Memory Graph
    *   [ ] Task 4.2: Update README (Optional)
    *   [x] Task 4.3: Update `.gitignore`

## Overall Success Criteria

*   The `openai-whisper` library is added as a dependency and installed correctly.
*   A new script `videospeeder_project/transcribe.py` exists and can transcribe video files using Whisper, accepting input/output paths and model size via CLI arguments.
*   A `make transcribe INPUT=<in> OUTPUT=<out>` command is available to run the transcription.
*   The `make help` command documents the new target.
*   This plan is added to the memory graph.