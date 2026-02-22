# Flight Plan: Phase 2 — Folder Processing

**Plan**: [../../vad-first-pass-multi-angle-plan.md](../../vad-first-pass-multi-angle-plan.md)
**Dossier**: [./tasks.md](./tasks.md)
**Phase**: Phase 2: Folder Processing
**Generated**: 2026-02-22
**Status**: Landed

---

## Departure → Destination

**Where we are**: Phase 1 gave videospeeder a two-pass workflow — detect speech once and write a `.vad.json` sidecar, then process from that sidecar with `--vad-json`. A `--quiet` flag cleans up terminal output. But each video must still be processed individually by passing `-i` and `-o` one file at a time.

**Where we're going**: By the end of this phase, a content creator can point videospeeder at a folder of multi-angle recordings and process them all in one command. The tool discovers videos, finds the sidecar, handles duration mismatches per-file, skips already-processed outputs, and keeps going if one file fails. A `--vad-master` flag combines detection and folder processing into a single command.

---

## Flight Status

<!-- Updated by /plan-6: pending → active → done. Use blocked for problems/input needed. -->

```mermaid
stateDiagram-v2
    classDef pending fill:#9E9E9E,stroke:#757575,color:#fff
    classDef active fill:#FFC107,stroke:#FFA000,color:#000
    classDef done fill:#4CAF50,stroke:#388E3C,color:#fff
    classDef blocked fill:#F44336,stroke:#D32F2F,color:#fff

    state "1: Add CLI flags" as S1
    state "2: Video discovery" as S2
    state "3: Sidecar discovery" as S3
    state "4: Folder loop" as S4
    state "5: Vad-master mode" as S5
    state "6: Justfile + README" as S6
    state "7: E2E validation" as S7

    [*] --> S1
    S1 --> S2
    S1 --> S3
    S2 --> S4
    S3 --> S4
    S4 --> S5
    S5 --> S6
    S6 --> S7
    S7 --> [*]

    class S1,S2,S3,S4,S5 done
    class S1,S2,S3,S4,S5,S6,S7 done
```

**Legend**: grey = pending | yellow = active | red = blocked/needs input | green = done

---

## Stages

<!-- Updated by /plan-6 during implementation: [ ] → [~] → [x] -->

- [x] **Stage 1: Add folder CLI flags** — add `--folder`, `--vad-master`, `--overwrite`, `--extensions` to argparse and extend the validation matrix (`videospeeder.py`)
- [x] **Stage 2: Implement video discovery** — scan a folder for files matching video extensions, sorted alphabetically (`videospeeder.py`)
- [x] **Stage 3: Implement sidecar discovery** — find exactly one `.vad.json` or error clearly if zero or multiple found (`videospeeder.py`)
- [x] **Stage 4: Implement folder processing loop** — process all discovered videos sequentially with shared sidecar, skip existing outputs, continue on failure, print summary (`videospeeder.py`)
- [x] **Stage 5: Implement vad-master one-liner** — detect on a named master file then process the entire folder in one command (`videospeeder.py`)
- [x] **Stage 6: Justfile recipes + README update** — add `detect`, `speed-folder`, `speed-all` recipes and document new flags with multi-angle examples (`Justfile`, `README.md`)
- [x] **Stage 7: End-to-end validation** — full regression pass of all 16 acceptance criteria with real multi-angle video files

---

## Architecture: Before & After

```mermaid
flowchart LR
    classDef existing fill:#E8F5E9,stroke:#4CAF50,color:#000
    classDef changed fill:#FFF3E0,stroke:#FF9800,color:#000
    classDef new fill:#E3F2FD,stroke:#2196F3,color:#000

    subgraph Before["Before Phase 2"]
        PA1[parse_args]:::existing
        D1[Detect-only path]:::existing
        VJ1[Vad-json loader]:::existing
        SI1[Silence detection]:::existing
        CS1[calculate_segments]:::existing
        BF1[build_filtergraph]:::existing
        RF1[run_ffmpeg]:::existing

        PA1 --> D1
        PA1 --> VJ1
        PA1 --> SI1
        VJ1 --> CS1
        SI1 --> CS1
        CS1 --> BF1
        BF1 --> RF1
    end

    subgraph After["After Phase 2"]
        PA2[parse_args]:::changed
        D2[Detect-only path]:::existing
        VJ2[Vad-json loader]:::existing
        SI2[Silence detection]:::existing
        DV[discover_videos]:::new
        DS[discover_sidecar]:::new
        FL[Folder loop]:::new
        VM[Vad-master mode]:::new
        CS2[calculate_segments]:::existing
        BF2[build_filtergraph]:::existing
        RF2[run_ffmpeg]:::existing

        PA2 --> D2
        PA2 --> VM
        PA2 --> FL
        PA2 --> VJ2
        PA2 --> SI2
        VM --> DS
        VM --> DV
        FL --> DS
        FL --> DV
        DV --> FL
        FL --> CS2
        VJ2 --> CS2
        SI2 --> CS2
        CS2 --> BF2
        BF2 --> RF2
    end
```

**Legend**: existing (green, unchanged) | changed (orange, modified) | new (blue, created)

---

## Acceptance Criteria

- [ ] AC-7: Folder mode processes all videos with shared sidecar
- [ ] AC-8: Folder mode auto-discovers single sidecar
- [ ] AC-9: Folder mode errors on ambiguous (multiple) sidecars
- [ ] AC-10: `--vad-master` does detect + process in one command
- [ ] AC-11: Folder mode skips existing outputs (respects `--overwrite`)
- [ ] AC-12: Folder mode continues on single-file failure
- [ ] AC-1–AC-6, AC-13–AC-16: Full regression pass

---

## Goals & Non-Goals

**Goals**:
- `--folder`, `--vad-master`, `--overwrite`, `--extensions` flags on CLI
- Auto-discover single `.vad.json` sidecar in folder
- Process all matching videos sequentially with shared sidecar
- Skip existing outputs by default; `--overwrite` re-processes
- Continue on single-file failure with summary
- `--vad-master` combines detect + folder in one command
- Justfile recipes and README docs for multi-angle workflow

**Non-Goals**:
- Parallel video encoding (FFmpeg uses multiple cores)
- Per-angle time offset correction (NLE handles sync)
- Interactive confirmation (never prompt)
- Recursive folder scanning (flat only)
- Unit tests or mocks (Manual Only)

---

## Checklist

- [x] T009: Add `--folder`, `--vad-master`, `--overwrite`, `--extensions` flags (CS-1)
- [x] T010: Implement `discover_videos()` helper (CS-1)
- [x] T011: Implement `discover_sidecar()` helper (CS-1)
- [x] T012: Implement folder processing loop in main() (CS-3)
- [x] T013: Implement `--vad-master` one-liner mode (CS-2)
- [x] T014: Add Justfile recipes (CS-1)
- [x] T015: Update README.md (CS-2)
- [x] T016: End-to-end validation (CS-1)

---

## PlanPak

Not active for this plan.
