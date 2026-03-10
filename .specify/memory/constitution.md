<!--
SYNC IMPACT REPORT
==================
Version change: N/A (initial) → 1.0.0
Modified principles: N/A (initial constitution)
Added sections:
  - Core Principles (I–V)
  - Legal Compliance & Data Standards
  - Development Workflow
  - Governance
Templates reviewed:
  - .specify/templates/plan-template.md       ✅ aligned (Constitution Check section present)
  - .specify/templates/spec-template.md       ✅ aligned (no conflicts with principles)
  - .specify/templates/tasks-template.md      ✅ aligned (documentation tasks covered under Polish phase)
  - .specify/templates/commands/ (commands)   ✅ no command files found — nothing to update
Follow-up TODOs: none — all placeholders resolved.
-->

# CZ Tax Wizard Constitution

## Core Principles

### I. Documentation-First

All public-facing code — functions, classes, modules, CLI commands, and APIs — MUST include
clear, accurate documentation before a feature is considered complete. Documentation MUST
describe purpose, parameters, return values, raised errors, and any domain-specific tax
context relevant to the implementation.

**Rationale**: Tax analysis tools are used by non-experts making legally and financially
consequential decisions. Undocumented code cannot be audited, trusted, or safely extended.

### II. Tax Accuracy

All tax calculations, form mappings, and regulatory interpretations MUST be traceable to
a specific Czech tax regulation, official guidance, or publicly available tax authority
source (e.g., Finanční správa ČR). Any ambiguity in interpretation MUST be surfaced
explicitly to the user — never silently defaulted.

**Rationale**: Incorrect tax advice can result in penalties, back-taxes, or legal liability
for users. Accuracy is non-negotiable and traceability is the mechanism that enforces it.

### III. Data Privacy & Security

Personally identifiable information (PII) and financial data MUST NOT be logged, persisted,
or transmitted beyond the minimum necessary for the analysis task. No user data MUST be
stored without explicit user consent and clear disclosure of purpose and retention period.

**Rationale**: Tax data is among the most sensitive categories of personal information.
Handling it carelessly violates user trust and Czech/EU data protection law (GDPR, ZOOÚ).

### IV. Testability

Every tax calculation, data transformation, and form-mapping rule MUST be independently
testable with deterministic inputs and outputs. Business logic MUST be decoupled from I/O,
UI, and external service calls to permit unit testing without side effects.

**Rationale**: Tax rules change annually. Isolated, tested logic enables safe updates and
regression detection when regulations are amended.

### V. Simplicity & Transparency

The simplest correct solution MUST be preferred over clever or over-engineered alternatives.
Analysis results presented to users MUST be explainable: every computed value MUST be
accompanied by the reasoning or rule that produced it. Complexity MUST be justified against
a concrete requirement — YAGNI applies.

**Rationale**: Users relying on tax guidance must be able to understand and verify outputs.
Opaque computations erode trust and make auditability impossible.

## Legal Compliance & Data Standards

Czech tax law and EU regulations impose non-negotiable constraints on this toolkit:

- Tax year scope MUST be clearly stated for every analysis (e.g., "Tax Year 2025").
- All monetary amounts MUST be handled in CZK (Czech Koruna) unless the user's scenario
  explicitly involves foreign income, in which case the applicable exchange rate source
  (e.g., Czech National Bank — ČNB) MUST be cited.
- The toolkit MUST NOT provide legal advice. Outputs MUST be clearly labeled as informational
  estimates. Users MUST be directed to a qualified tax advisor for final filing decisions.
- GDPR Article 5 principles (purpose limitation, data minimisation, storage limitation)
  MUST be respected in any feature that handles user-supplied financial or personal data.

## Development Workflow

- Features MUST NOT be merged without documentation (see Principle I).
- Tax rule references MUST be included as inline comments or linked docs at the point of
  implementation, not only in external design documents.
- Any change to a tax calculation MUST be accompanied by updated or new tests (see
  Principle IV) before the PR is approved.
- Breaking changes to public APIs or CLI interfaces MUST increment the MAJOR version and
  include a migration note in the changelog.
- All code review checklists MUST include a "Tax Accuracy" gate that verifies regulatory
  citations are present and correct.

## Governance

This constitution supersedes all informal conventions and prior undocumented practices.
Amendments require:

1. A written proposal describing the changed principle and motivation.
2. Review and approval by at least one domain stakeholder (tax or engineering lead).
3. A migration plan if existing features are affected.
4. Version increment per the policy below and update of `LAST_AMENDED_DATE`.

**Versioning policy**:
- MAJOR: Removal or redefinition of a principle, or backward-incompatible governance change.
- MINOR: New principle or section added, or materially expanded guidance.
- PATCH: Clarifications, wording fixes, or non-semantic refinements.

All PRs and code reviews MUST verify compliance with the five Core Principles above.
Complexity exceptions MUST be documented in the plan's Complexity Tracking table before
implementation begins.

**Version**: 1.0.0 | **Ratified**: 2026-03-07 | **Last Amended**: 2026-03-07
