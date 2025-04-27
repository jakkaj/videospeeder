# Plan: Enhance Fast-Forward Indicator (Issue #3)

**Objective:** Replace the current `>>` text indicator during fast-forward segments with the `videospeeder_project/fastforward.svg` icon and the calculated speed (e.g., '110x') displayed next to it in a large font (200pt).

**Plan File:** `docs/plans/3/fast_forward_overlay.md`

## Phase 1: Setup and Preparation

*   **Task 1.1: SVG to PNG Conversion Strategy:**
    *   **Action:** Decide how to handle the SVG file for FFmpeg's `overlay` filter. FFmpeg typically requires bitmap images (like PNG) for overlays.
    *   **Decision:** Convert `videospeeder_project/fastforward.svg` to `videospeeder_project/fastforward.png` as a one-time pre-processing step. This avoids adding runtime dependencies for SVG rendering within the Python script.
    *   **Tool:** Use a command-line tool like `inkscape` or `rsvg-convert` for the conversion. Example: `inkscape -w 100 -h 100 videospeeder_project/fastforward.svg -o videospeeder_project/fastforward.png` (adjust size `-w`/`-h` as needed).
    *   **Success Criteria:** `videospeeder_project/fastforward.png` is created and suitable for overlaying.
*   **Task 1.2: Add PNG to Repository:**
    *   **Action:** Add the generated `videospeeder_project/fastforward.png` to the Git repository.
    *   **Success Criteria:** The PNG file is tracked by Git.
*   **Task 1.3: Font Selection for Speed Text:**
    *   **Action:** Identify a suitable default font available to FFmpeg's `drawtext` filter or specify a path to a font file. Using a common system font is preferable. We'll start with a default and see if specification is needed.
    *   **Success Criteria:** A font strategy for the speed text is determined.

## Phase 2: Implementation in `videospeeder.py`

*   **Task 2.1: Modify `build_filtergraph` Function:**
    *   **Action:** Update the logic within the `if typ == "silent":` block.
    *   **Details:**
        *   Retrieve the calculated `current_speed`.
        *   Remove the existing `drawtext=text='>>':...` line.
        *   Construct a new filter chain segment using `overlay` for the PNG and `drawtext` for the speed text.
    *   **Success Criteria:** `build_filtergraph` function signature and internal logic updated to support the new overlay.
*   **Task 2.2: Implement PNG Overlay:**
    *   **Action:** Add the `overlay` filter to the video filter chain (`vf`) for silent segments.
    *   **Revised Filter Strategy:**
        1.  Load the PNG image as a separate input to `filter_complex`.
        2.  Inside the loop for silent segments: Apply `setpts` to the video segment.
        3.  After the loop, before `concat`: Use the `overlay` filter, taking the sped-up video segment stream and the image input stream, placing the overlay. Apply `drawtext` *after* the overlay. Position bottom-right: `overlay=x=W-w-10:y=H-h-10`.
    *   **Success Criteria:** The `fastforward.png` icon is correctly overlaid on silent segments.
*   **Task 2.3: Implement Speed Text Overlay:**
    *   **Action:** Add the `drawtext` filter after the `overlay` filter for silent segments.
    *   **Details:**
        *   Format the text as `f"{current_speed:.0f}x"`.
        *   Set `fontsize=200`.
        *   Set `fontcolor=white` (or another visible color).
        *   Set position `x` and `y` relative to the icon (e.g., to the left of the icon). Example: `x=W-overlay_w-text_w-20:y=H-overlay_h/2-text_h/2` (approximate vertical centering next to icon).
        *   Reference the chosen font if necessary.
    *   **Success Criteria:** The speed multiplier text (e.g., "110x") is displayed next to the icon with the specified size and color during silent segments.

## Phase 3: Testing

*   **Task 3.1: Basic Functionality Test:**
    *   **Action:** Run `videospeeder.py` with the `--indicator` flag on a video with clear silent parts.
    *   **Success Criteria:** The overlay (icon + text) appears *only* during sped-up sections and disappears during normal speed sections. The speed value displayed is correct.
*   **Task 3.2: Visual Appearance Test:**
    *   **Action:** Check the size, positioning, and clarity of the icon and text. Assess if 200pt is appropriate or too large/small.
    *   **Success Criteria:** The overlay is visually acceptable and doesn't obstruct important video content excessively. Font size and positioning are confirmed or marked for adjustment.
