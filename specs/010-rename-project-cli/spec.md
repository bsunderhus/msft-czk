# Feature Specification: Rename Project and Provide Proper Executable

**Feature Branch**: `010-rename-project-cli`
**Created**: 2026-03-09
**Status**: Draft
**Input**: User description: "let's rename the project and provide a proper executable"

## Clarifications

### Session 2026-03-09

- Q: What is the delivery mechanism for the executable? → A: Standalone binary uploaded to GitHub Releases — no Python required; users download directly via `curl`/`wget`.
- Q: Which platforms should the binary target? → A: Linux x86-64 + macOS (Apple Silicon and Intel).
- Q: How should releases be published? → A: GitHub Actions workflow triggered manually (workflow_dispatch) — not automatic on tag push, not fully manual.
- Q: How should the README install instructions present the download? → A: Per-platform one-liners — three separate `curl` commands, one per platform, user picks the right one.
- Q: How should releases be versioned? → A: Semantic versioning (`v1.0.0`); version is read from the project metadata at workflow runtime — no version input on the workflow_dispatch trigger.
- Q: Where should the `curl` one-liner place the downloaded binary? → A: Current directory — `curl ... -o msft-czk && chmod +x msft-czk && ./msft-czk`; no PATH config or sudo required.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Install and invoke the tool by its new name (Priority: P1)

A user installs the tool from source and invokes it by the new executable name. The old name no longer works. All documentation, help text, and error messages reference the new name consistently.

**Why this priority**: The executable name is the primary user-facing identity of the tool. This is the core deliverable of the rename.

**Independent Test**: Install the package in a fresh virtual environment and run `msft-czk --help` — it should display the tool's help. Running the old name should fail with "command not found".

**Acceptance Scenarios**:

1. **Given** the package is installed, **When** the user runs `msft-czk --help`, **Then** the help text is displayed with the new name in the usage line.
2. **Given** the package is installed, **When** the user runs the old command `cz-tax-wizard`, **Then** the shell reports the command is not found.
3. **Given** the package is installed, **When** the user runs `msft-czk` with valid PDF inputs, **Then** the tool produces correct tax output as before.

---

### User Story 2 - Download and run the binary in one step (Priority: P1)

A user with no Python or pip installed downloads the self-contained `msft-czk` binary from the GitHub Releases page and runs it immediately. No installation wizard, no dependency setup.

**Why this priority**: This is the "dead simple" use case explicitly requested — zero prerequisites, single download, works immediately.

**Independent Test**: On a machine with no Python installed, `curl`-download the binary from the latest GitHub Release, mark it executable, and run `./msft-czk --help` — it must succeed.

**Acceptance Scenarios**:

1. **Given** a machine with no Python runtime, **When** the user downloads the binary from GitHub Releases and marks it executable, **Then** `./msft-czk --help` prints the usage text.
2. **Given** the latest GitHub Release page, **When** a user visits it, **Then** a downloadable binary asset named `msft-czk` (or platform-suffixed variant) is present.
3. **Given** the binary is downloaded, **When** the user runs it with valid PDF arguments, **Then** it produces correct tax output identical to the source-installed version.

---

### User Story 3 - Consistent naming across the codebase (Priority: P2)

A developer clones the repository and finds a single, consistent project identity: the package distribution name, the Python module name, the CLI command, and any internal strings all use the new name.

**Why this priority**: Inconsistent naming causes confusion for contributors and misleads users reading source code or error messages.

**Independent Test**: Search the repository for the old name — zero occurrences remain in source files, configuration, and documentation.

**Acceptance Scenarios**:

1. **Given** the repository, **When** a developer searches all source and config files for the old project name, **Then** no occurrences are found (except in git history and migration notes).
2. **Given** a development install, **When** a developer runs the test suite, **Then** all tests pass using the new package import path.
3. **Given** the pyproject.toml, **When** the developer reads it, **Then** the distribution name, the entry-point command, and the package directory all reflect the new name.

---

### Edge Cases

- What happens if a user has both the old and new name installed simultaneously (e.g., in the same virtualenv)? The old entry point must be absent after a clean reinstall.
- How are in-code string literals that mention the old project name (e.g., in error messages or help text) handled?
- What happens if the binary is run on a platform it was not built for? It should fail with a clear error from the OS (not silently corrupt output).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tool MUST be invocable via the command `msft-czk` after installation.
- **FR-002**: The old command name `cz-tax-wizard` MUST NOT be registered as an entry point after the rename.
- **FR-003**: The Python package distribution name MUST be updated to match the new project identity.
- **FR-004**: The Python module directory under `src/` MUST be renamed to match the new package name.
- **FR-005**: All internal imports MUST be updated to reference the new module name.
- **FR-006**: All tests MUST be updated to import from the new module name and MUST continue to pass.
- **FR-007**: The `--help` output MUST display the new command name in the usage line.
- **FR-008**: Any user-visible string in error messages or prompts that references the old project name MUST be updated.
- **FR-009**: Self-contained binaries MUST be produced for Linux x86-64, macOS Apple Silicon (arm64), and macOS Intel (x86-64), and attached as assets to each GitHub Release — none require a Python runtime on the target machine.
- **FR-010**: The README MUST include three per-platform `curl` one-liners (Linux x86-64, macOS arm64, macOS x86-64), each downloading the binary to the current directory, marking it executable, and showing the invocation as `./msft-czk`.
- **FR-011**: A GitHub Actions workflow MUST exist that builds all platform binaries and publishes a GitHub Release when manually triggered (workflow_dispatch) — it MUST NOT trigger automatically on push or tag.
- **FR-012**: The workflow_dispatch trigger MUST have no version input — the workflow MUST read the version from the project metadata (e.g. `pyproject.toml`) and use it as the Git tag and GitHub Release name.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After installation, running `msft-czk --help` succeeds and running `cz-tax-wizard` fails — verifiable in under 30 seconds.
- **SC-002**: The entire test suite (all currently passing tests) passes without modification beyond the import path change.
- **SC-003**: Zero occurrences of the old project name remain in tracked source files, configuration, and documentation.
- **SC-004**: A developer unfamiliar with the old name can install and use the tool correctly using only the README and `--help` output.
- **SC-005**: A user with no Python installed can download and run `msft-czk` from a GitHub Release in under 2 minutes using only the README one-liner for their platform.
- **SC-006**: Triggering the release workflow (no inputs required) produces a GitHub Release tagged with the version from `pyproject.toml`, with three binary assets attached (Linux x86-64, macOS arm64, macOS x86-64), without manual file uploads.

## Assumptions

- The new name applies uniformly to: the pip distribution package, the Python module, and the CLI entry-point command.
- No backward-compatibility shim (alias) for the old command name is required.
- The git repository name on disk is not part of this rename (only the package/tool identity changes).
- Existing test fixtures and PDF samples do not need renaming.
- Target platforms for the standalone binary: Linux x86-64, macOS Apple Silicon (arm64), macOS Intel (x86-64).
