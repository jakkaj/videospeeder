<!--
Sync Impact Report
==================
Version: 1.0.0 (initial)
Amendment Date: 2025-11-09
Affected Sections: All (initial creation)
Outstanding TODOs: None
Supporting Docs Updated: rules.md, idioms.md, architecture.md created
Templates Updated: N/A (no project-specific templates exist)
Rationale: Initial constitution establishing foundational governance for VideoSpeeder project
-->

# VideoSpeeder Project Constitution

**Version:** 1.0.0
**Ratified:** 2025-11-09
**Last Amended:** 2025-11-09

## Guiding Principles

### § 1. User Workflow Efficiency
**Principle:** Save users time by automating video editing tasks that are tedious and time-consuming when done manually.

**Rationale:** The primary value proposition of VideoSpeeder is to reduce hours of manual video editing into minutes of automated processing. Every feature must be evaluated against whether it improves user workflow efficiency.

**Application:**
- MUST prioritize features that automate repetitive tasks
- SHOULD minimize configuration complexity while maintaining flexibility
- MUST provide clear feedback on time saved and processing progress

### § 2. Intelligent Automation
**Principle:** Apply smart algorithms and heuristics rather than requiring users to make manual decisions.

**Rationale:** Users should benefit from intelligent defaults that "just work" for common cases, with the option to override when needed.

**Application:**
- MUST use dynamic calculations (e.g., variable speed based on silence duration)
- SHOULD provide sensible defaults based on common use cases
- MAY expose advanced parameters for edge cases and power users

### § 3. Clarity and Transparency
**Principle:** Users must understand what the tool is doing and why.

**Rationale:** Video editing involves creative intent. Users need visibility into modifications to trust the output.

**Application:**
- MUST provide visual indicators when modifications are applied (optional)
- MUST show processing statistics before and after
- SHOULD log significant decisions and calculations
- MUST surface errors in actionable, understandable language

### § 4. Flexibility and Control
**Principle:** Users should have fine-grained control over behavior when defaults don't meet their needs.

**Rationale:** Different content types (podcasts, screencasts, tutorials, vlogs) have different requirements.

**Application:**
- MUST expose key parameters (threshold, duration, speed calculations)
- SHOULD provide presets for common scenarios
- MAY allow advanced users to customize processing pipelines

### § 5. Performance Optimization
**Principle:** Leverage hardware acceleration and efficient algorithms to minimize processing time.

**Rationale:** Video processing is computationally expensive. Efficient implementation directly impacts user experience.

**Application:**
- MUST support GPU acceleration where available (NVIDIA NVENC/CUVID)
- SHOULD optimize for common video formats and resolutions
- MAY provide quality/speed trade-off options

### § 6. Accessibility
**Principle:** The tool should be easy to install, understand, and use for target audiences.

**Rationale:** A powerful tool is useless if users can't access it or understand how to use it.

**Application:**
- MUST provide clear installation instructions for major platforms
- MUST use standard package managers and distribution channels
- SHOULD minimize external dependencies and manual setup
- MUST include usage examples for common scenarios

## Quality & Verification Strategy

### Testing Philosophy
VideoSpeeder employs a **pragmatic, manual testing approach** focused on end-to-end functionality with real-world scenarios.

**Core Tenets:**
1. **Tests as Documentation (TAD):** Every test must explain why it exists, what contract it asserts, and provide usage examples
2. **Quality over Coverage:** Tests must "pay rent" through comprehension value and regression protection
3. **Real-World Validation:** Test with actual video files across different formats, resolutions, and content types
4. **Phase-Based Success Criteria:** Each development phase has explicit, testable outcomes that must pass before proceeding

### Verification Approach

**Pre-Commit Verification:**
- Manual testing with representative video samples (720p, 1080p, 4K)
- Visual verification of overlays and indicators
- Variable speed calculation validation
- Cross-platform testing (macOS primary, Linux secondary)

