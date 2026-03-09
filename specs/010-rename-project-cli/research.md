# Research: Rename Project and Provide Proper Executable

**Date**: 2026-03-09
**Branch**: `010-rename-project-cli`

## R-001: Binary Bundling Tool

**Decision**: PyInstaller 6+ with `--onefile`

**Rationale**:
- Single command produces a self-contained executable; zero source code changes required
- Includes the Python runtime, pdfplumber, click, and all native extensions in one file
- Mature, actively maintained, largest community for troubleshooting
- `--onefile` cold-start of 1–3 s is fully acceptable for a once-a-year tax tool

**Alternatives Considered**:

| Tool | Why Rejected |
|------|-------------|
| Nuitka | Compiles to C — requires a C toolchain on every runner, significantly more complex CI; no performance benefit justifies that cost for this use case |
| shiv / zipapp | Produces `.pyz` archives that still require Python on the target machine — violates FR-009 |
| cx_Freeze | Less maintained; no advantage over PyInstaller for a personal CLI tool |

---

## R-002: GitHub Actions Runner Matrix

**Decision**: Three separate native runners via matrix strategy — no cross-compilation.

PyInstaller cannot cross-compile: the binary embeds OS-specific Python libraries and native extensions. Each target must be built on its own runner.

| Target | Runner label | Binary asset name |
|--------|-------------|-------------------|
| Linux x86-64 | `ubuntu-latest` | `msft-czk-linux-x86_64` |
| macOS Apple Silicon (arm64) | `macos-latest` | `msft-czk-macos-arm64` |
| macOS Intel (x86-64) | `macos-13` | `msft-czk-macos-x86_64` |

**Notes**:
- `macos-latest` defaults to arm64 (M3) as of mid-2024 — correct for Apple Silicon binaries.
- `macos-13` is the last Intel runner available. GitHub has signalled deprecation post-2025; if it becomes unavailable, migrate to `macos-13-large` or equivalent Intel runner at that time.
- `ubuntu-latest` is always x86-64.

---

## R-003: Version Extraction from pyproject.toml

**Decision**: Inline Python using `tomllib` (stdlib since Python 3.11).

```bash
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
echo "VERSION=$VERSION" >> "$GITHUB_ENV"
```

The tag is created as `v$VERSION`. The version value in `pyproject.toml` must follow semver
(e.g. `1.0.0`) without a `v` prefix — the workflow adds the prefix at release time.

**Workflow guard** — fail if tag already exists:
```bash
git fetch --tags
if git rev-parse "v$VERSION" >/dev/null 2>&1; then
  echo "ERROR: tag v$VERSION already exists. Bump the version in pyproject.toml first."
  exit 1
fi
```

**Alternatives Considered**:
- `grep`/`sed` pipeline — brittle for edge cases in TOML formatting; `tomllib` is authoritative
- `setuptools` `pkg_resources` — deprecated API, unnecessary dependency

---

## R-004: GitHub Release Creation

**Decision**: `gh release create` (GitHub CLI, pre-installed on all GitHub Actions runners).

**Rationale**: Simpler than `softprops/action-gh-release` — no third-party action dependency,
no version pinning to manage, shell commands are immediately auditable.

**Minimal workflow snippet**:
```yaml
- name: Create GitHub Release
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    gh release create "v${{ env.VERSION }}" \
      --title "v${{ env.VERSION }}" \
      --generate-notes \
      artifacts/msft-czk-linux-x86_64/msft-czk-linux-x86_64 \
      artifacts/msft-czk-macos-arm64/msft-czk-macos-arm64 \
      artifacts/msft-czk-macos-x86_64/msft-czk-macos-x86_64
```

**Alternative** (`softprops/action-gh-release`): Glob-based asset attachment is more
convenient when there are many assets, but the overhead of tracking an external action
is not justified for 3 fixed assets.

---

## R-005: PyInstaller Hidden Imports (pdfplumber)

pdfplumber uses several dynamically imported modules (e.g. `pdfminer` sub-packages).
PyInstaller may miss some; if the binary fails at runtime with `ModuleNotFoundError`,
add the missing module via `--hidden-import`:

```bash
pyinstaller --onefile \
  --hidden-import=pdfminer.high_level \
  --hidden-import=pdfminer.layout \
  --name msft-czk \
  src/msft_czk/cli.py
```

A `.spec` file should be committed to the repository so the build is reproducible and
hidden imports are tracked in version control rather than reconstructed ad hoc.

---

## Summary: All Research Unknowns Resolved

| Unknown | Decision | Confidence |
|---------|----------|-----------|
| Binary bundler | PyInstaller `--onefile` | High |
| CI runner matrix | Native runner per platform, 3-way matrix | High |
| Version source | `tomllib` from `pyproject.toml` | High |
| Release tool | `gh release create` | High |
| Hidden imports | `.spec` file with explicit hidden-import list | Medium (validate in Phase B) |
