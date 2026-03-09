# Tasks: Rename Project and Provide Proper Executable

**Input**: Design documents from `/specs/010-rename-project-cli/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/cli-contract.md ✅, quickstart.md ✅

**Tests**: No dedicated test tasks — spec does not request TDD. Existing test suite is used as validation (all tests must pass after rename).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Add build tooling required for Phase 4 (binary distribution).

- [x] T001 Add `pyinstaller>=6` to `[project.optional-dependencies] dev` in `pyproject.toml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Rename the source directory and reconfigure the package metadata. **MUST complete before any user story work begins** — until this phase is done, neither `msft-czk` nor any test import will resolve.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T002 Rename source directory using `git mv src/cz_tax_wizard src/msft_czk`
- [x] T003 Delete stale build artifact directory `src/cz_tax_wizard.egg-info/`
- [x] T004 Update `pyproject.toml`: set `name = "msft-czk"`, change `[project.scripts]` entry from `cz-tax-wizard = "cz_tax_wizard.cli:main"` to `msft-czk = "msft_czk.cli:main"`, and update `[tool.setuptools.packages.find] where = ["src"]` (already correct — verify unchanged)
- [x] T005 Bump version in `pyproject.toml` to `1.0.0` (MAJOR bump per Constitution — breaking CLI interface change: `cz-tax-wizard` → `msft-czk`)
- [x] T006 Reinstall the package: `pip install -e .`

**Checkpoint**: `msft-czk` entry point is now registered (imports will still fail until Phase 3).

---

## Phase 3: User Story 1 — Install and invoke tool by new name (Priority: P1) 🎯 MVP

**Goal**: `msft-czk --help` succeeds; `cz-tax-wizard` is gone; all source imports resolve.

**Independent Test**: After this phase, run `msft-czk --help` and confirm it prints the usage text with `msft-czk` in the usage line. Confirm `cz-tax-wizard` reports "command not found".

### Implementation for User Story 1

- [x] T007 [US1] Update module docstring in `src/msft_czk/cli.py`: replace every occurrence of `cz-tax-wizard` with `msft-czk`
- [x] T008 [US1] Update all `from cz_tax_wizard` imports → `from msft_czk` in `src/msft_czk/cli.py` (depends on T007 — same file)
- [x] T009 [P] [US1] Update all `from cz_tax_wizard` imports → `from msft_czk` in `src/msft_czk/reporter.py`
- [x] T010 [P] [US1] Update all `from cz_tax_wizard` imports → `from msft_czk` in `src/msft_czk/cnb.py`
- [x] T011 [P] [US1] Update all `from cz_tax_wizard` imports → `from msft_czk` in `src/msft_czk/extractors/fidelity.py`
- [x] T012 [P] [US1] Update all `from cz_tax_wizard` imports → `from msft_czk` in `src/msft_czk/extractors/fidelity_espp_periodic.py`
- [x] T013 [P] [US1] Update all `from cz_tax_wizard` imports → `from msft_czk` in `src/msft_czk/extractors/fidelity_rsu.py`
- [x] T014 [P] [US1] Update all `from cz_tax_wizard` imports → `from msft_czk` in `src/msft_czk/extractors/morgan_stanley.py`
- [x] T015 [P] [US1] Update all `from cz_tax_wizard` imports → `from msft_czk` in `src/msft_czk/calculators/dual_rate.py`
- [x] T016 [P] [US1] Update all `from cz_tax_wizard` imports → `from msft_czk` in `src/msft_czk/calculators/paragraph6.py`
- [x] T016a [P] [US1] Update all `from cz_tax_wizard` imports → `from msft_czk` in `src/msft_czk/extractors/base.py`
- [x] T017 [US1] Verify: run `msft-czk --help` (must succeed, usage line shows `msft-czk`) and run `cz-tax-wizard` (must report command not found)

**Checkpoint**: User Story 1 is fully functional — the renamed CLI works end-to-end.

---

## Phase 4: User Story 2 — Download and run binary in one step (Priority: P1)

**Goal**: A self-contained binary for each platform is produced and published to GitHub Releases via a manually triggered workflow. No Python required on the target machine.

**Independent Test**: Build the binary locally with `pyinstaller --onefile` and run `./dist/msft-czk --help` without any virtualenv active. Confirm it prints usage text.

### Implementation for User Story 2

