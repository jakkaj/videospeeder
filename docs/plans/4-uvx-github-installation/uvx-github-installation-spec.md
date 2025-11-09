# UVX GitHub Installation Support

## Summary

Enable users to run VideoSpeeder directly from GitHub without manual installation using `uvx` (the UV project's tool execution utility). This eliminates the need for users to clone the repository, install dependencies manually, or manage virtual environments.

**Value Proposition:** One-command execution from GitHub makes VideoSpeeder instantly accessible for quick tasks, experimentation, and CI/CD integration. Users can run the latest version directly:

```bash
uvx --from git+https://github.com/USERNAME/videospeeder videospeeder -i input.mp4 -o output.mp4
```

## Goals

- **Frictionless Execution:** Users can run VideoSpeeder without cloning or installing
- **Zero Setup Time:** No manual dependency installation or virtual environment management
- **Latest Version Access:** Users can run from main branch or specific commits/tags
- **CI/CD Integration:** Enable easy integration into automated workflows
- **Maintain Backward Compatibility:** Existing installation methods (pip, manual) continue working
- **Standard Python Packaging:** Use modern Python packaging standards (PEP 517/518/621)

## Non-Goals

- Publishing to PyPI (future consideration, separate from this feature)
- Supporting other package runners besides uvx (pipx support may come automatically)
- Bundling FFmpeg with the package (remains external dependency)
- Creating a GUI installer or wrapper
- Supporting Python versions below 3.6
- Converting project to setuptools-based packaging (prefer modern pyproject.toml)

## Complexity

**Score:** CS-3 (medium)

**Breakdown:**
- **Surface Area (S):** 1 - Multiple files (add pyproject.toml, reorganize project structure, potentially move scripts)
- **Integration Breadth (I):** 1 - One new external tooling dependency (uvx/uv ecosystem)
- **Data & State (D):** 0 - No data schema or migrations
- **Novelty & Ambiguity (N):** 1 - Some unknowns around project structure requirements for uvx compatibility
- **Non-Functional Constraints (F):** 0 - Standard packaging practices, no strict constraints
- **Testing & Rollout (T):** 1 - Integration testing with uvx, multiple platform validation

**Total Points:** 4 → **CS-3 (medium)**

**Confidence:** 0.75

**Assumptions:**
- Current project structure can be adapted to Python package format
- uvx works with git+ URLs for GitHub repositories
- FFmpeg remains external dependency (documented requirement)
- Entry point can be created without major code refactoring

**Dependencies:**
- uv/uvx tool (for testing and validation)
- Git repository hosted on GitHub
- Modern Python packaging tools (hatchling or setuptools with pyproject.toml)

**Risks:**
- Project structure may need reorganization (moving scripts into package)
- Asset files (fastforward.png) may need special handling in package
- FFmpeg external dependency must be clearly documented as prerequisite
- Users may not understand uvx/uv tooling (need clear documentation)

**Phases:**
1. Research uvx requirements and best practices
2. Design package structure (decide on layout)
3. Implement pyproject.toml and package configuration
4. Reorganize project files if needed
5. Create entry point and test local installation
6. Test uvx execution from GitHub
7. Update documentation with installation instructions
8. Validate on multiple platforms (macOS, Linux)

## Acceptance Criteria

### 1. UVX Execution from GitHub
**Given** a user has uvx installed and FFmpeg available,
**When** they run `uvx --from git+https://github.com/USERNAME/videospeeder videospeeder --help`,
**Then** the VideoSpeeder help text displays successfully without errors.

### 2. Full Processing Pipeline via UVX
**Given** a user has uvx and FFmpeg installed,
**When** they run `uvx --from git+https://github.com/USERNAME/videospeeder videospeeder -i sample.mp4 -o output.mp4`,
**Then** the video processes successfully and output.mp4 is created with correct speed adjustments.

### 3. Asset Files Accessible
**Given** VideoSpeeder is run via uvx with --indicator flag,
**When** processing a video,
**Then** the fastforward.png asset loads successfully and overlays appear correctly.

### 4. Dependency Installation Automatic
**Given** a clean environment with only uvx installed,
**When** running VideoSpeeder via uvx,
**Then** all Python dependencies (tqdm, rich, openai-whisper) install automatically without user intervention.

### 5. Version Pinning Works
**Given** a user wants to run a specific version,
**When** they run `uvx --from git+https://github.com/USERNAME/videospeeder@v1.2.3 videospeeder`,
**Then** that specific tagged version executes (future-proofing for when tags exist).

### 6. Error Messages Helpful
**Given** a user runs VideoSpeeder via uvx without FFmpeg installed,
**When** the tool checks for dependencies,
**Then** a clear error message explains that FFmpeg must be installed separately with installation links.

### 7. Backward Compatibility Maintained
**Given** existing users have installed VideoSpeeder manually,
**When** they update to the new packaged version,
**Then** their existing workflows (manual execution, Makefile targets) continue working unchanged.

### 8. Documentation Complete
**Given** a new user reads the README,
**When** they look for installation instructions,
**Then** uvx installation method is prominently featured with clear examples and FFmpeg prerequisite noted.

## Risks & Assumptions

### Risks

1. **Project Structure Changes:** May require significant reorganization (moving `videospeeder_project/` contents to package root or creating proper package structure)
   - **Mitigation:** Design minimal structure changes; maintain backward compatibility with existing scripts

2. **Asset File Packaging:** PNG/SVG assets must be included in package and accessible at runtime
   - **Mitigation:** Use `package_data` in pyproject.toml; test asset loading thoroughly

3. **FFmpeg Not Bundled:** Users must install FFmpeg separately, may cause confusion
   - **Mitigation:** Clear documentation; runtime checks with helpful error messages

4. **Platform-Specific Issues:** Path handling, FFmpeg locations may differ across platforms
   - **Mitigation:** Test on macOS and Linux; use `shutil.which()` for FFmpeg detection

5. **UVX Adoption:** Users may not be familiar with uv/uvx tooling
   - **Mitigation:** Provide multiple installation methods (uvx, pip, manual); clear quickstart guide

### Assumptions

1. **GitHub Repository:** Project will remain hosted on GitHub with public access
2. **Modern Python:** Users have Python 3.6+ available (3.9+ recommended)
3. **UV Stability:** uvx tool API remains stable (currently in active development)
4. **No Binary Compilation:** Pure Python package with no C extensions (remains true)
5. **Asset Files Small:** PNG/SVG assets small enough to include in package (<1MB total)

## Open Questions

1. **Project Structure:** Should we reorganize to a src/ layout or keep current structure?
   - Options: (A) Create `src/videospeeder/` package, (B) Move scripts to `videospeeder/` package root, (C) Minimal changes with entry point wrapper
   - Implications: Affects import paths, testing structure, existing workflows

2. **Package Name:** Should the package name match the repo name or be different?
   - Options: (A) `videospeeder` (matches repo), (B) `video-speeder` (hyphenated), (C) `videospeeder-cli` (explicit)
   - Preference: `videospeeder` for simplicity

3. **Entry Point Name:** What should the command be called when installed?
   - Current: `python videospeeder.py` (script execution)
   - Options: (A) `videospeeder`, (B) `video-speeder`, (C) `vspeeder` (short alias)
   - Preference: `videospeeder` (clear and memorable)

4. **Build Backend:** Which build system to use?
   - Options: (A) `hatchling` (modern, simple), (B) `setuptools` (traditional, widely supported), (C) `flit` (minimal)
   - Preference: `hatchling` for modern Python packaging, but `setuptools` if compatibility needed

5. **Optional Dependencies:** Should openai-whisper be optional?
   - Currently: Required in requirements.txt
   - Options: (A) Make all dependencies required (simplest), (B) Make whisper optional via extras (e.g., `uvx videospeeder[transcribe]`)
   - Trade-off: Simpler vs. smaller base install

6. **Version Source:** Where should version number be stored?
   - Options: (A) `__init__.py` with `__version__`, (B) `pyproject.toml` only (single source of truth), (C) Git tags via `setuptools_scm`
   - Preference: Single source in pyproject.toml or git tags for simplicity

7. **Testing Strategy:** How to test uvx installation in CI?
   - Options: (A) Manual testing only, (B) GitHub Actions workflow with uvx, (C) Test both uvx and pip installation methods
   - Preference: Add GitHub Actions test for uvx to prevent regressions

## ADR Seeds (Optional)

### Decision Drivers

- **Ease of Use:** Primary goal is making VideoSpeeder instantly runnable without setup
- **Modern Packaging:** Should follow current Python packaging best practices (2024+)
- **Minimal Breaking Changes:** Existing workflows must continue working
- **Maintainability:** Package structure should be simple to maintain and understand
- **Asset Handling:** Must reliably include and load PNG/SVG assets at runtime

### Candidate Alternatives

**Package Structure:**
- **A. Src Layout:** `src/videospeeder/` with package code, pyproject.toml at root
  - Pros: Clean separation, prevents accidental imports, modern best practice
  - Cons: Requires significant reorganization, import path changes

- **B. Flat Package:** `videospeeder/` at root with scripts moved inside
  - Pros: Simpler migration, less file movement
  - Cons: Less clean separation between package and project files

- **C. Minimal Wrapper:** Keep current structure, create thin entry point wrapper
  - Pros: Minimal changes, existing code untouched
  - Cons: Non-standard structure, may complicate packaging

**Build Backend:**
- **A. Hatchling:** Modern, simple, good defaults
- **B. Setuptools:** Traditional, maximum compatibility, widely known
- **C. PDM/Poetry:** Full project management, but heavy for simple CLI tool

### Stakeholders

- **End Users:** Want easiest installation and usage
- **Contributors:** Need simple, maintainable project structure
- **CI/CD Users:** Want reliable, reproducible installation in pipelines
- **Maintainers:** Need to balance innovation with backward compatibility

---

**Next Steps:**
- Run `/plan-2-clarify` to resolve open questions
- Create ADR if architectural decisions need formal documentation
- Begin implementation once questions resolved