*   **Task 3.3: Variable Speed Test:**
    *   **Action:** Test with silent sections of varying lengths to ensure the `current_speed` calculation and display are accurate for different speedup factors.
    *   **Success Criteria:** The displayed speed factor dynamically reflects the calculated speed for each silent segment.
*   **Task 3.4: Resolution Test:**
    *   **Action:** Test with input videos of different resolutions (e.g., 720p, 1080p, 4K if possible).
    *   **Success Criteria:** The overlay scales reasonably or maintains a consistent appearance across different resolutions. Positioning logic (`W-w-10`, etc.) works as expected.

## Phase 4: Refinement and Documentation

*   **Task 4.1: Adjust Size/Positioning:**
    *   **Action:** Based on testing (Task 3.2, 3.4), adjust the PNG size (Task 1.1), overlay position (Task 2.2), and text size/position (Task 2.3) in the code.
    *   **Success Criteria:** Final visual appearance is satisfactory.
*   **Task 4.2: Update Documentation:**
    *   **Action:** Briefly mention the new indicator style in `README.md` or other relevant docs.
    *   **Success Criteria:** Documentation reflects the current indicator behavior.
*   **Task 4.3: Code Cleanup:**
    *   **Action:** Ensure code is clean, well-commented, and adheres to project standards.
    *   **Success Criteria:** Code is finalized and reviewed.
*   **Task 4.4: Update Memory Graph:**
    *   **Action:** Create `SourceFile` and `FileChange` entities in the memory graph for the modifications to `videospeeder.py`, linking them to this plan (Issue #3).
    *   **Success Criteria:** Memory graph accurately reflects the changes made.

## Workflow Diagram

```mermaid
graph TD
    subgraph build_filtergraph for Silent Segment
        direction LR
        S_Start[Input Video Segment] --> S_Speed[Calculate Speed (current_speed)]
        S_Speed --> S_Setpts[Apply setpts filter: PTS / current_speed]
        S_Setpts --> S_Overlay[Apply overlay filter: Use pre-loaded PNG input]
        S_Overlay --> S_Drawtext[Apply drawtext filter: Text = f"{current_speed:.0f}x", Size=200pt]
        S_Drawtext --> S_Output[Output Video Segment Stream]
    end

    InputImage[Load fastforward.png] --> S_Overlay

    Start --> GetSegments[Calculate Segments]
    GetSegments --> LoopSegments{Loop Through Segments}
    LoopSegments -- Silent --> build_filtergraph
    LoopSegments -- Non-Silent --> Trim[Apply trim filter]
    build_filtergraph --> CollectStreams[Collect Segment Streams]
    Trim --> CollectStreams
    CollectStreams -- End Loop --> Concat[Concatenate Streams]
    Concat --> End[Final Filtergraph]

```

## Checklist

**Phase 1: Setup and Preparation**
- [x] Task 1.1: SVG to PNG Conversion Strategy Decided & Executed (Skipped: PNG provided by user)
- [x] Task 1.2: Add PNG to Repository (Skipped: PNG provided by user)
- [x] Task 1.3: Font Selection for Speed Text

**Phase 2: Implementation in `videospeeder.py`**
- [x] Task 2.1: Modify `build_filtergraph` Function Structure
- [x] Task 2.2: Implement PNG Overlay Logic
- [x] Task 2.3: Implement Speed Text Overlay Logic

**Phase 3: Testing**
- [x] Task 3.1: Basic Functionality Test Passed
- [x] Task 3.2: Visual Appearance Test Passed (or adjustments noted)
- [x] Task 3.3: Variable Speed Test Passed
- [x] Task 3.4: Resolution Test Passed (or adjustments noted)

**Phase 4: Refinement and Documentation**
- [x] Task 4.1: Adjust Size/Positioning (if needed)
- [x] Task 4.2: Update Documentation
- [x] Task 4.3: Code Cleanup
- [x] Task 4.4: Update Memory Graph

## Success Criteria

The overall task is complete when:
1.  The fast-forward indicator uses the `fastforward.png` icon and displays the calculated speed multiplier text (e.g., "110x") next to it.
2.  The text size is approximately 200pt (adjusted based on testing for visual appeal).
3.  The overlay appears correctly only during sped-up silent sections.
4.  The implementation passes all tests outlined in Phase 3.
5.  The plan checklist is fully marked (`[x]`).
6.  The code is clean and documentation is updated.
7.  Memory graph is updated to reflect the changes.