- [x] T018 [US2] Create `msft-czk.spec` PyInstaller spec file at the repository root with `--onefile`, `name=msft-czk`, entry point `src/msft_czk/cli.py`, and explicit `hiddenimports` for `pdfminer.high_level`, `pdfminer.layout`, `pdfminer.pdfpage`, `pdfminer.pdfinterp`, `pdfminer.converter`
- [x] T019 [US2] Smoke test local build: run `pyinstaller msft-czk.spec`, then run `./dist/msft-czk --help` outside any virtualenv; confirm usage text printed with no import errors
- [x] T020 [US2] Create `.github/workflows/release.yml` with: `on: workflow_dispatch` trigger (no inputs), a `build` job with a 3-entry matrix (`ubuntu-latest`/`msft-czk-linux-x86_64`, `macos-latest`/`msft-czk-macos-arm64`, `macos-13`/`msft-czk-macos-x86_64`), each runner installing deps + PyInstaller, building via `pyinstaller msft-czk.spec` (produces `dist/msft-czk`), then renaming with `mv dist/msft-czk dist/<matrix.asset_name>` before uploading the artifact via `actions/upload-artifact@v4`
- [x] T021 [US2] Add `release` job to `.github/workflows/release.yml`: reads version with `python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"`, guards against existing tag, downloads all 3 artifacts with `actions/download-artifact@v4`, and creates the GitHub Release with `gh release create "v$VERSION" --generate-notes <asset-paths>`
- [x] T022 [US2] Verify workflow YAML is structurally valid by inspecting jobs/steps manually and confirming the trigger is `workflow_dispatch` with no inputs, all 3 matrix entries are present, and the release job depends on the build job

**Checkpoint**: User Story 2 is complete — a manually triggered workflow builds and publishes all 3 binaries.

---

## Phase 5: User Story 3 — Consistent naming across the codebase (Priority: P2)

**Goal**: Zero occurrences of the old name in tracked source files, configuration, and documentation. Full test suite passes.

**Independent Test**: Run `grep -r "cz_tax_wizard\|cz-tax-wizard" src/ tests/ pyproject.toml README.md CLAUDE.md` — must return zero results. Run `pytest` — all tests must pass.

### Implementation for User Story 3

- [x] T023 [P] [US3] Update all `from cz_tax_wizard` imports → `from msft_czk` in `tests/unit/test_models.py`
- [x] T024 [P] [US3] Update all `from cz_tax_wizard` imports → `from msft_czk` in `tests/unit/test_models_rsu.py`
- [x] T025 [P] [US3] Update all `from cz_tax_wizard` imports → `from msft_czk` in `tests/unit/test_reporter.py`
- [x] T026 [P] [US3] Update all `from cz_tax_wizard` imports → `from msft_czk` in `tests/unit/test_cnb_daily.py`
- [x] T027 [P] [US3] Update all `from cz_tax_wizard` imports → `from msft_czk` in `tests/unit/test_calculators/test_currency.py`
- [x] T028 [P] [US3] Update all `from cz_tax_wizard` imports → `from msft_czk` in `tests/unit/test_calculators/test_dual_rate.py`
- [x] T029 [P] [US3] Update all `from cz_tax_wizard` imports → `from msft_czk` in `tests/unit/test_calculators/test_paragraph6.py`
- [x] T030 [P] [US3] Update all `from cz_tax_wizard` imports → `from msft_czk` in `tests/unit/test_extractors/test_fidelity.py`
- [x] T031 [P] [US3] Update all `from cz_tax_wizard` imports → `from msft_czk` in `tests/unit/test_extractors/test_fidelity_espp_periodic.py`
- [x] T032 [P] [US3] Update all `from cz_tax_wizard` imports → `from msft_czk` in `tests/unit/test_extractors/test_fidelity_rsu.py`
- [x] T033 [P] [US3] Update all `from cz_tax_wizard` imports → `from msft_czk` in `tests/unit/test_extractors/test_morgan_stanley.py`
- [x] T034 [P] [US3] Update all `from cz_tax_wizard` imports → `from msft_czk` in `tests/integration/test_full_run.py`
- [x] T035 [P] [US3] Update all `from cz_tax_wizard` imports → `from msft_czk` in `tests/integration/test_fidelity_espp_periodic_full_run.py`
- [x] T036 [P] [US3] Update all `from cz_tax_wizard` imports → `from msft_czk` in `tests/integration/test_fidelity_rsu_full_run.py`
- [x] T037 [US3] Run `pytest` and confirm all tests pass with the new import path
- [x] T038 [US3] Run `grep -r "cz_tax_wizard\|cz-tax-wizard" src/ tests/ pyproject.toml README.md CLAUDE.md` and confirm zero matches