**Phase Validation:**
- Each phase defines explicit success criteria
- Tasks marked complete ONLY when tests pass
- Debug-first approach: add targeted debug output before guessing solutions
- Make tests resilient to environment quirks (OS, Python version, FFmpeg version)

**Makefile-Based Testing:**
- Standardized test commands (`make test`, `make test-segment`)
- Reproducible test scenarios with known inputs
- Progress feedback via tqdm and rich libraries

**Manual Test Coverage:**
- Silence detection accuracy across different audio profiles
- Speed calculation correctness for various silence durations
- Visual indicator appearance and positioning
- Codec compatibility (H.264, HEVC, AV1)
- GPU acceleration functionality and fallback behavior

### Quality Gates

**Definition of Done:**
1. Feature meets all acceptance criteria from specification
2. Manual tests pass with representative samples
3. No regressions in existing functionality
4. Performance meets reasonable expectations
5. Documentation updated (README, code comments)
6. Visual elements (if applicable) verified across resolutions

**When Tests Fail:**
1. Read error output completely
2. Add targeted debug output to understand failure
3. Make tests resilient to environment differences
4. Fix root cause (do not mask with workarounds)
5. Verify fix across multiple scenarios
6. Do NOT mark task complete until tests pass

## Delivery Practices

### Planning Cadence

**Phase-Based Planning:**
- Plans stored in `docs/plans/<ordinal>-<slug>/`
- Must request issue number if not provided (for GitHub integration)
- Use numbered phases and tasks (Phase 1, Task 1.1)
- Provide checklists (`- [ ]` / `- [x]`) for tracking
- Finish plans with overall success criteria

**Plan Execution:**
- Follow plan phases sequentially
- Do NOT mark tasks complete until tests pass
- Keep GitHub issue body and local plan in sync (when applicable)
- Add one-line comment to GitHub for meaningful changes

### Source Control Workflow

**Branching:**
- Convention: `issue-<issue>-phase-<phase>` (when using GitHub issues)
- Branch from main for new features/fixes
- Keep branches focused and short-lived

**Commits:**
- MUST use Conventional Commits format
- Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`
- Add `!` or `BREAKING CHANGE:` footer for major changes
- Reference issues in commit footer (e.g., `Fixes #123`)
- Write concise, imperative commit messages

**Pull Requests:**
- Push branch and open PR against main
- CI runs automatically on PRs (when configured)
- Merge via squash once reviews and checks pass
- Delete branch after merge

**Versioning:**
- Semantic-release handles auto-versioning (when configured)
- No manual version bumping
- Versions follow SemVer strictly

### Documentation Standards

**README Requirements:**
- Clear project description and value proposition
- Installation instructions for target platforms
- Usage examples for common scenarios
- Configuration options and parameters
- Troubleshooting guide for common issues
- Contribution invitation

**Code Documentation:**
- Inline comments for non-obvious logic
- Docstrings for public functions and classes
- CLI help text for all arguments
- Type hints where applicable (Python 3.6+)

### Standardized Commands

**Makefile Usage:**
- Provide `make install`, `make test`, `make clean`, `make help`
- Include `make` targets for common workflows
- Keep Makefile cross-platform compatible

## Governance

### Complexity-First Estimation Policy

**Prohibition of Time Estimates:**
- NEVER output or imply time, duration, or ETA in any form
- Banned terms: hours, minutes, days, "quick", "fast", "soon", deadlines
- All effort quantification MUST use Complexity Score (CS 1-5) system

**Complexity Score (CS) Rubric:**

Score points (0-2) for each factor, then sum to total P (0-12):

1. **Surface Area (S):** Files/modules touched
   - 0 = One file/module
   - 1 = Multiple files/modules
   - 2 = Many files or cross-cutting changes

2. **Integration Breadth (I):** External dependencies
   - 0 = Internal only
   - 1 = One external dependency/API
   - 2 = Multiple externals or unstable APIs

3. **Data & State (D):** Schema, migrations, concurrency
   - 0 = None
   - 1 = Minor data changes
   - 2 = Non-trivial migration or concurrency