**Checkpoint**: All three user stories are independently functional and the codebase is clean.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation updates and final validation.

- [x] T039 Add `## Installation` section to `README.md` with the three per-platform `curl` one-liners, substituting the actual GitHub repo URL (e.g. `https://github.com/bsunderhus/cz-tax-wizard/releases/latest/download/`) for each asset name (`msft-czk-linux-x86_64`, `msft-czk-macos-arm64`, `msft-czk-macos-x86_64`)
- [x] T039a Add migration note to `CHANGELOG.md` (create if absent): document that v1.0.0 renames the CLI command from `cz-tax-wizard` to `msft-czk` (Constitution: breaking CLI interface change MUST include migration note in changelog)
- [x] T040 [P] Update `CLAUDE.md` Project Structure section: change `src/cz_tax_wizard/` → `src/msft_czk/` in the directory tree
- [x] T041 Run the full verification checklist from `specs/010-rename-project-cli/quickstart.md` and confirm all items pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2 — source imports must resolve for CLI to work
- **US2 (Phase 4)**: Depends on Phase 3 — binary is built from renamed source; PARALLEL with Phase 5
- **US3 (Phase 5)**: Depends on Phase 2 — can run in parallel with Phase 4
- **Polish (Phase 6)**: Depends on Phases 3, 4, 5 all complete

### User Story Dependencies

- **US1 (P1)**: Starts after Foundational — no dependency on US2 or US3
- **US2 (P1)**: Starts after US1 complete (binary must be built from renamed source)
- **US3 (P2)**: Starts after Foundational — can run in parallel with US2

### Within Each User Story

- All [P]-marked tasks within a story operate on different files and can be done simultaneously
- T017 (US1 verification) must follow T007–T016
- T019 (binary smoke test) must follow T018 (spec file creation)
- T021 (release job) must follow T020 (build matrix job)
- T037/T038 (US3 validation) must follow T023–T036

---

## Parallel Opportunities

### Phase 3 (US1) — All import updates can run simultaneously

```
Task T008: src/msft_czk/cli.py
Task T009: src/msft_czk/reporter.py
Task T010: src/msft_czk/cnb.py
Task T011: src/msft_czk/extractors/fidelity.py
Task T012: src/msft_czk/extractors/fidelity_espp_periodic.py
Task T013: src/msft_czk/extractors/fidelity_rsu.py
Task T014: src/msft_czk/extractors/morgan_stanley.py
Task T015: src/msft_czk/calculators/dual_rate.py
Task T016: src/msft_czk/calculators/paragraph6.py
```

### Phase 5 (US3) — All test import updates can run simultaneously

```
Tasks T023–T036: 14 test files, all independent
```

### Phases 4 and 5 — Can run in parallel after Phase 3

```
Phase 4 (US2): T018 → T019 → T020 → T021 → T022
Phase 5 (US3): T023–T036 (parallel) → T037 → T038
```

---

## Implementation Strategy

### MVP (User Stories 1 + 3 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (**critical**)
3. Complete Phase 3: US1 (command rename) — **stop and verify `msft-czk --help`**
4. Complete Phase 5: US3 (test imports + cleanliness sweep)
5. **STOP and VALIDATE**: run `pytest`, run grep, confirm zero old names

This delivers a fully renamed package with a clean codebase and passing tests — without the binary/CI work.

### Full Delivery

1. MVP above
2. Add Phase 4: US2 (PyInstaller binary + GitHub Actions workflow)
3. Add Phase 6: Polish (README install section, CLAUDE.md update)

### Notes

- T002 (`git mv`) preserves git history for all renamed files — prefer over shell `mv`
- T005 (version bump to 1.0.0) is required by the Constitution for breaking CLI interface changes
- If `pdfminer` hidden imports in T018 are insufficient, run the binary and add any `ModuleNotFoundError` module to the spec's `hiddenimports` list
- Commit after each phase checkpoint