4. **Novelty & Ambiguity (N):** Requirements clarity
   - 0 = Well-specified
   - 1 = Some ambiguity
   - 2 = Unclear specs or significant discovery needed

5. **Non-Functional Constraints (F):** Performance, security, compliance
   - 0 = Standard gates
   - 1 = Moderate constraints
   - 2 = Strict or critical constraints

6. **Testing & Rollout (T):** Test depth, flags, staged rollout
   - 0 = Unit tests only
   - 1 = Integration/e2e tests
   - 2 = Feature flags, staged rollout, backward compatibility

**CS Mapping (Total P):**
- **CS-1 (0-2 points):** Trivial - isolated tweak, no new deps, unit test touchups
- **CS-2 (3-4 points):** Small - few files, familiar code, one internal integration
- **CS-3 (5-7 points):** Medium - multiple modules, small migration or stable external API
- **CS-4 (8-9 points):** Large - cross-component, new dependency, meaningful migration, rollout plan
- **CS-5 (10-12 points):** Epic - architectural change, high uncertainty, phased rollout with flags

**Mandatory Output Fields:**
```json
{
  "complexity": {
    "score": "CS-3",
    "label": "medium",
    "breakdown": {"S": 1, "I": 1, "D": 0, "N": 1, "F": 0, "T": 1},
    "confidence": 0.75
  },
  "assumptions": ["Spec is final", "FFmpeg API stable"],
  "dependencies": ["FFmpeg 4.x+"],
  "risks": ["Codec compatibility variations"],
  "phases": ["Design", "Implementation", "Testing"]
}
```

**Enforcement:**
- For CS ≥ 4, MUST include staged rollout, feature flags, and rollback plan
- Use complexity idioms: "scope", "risk", "breadth", "unknowns"
- If uncertainty is high, ask clarifying questions and reflect in N factor
- Self-check: replace any time language with complexity reasoning

### Amendment Procedure

**Minor Changes (PATCH):**
- Clarifications, formatting, example additions
- Approved by maintainer review
- Update Last Amended date

**Moderate Changes (MINOR):**
- New principles or sections
- Expanded guidance in existing areas
- Requires discussion and consensus
- Update Last Amended date, increment MINOR version

**Major Changes (MAJOR):**
- Breaking changes to core principles
- Fundamental governance shifts
- Requires broader team agreement and rationale documentation
- Update Last Amended date, increment MAJOR version

### Compliance & Review

**Continuous Compliance:**
- All planning commands reference this constitution
- Code reviews validate against rules and idioms
- Architecture decisions trace back to guiding principles

**Review Cadence:**
- Constitution reviewed during major project milestones
- Annual review recommended for active projects
- Ad-hoc reviews when principles conflict with reality

**Conflict Resolution:**
- Rules trump idioms in case of contradiction
- Constitution trumps rules when principle is at stake
- Log deviations in plan documentation with rationale
- Escalate persistent conflicts to governance review

### Memory & Knowledge Management

**Recording Decisions:**
- Record only non-obvious, searchable decisions
- Distinguish substantive vs trivial changes
- Substantive: new modules, public interfaces, config keys, cross-cutting patterns, performance decisions, behavior-codifying tests, architectural trade-offs

**Mandatory Retrieval:**
- Search memory at start of task
- Search before implementation
- Search before answering questions

**Mandatory Update Workflow:**
- After new features or behavior changes
- After learning major codebase structure
- After discovering inconsistencies requiring design clarification
- After deciding design trade-offs

**Update Checklist (requires at least one):**
- Introduces or retires a concept
- Changes external behavior or configuration
- Documents why an approach was chosen

**File Change Tracking:**
- Search memory before modifying files
- Create SourceFile entities for significant files
- Create FileChange entities with descriptive names
- Link bidirectionally (file ↔ change)
- Link to Plan entities when applicable
- Track only substantive changes
- Use present tense for descriptions
- Update SourceFile when purpose changes

---

*This constitution serves as the authoritative governance document for the VideoSpeeder project. All planning, development, and review activities must align with the principles and practices defined herein.*
