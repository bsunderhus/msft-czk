# Feature Specification: Broker Tax Calculator

**Feature Branch**: `001-broker-tax-calculator`
**Created**: 2026-03-07
**Status**: Draft
**Input**: User description: "let's create a tool that will help us calculate RSU and ESPP
tax declarations based on broker declaration statements. This tool will rely on PDF reading
techniques + AI for extracting data and then displaying the fields that have to be properly
populated. fields of interest are the ones related to income from foreign land in this case
(2. Priijmy ze zdroju v zahranici - metoda zapoctu dane zaplacene v zahranici)"

**Note on AI extraction**: The original description mentioned AI for data extraction. After
review, AI-based extraction was rejected in favour of deterministic structured text parsing
against the known Morgan Stanley and Fidelity PDF layouts. AI extraction is explicitly
deferred as a future enhancement.

## Clarifications

### Session 2026-03-07

- Q: Does the employer provide RSU and ESPP income in the Potvrzeni, or must the employee self-calculate and self-declare it? → A: The employer provides only base salary in the Potvrzeni (MFin 5460). The employee MUST calculate RSU vesting income and ESPP discount income from broker statements and self-declare them as additional paragraph 6 rows in the DPFDP7 employer income table.
- Q: Should the tool also parse the Potvrzeni PDF to read the base salary automatically, or does the user enter it manually? → A: The tool accepts the Potvrzeni PDF as an input, reads the base salary automatically, and outputs the complete paragraph 6 picture: base salary + RSU income + ESPP income = total row 31.
- Q: Where does AI-based PDF extraction processing happen? → A: All processing is strictly local. No PDF content, personal data, or financial figures are sent to any external service or API.
- Q: What is the output format? → A: CLI tool — structured text report printed to the console, with all form row values clearly labeled and ready to copy into the tax declaration.
- Q: How does the tool obtain the CNB annual average exchange rate? → A: The tool automatically fetches the official CNB annual average rate from the CNB public website (no personal data transmitted). If the rate is not yet published or the user prefers manual control, a `--cnb-rate` CLI flag overrides the auto-fetch. The tool always prints the rate used and its source.
- Q: How does the user specify which tax year to process? → A: User passes `--year 2024` as a required CLI flag. The tool validates that all provided PDFs contain dates within that year and warns on any outliers.
- Q: Should Fidelity ESPP account dividends be included in §8 foreign income (row 321)? → A: Yes — dividends from both Morgan Stanley and Fidelity are included in row 321, aggregated in USD then converted to CZK, and itemized by broker in the output so the user can verify each amount independently.
- Q: Is the `--potvrzeni` argument mandatory? → A: Either `--potvrzeni <path>` or `--base-salary <CZK>` must be provided — they are mutually exclusive. The §6 summary is always produced; `--base-salary` allows the user to supply the base salary directly without the PDF.
- Q: Should AI be used for PDF data extraction? → A: No. The primary extraction method is deterministic structured text parsing against the known Morgan Stanley and Fidelity PDF layouts. AI-based extraction is explicitly out of scope for this feature and deferred as a future enhancement. The tool must fail loudly with a specific error if a PDF layout does not match the expected format.
- Q: What is the maximum acceptable execution time for a full run? → A: 30 seconds for a full run (up to 5 PDFs plus Potvrzeni) on a standard laptop.
- Q: SC-001 references the filed 2024 declaration values (row 321 = 10,748 CZK, Morgan Stanley only), but the Q2 clarification requires including Fidelity dividends too — which governs? → A: Tax accuracy governs. SC-001 is updated to reference the corrected full total (Morgan Stanley + Fidelity dividends combined), with a note that the sample 2024 declaration under-reported §8 by omitting Fidelity ESPP account dividends.
- Q: What rounding method is used for USD → CZK conversion? → A: Round half-up to the nearest whole CZK (standard arithmetic rounding: 0.5 rounds up). This applies to all intermediate and final converted amounts.
- Q: How are multiple broker PDFs passed on the CLI, and how does the tool know which broker each file belongs to? → A: Broker PDFs are passed as positional arguments after all named flags (e.g., `cz-tax-wizard --year 2024 --potvrzeni cert.pdf ms-q1.pdf ms-q2.pdf fidelity.pdf`). The tool auto-detects the broker type from each PDF's content; no per-file type flag is required.
- Q: Should RSU/ESPP output be shown when `--potvrzeni` is omitted? → A: The tool requires either `--potvrzeni <path>` OR `--base-salary <value>` — one of the two is always mandatory. This ensures the base salary is always available and the complete §6 summary (base + RSU + ESPP = row 31) is always produced. `--potvrzeni` and `--base-salary` are mutually exclusive.
- Q: Should the tool confirm the detected broker type for each PDF? → A: Yes — the tool MUST print the detected broker type and account number for each positional PDF argument before extracting data (e.g., `[Morgan Stanley Q1 2024] ms-q1.pdf`), so the user can confirm auto-detection was correct.
- Q: How does the tool determine which broker PDF is RSU (Morgan Stanley) and which is ESPP (Fidelity)? → A: The tool detects broker identity by searching the PDF text content for the broker name (e.g., "Morgan Stanley" or "Fidelity" in the document header or footer). Income type classification follows from a fixed mapping: Morgan Stanley → RSU vesting rules + dividend extraction; Fidelity → ESPP purchase rules + dividend extraction. This mapping is hardcoded against the known statement formats from the verified sample PDFs.
- Q: Does the missing-quarter warning (FR-015) apply to all broker PDFs or only Morgan Stanley? → A: Morgan Stanley only. Morgan Stanley publishes quarterly statements (4 per year); the tool warns if fewer than 4 distinct quarterly periods are detected across all Morgan Stanley PDFs. Fidelity provides a single year-end consolidated report covering the full year, so no quarter check applies to Fidelity.
- Q: How does the tool handle dividends paid in currencies other than USD? → A: Non-USD dividends are out of scope for this feature. If the tool encounters a dividend in a currency other than USD, it MUST report a specific warning identifying the currency and the transaction, skip that dividend, and continue processing. No CNB rate lookup for non-USD currencies is performed.
- Q: Does US3 Acceptance Scenario 3 (multiple foreign countries) contradict the US-only assumption? → A: Yes — it contradicts. US is the only source country in scope. The multiple-countries scenario is removed from US3. Příloha č. 3 computation always assumes a single source country (United States); no per-country coefficient loop is required.
- Q: Should the tool print a per-quarter dividend breakdown (FR-016)? → A: No — FR-016 is removed. Only annual totals are required for dividends and withholding. Per-event breakdown for RSU and per-offering-period for ESPP (FR-017) is retained.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Extract Dividends and Compute Foreign Income Fields (Priority: P1)

A Microsoft employee in the Czech Republic has quarterly broker statements (Morgan Stanley
or Fidelity) as PDFs. They run the tool from the command line, providing the PDF paths.
The tool reads each PDF locally, identifies all dividend payments and US withholding tax
amounts, aggregates the totals across all quarters, and converts them to CZK using the
CNB annual average exchange rate for the tax year. It prints to the console the exact
values to enter into Priloha c. 3 of the Czech income tax return (DPFDP7).

**Why this priority**: Dividends flowing into paragraph 8 (capital income) and Priloha c.
3 are the primary foreign income source currently calculated manually and error-prone. This
delivers the core value of the tool end-to-end with no dependencies on other stories.

**Independent Test**: User runs the tool with the four 2024 Morgan Stanley quarterly PDFs.
Console output shows: foreign income row 321 = 10,748 CZK, foreign tax paid row 323 =
1,612 CZK. These match the known-correct declared values from the sample declaration.

**Acceptance Scenarios**:

1. **Given** a set of quarterly broker PDFs for a complete tax year, **When** the user
   runs the tool from the command line, **Then** it correctly identifies all dividend
   payments, sums them by source country, converts to CZK at the CNB annual average rate,
   and prints the results to the console.

2. **Given** PDFs from both Morgan Stanley (RSU account) and Fidelity (ESPP account),
   **When** the tool processes them, **Then** it correctly extracts dividends from each
   broker, aggregates them into a single row 321 total, does not double-count, and
   prints a per-broker dividend breakdown so the user can verify each component.

3. **Given** a dividend that had US withholding tax deducted at source, **When** the tool
   processes the statement, **Then** it extracts the gross dividend amount AND withholding
   tax amount separately and maps them to row 321 and row 323 respectively.

4. **Given** reinvested dividends (dividend used to purchase additional shares), **When**
   the tool processes the statement, **Then** it still reports the gross dividend as
   taxable income, since reinvestment does not exempt it from Czech tax.

---

### User Story 2 - Self-Declare RSU and ESPP Income as Additional Paragraph 6 Rows (Priority: P1)

The employer's Potvrzeni o zdanitelnych prijmech ze zavisle cinnosti (MFin 5460) contains
only the base salary. RSU vesting income and ESPP discount income are not included. The
employee must calculate these amounts from broker statements and enter them as additional
rows in the paragraph 6 employer income table of the DPFDP7 form, alongside the base
salary row from the Potvrzeni.

The tool accepts the Potvrzeni PDF and broker PDFs as command-line arguments. It reads the
base salary from the Potvrzeni automatically, calculates from broker statements:
- RSU income: full FMV at each vesting date multiplied by shares vested, converted to CZK
- ESPP income: discount amount (FMV minus purchase price, times shares) per offering
  period, converted to CZK

It prints to the console the complete paragraph 6 breakdown ready to copy into the form:
base salary (from Potvrzeni) + RSU income + ESPP income = total row 31.

**Why this priority**: This is P1 — mandatory self-declaration. Without these amounts, the
declared paragraph 6 income is understated. Any Czech tax resident receiving RSU or ESPP
income from a foreign parent company MUST self-declare this income.

**Independent Test**: User runs the tool with the 2024 Potvrzeni PDF plus all Morgan
Stanley and Fidelity PDFs. Console shows base salary 2,246,694 CZK from Potvrzeni, RSU
income ~665,603 CZK, ESPP income ~19,199 CZK, and total paragraph 6 = 2,931,496 CZK,
matching the declared value in the sample declaration.

**Acceptance Scenarios**:

1. **Given** `--potvrzeni <path>` passed as a CLI argument, **When** the tool processes
   it, **Then** it extracts the base salary amount and employer tax ID (DIC) automatically.
   **Given** `--base-salary <CZK>` passed instead, **When** the tool runs, **Then** it
   uses that value directly and omits the employer tax ID from output.

2. **Given** Morgan Stanley quarterly statements, **When** the tool processes them,
   **Then** it identifies all Share Deposit transactions as RSU vesting events, calculates
   income as quantity multiplied by FMV at vesting date, converts to CZK, and prints the
   total as a separate additional paragraph 6 row attributed to the same employer.

3. **Given** Fidelity ESPP statements, **When** the tool processes them, **Then** it
   identifies each offering period purchase, calculates the discount (FMV minus purchase
   price, multiplied by shares), converts to CZK, and prints the total as a separate
   additional paragraph 6 row. Employee payroll contributions are NOT income.

4. **Given** all inputs processed, **When** the tool prints the paragraph 6 summary,
   **Then** it displays: base salary (source: Potvrzeni) + RSU income (source: Morgan
   Stanley) + ESPP income (source: Fidelity) = total row 31, with each line traceable
   to its source document.

5. **Given** a vesting event where shares were deposited at a specific price, **When** the
   tool processes the event, **Then** it uses the deposit price shown in the broker
   statement as the FMV at vesting date, not the quarter-end closing price.

---

### User Story 3 - Calculate Complete Priloha c. 3 Credit Computation (Priority: P2)

After extracting raw dividend and withholding data, the tool calculates all derived fields
of the foreign income credit computation (rows 324-330 of Priloha c. 3) when the user
provides their declared Czech tax base (rows 42 and 57 from the main DPFDP7 form) as
command-line arguments. The tool prints the complete Priloha c. 3 output with all values
and the formula behind each, ready to be copied into the declaration.

**Why this priority**: The coefficient and credit cap rows require Czech tax base values
not found in broker statements. Stories 1 and 2 function as a standalone MVP; Story 3
adds the full calculation chain once the user has their tax base.

**Independent Test**: User provides total foreign dividends ($461.69 USD), US withholding
($69.25 USD), CNB rate 23.28, Czech tax base 2,942,244 CZK, and raw tax 542,836.04 CZK
as CLI arguments. Console output shows rows 324-330 all matching the declared values.

**Acceptance Scenarios**:

1. **Given** extracted foreign income and withholding amounts plus Czech tax base inputs
   passed as CLI arguments, **When** the user runs the tool, **Then** it computes rows
   324-330 using the formulas from DPFDP7 and prints each value with its formula.

2. **Given** foreign tax paid exceeds the credit cap (row 325), **When** the tool
   computes the credit, **Then** it correctly limits the credit to the cap and shows the
   non-credited amount separately in rows 327 and 329.

---

### Edge Cases

- What happens when a Morgan Stanley quarterly PDF is missing for a full calendar year?
  The tool MUST warn the user that coverage is incomplete and flag which quarters (Q1–Q4)
  are absent based on the statement periods detected. This check does not apply to
  Fidelity, which provides a single year-end consolidated report.
- What happens when the CNB annual average rate for the tax year is not yet published?
  The tool MUST attempt auto-fetch first; if the rate is unavailable it MUST notify the
  user and instruct them to supply it via `--cnb-rate <value>`.
- What happens when the PDF is password-protected or unreadable? The tool MUST report the
  failure with a clear message identifying the specific file, not return zero values.
- What happens when a broker changes their PDF format? Because extraction is deterministic
  structured parsing, a format change will produce no pattern matches. The tool MUST
  detect this and report a specific, actionable error identifying the file and the
  unrecognized layout rather than silently returning zeros.
- What happens when dividends are paid in a currency other than USD? Non-USD dividends are
  out of scope. The tool MUST report a specific warning identifying the currency and the
  transaction, skip that dividend, and continue processing. Support for non-USD currencies
  is a future enhancement.
- How does the tool handle dividend reinvestment? It MUST use the gross dividend before
  reinvestment as the taxable amount, not the net amount after.
- What happens when an RSU vests in multiple tranches on the same date? The tool MUST sum
  all tranches for that date and report the combined income as one line item per date.
- What happens when the Potvrzeni cannot be parsed? The tool MUST exit with a specific
  error message instructing the user to re-run with `--base-salary <CZK>` instead.
- What happens when a positional PDF argument cannot be identified as either Morgan Stanley
  or Fidelity? The tool MUST report a specific error naming the unrecognized file and MUST
  NOT attempt to extract data from it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tool MUST require exactly one of two mutually exclusive base salary
  inputs: `--potvrzeni <path>` (PDF of the employer's Potvrzeni o zdanitelnych prijmech,
  MFin 5460) or `--base-salary <CZK>` (manually supplied integer value in CZK). When
  `--potvrzeni` is provided, the tool MUST extract the base salary amount and employer
  tax ID (DIC) automatically from the PDF. When `--base-salary` is provided, the tool
  MUST use that value directly. If neither or both are provided, the tool MUST exit with
  a clear usage error. The complete §6 summary is always computed and printed.

- **FR-002**: The tool MUST accept a required `--year <YYYY>` CLI flag specifying the tax
  year to process. Broker statement PDFs (Morgan Stanley quarterly statements and/or
  Fidelity year-end reports) are passed as one or more positional arguments after all
  named flags (e.g., `cz-tax-wizard --year 2024 --potvrzeni cert.pdf ms-q1.pdf fidelity.pdf`).
  The tool MUST auto-detect the broker type for each PDF from its content and MUST
  validate that all provided PDFs contain dates within the specified year, warning on
  any outliers.

- **FR-003**: The tool MUST extract data from broker PDFs using deterministic structured
  text parsing against the known Morgan Stanley and Fidelity PDF layouts. It MUST extract
  from each PDF: dividend payment dates, gross dividend amounts, US withholding tax
  amounts, and share transaction events (deposits and purchases with their prices and
  dates). AI-based extraction is out of scope for this feature.

- **FR-003a**: If a PDF's text content does not match the expected layout patterns for
  its broker type, the tool MUST report a specific error identifying the file and the
  unrecognized format, and MUST NOT silently return zero or partial values.

- **FR-004**: The tool MUST auto-detect broker identity for each positional PDF argument
  by searching the PDF text content for the broker name (e.g., "Morgan Stanley" or
  "Fidelity" in the document header or footer). Detection MUST use a fixed mapping:
  - **Morgan Stanley** → extract Share Deposit transactions as RSU vesting events
    (income = quantity × FMV at deposit price) and dividend events; both §6 and §8.
  - **Fidelity** → extract ESPP purchase events (income = discount amount only) and
    dividend events; both §6 and §8.
  Before extracting data from each file, the tool MUST print a confirmation line showing
  the detected broker, account number, and statement period
  (e.g., `[Morgan Stanley Q1 2024] ms-q1.pdf`). If neither broker name is found in the
  PDF text, the tool MUST report an unrecognized format error for that file.

- **FR-005**: The tool MUST aggregate all dividend events for the year from both Morgan
  Stanley and Fidelity in USD, convert the total to CZK using the CNB annual average
  exchange rate, and print a per-broker breakdown alongside the aggregate total for
  row 321. US withholding tax is similarly aggregated from both brokers for row 323.
  All USD → CZK conversions MUST use round-half-up to the nearest whole CZK.

- **FR-006**: The tool MUST print computed values mapped to their exact DPFDP7 Priloha
  c. 3 row numbers: row 321 (foreign income) and row 323 (foreign tax paid) as a minimum.

- **FR-007**: Given the user's Czech tax base values passed as CLI arguments (rows 42 and
  57), the tool MUST compute and print rows 324, 325, 326, 327, 328, and 330 of Priloha
  c. 3, each with its formula shown.

- **FR-008**: The tool MUST automatically fetch the CNB annual average exchange rate for
  the tax year from the CNB public website. If a `--cnb-rate` CLI flag is provided, it
  MUST use that value instead. In all cases it MUST print the rate used and its source
  (auto-fetched URL or user-supplied) so the user can verify it.

- **FR-008a**: If the CNB rate cannot be fetched (network unavailable or rate not yet
  published) and no `--cnb-rate` flag is provided, the tool MUST stop with a clear error
  message explaining how to supply the rate manually via `--cnb-rate`.

- **FR-009**: For RSU vesting events (Share Deposits in Morgan Stanley statements), the
  tool MUST calculate paragraph 6 income as quantity multiplied by the FMV at vesting
  date (the deposit price in the statement), converted to CZK using round-half-up, per
  vesting event.

- **FR-010**: For ESPP purchases (Fidelity statements), the tool MUST calculate paragraph
  6 income as the gain from purchase (FMV minus purchase price, multiplied by shares
  purchased) per offering period, converted to CZK. Employee payroll contributions are
  NOT income and MUST NOT be included.

- **FR-011**: The tool MUST print a complete paragraph 6 summary: base salary (from
  Potvrzeni) + RSU income (from Morgan Stanley) + ESPP income (from Fidelity) = total
  row 31, with each component traced to its source file.

- **FR-012**: If the Potvrzeni PDF cannot be parsed, the tool MUST exit with a specific
  error message instructing the user to supply the base salary manually via
  `--base-salary <CZK>` instead.

- **FR-013**: All PDF processing and data extraction MUST happen locally on the user's
  machine. No document content, personal data, or financial figures may be transmitted
  to any external service or API.

- **FR-014**: Every output section MUST include a disclaimer labeling the results as
  informational only and directing the user to verify with a qualified tax advisor.

- **FR-015**: The tool MUST warn the user if fewer than 4 distinct quarterly statement
  periods are detected across all provided Morgan Stanley PDFs for the specified tax year,
  since Morgan Stanley publishes quarterly statements and a missing quarter means incomplete
  dividend and RSU data. Fidelity provides a single year-end consolidated report and is
  exempt from this check.

- **FR-016**: The tool MUST print a per-event breakdown of RSU vesting income and a
  per-offering-period breakdown of ESPP income, so the user can trace each amount.
  Dividend output shows annual totals only (no per-quarter breakdown required).

### Key Entities

- **EmployerCertificate**: The Potvrzeni o zdanitelnych prijmech (MFin 5460) from the
  employer. Attributes: employer name, employer tax ID (DIC), tax year, base salary
  amount (CZK), tax withheld (CZK). Contains only employer-reported base salary — no
  stock compensation income.

- **BrokerStatement**: A single PDF from a broker. Attributes: broker name (Morgan Stanley
  or Fidelity), account number, statement period (start and end dates), source country,
  periodicity (quarterly for Morgan Stanley; annual for Fidelity).

- **DividendEvent**: A dividend payment extracted from a statement. Attributes: date,
  gross amount (USD), withholding tax amount (USD), whether the dividend was reinvested.

- **RSUVestingEvent**: A Share Deposit transaction from Morgan Stanley. Attributes: date,
  quantity vested, FMV at vesting date in USD (the deposit price shown in the statement).
  Income type: paragraph 6 self-declared.

- **ESPPPurchaseEvent**: An ESPP purchase from Fidelity. Attributes: offering period
  dates, purchase date, purchase price per share, FMV at purchase date, shares purchased,
  discount amount (taxable income). Income type: paragraph 6 self-declared.

- **ForeignIncomeReport**: The aggregated output for paragraph 8 and Priloha c. 3.
  Attributes: tax year, source country, CNB rate used, total gross dividends in USD and
  CZK, total US withholding in USD and CZK, all computed Priloha c. 3 row values with
  formula references.

- **StockIncomeReport**: The aggregated output of self-declared paragraph 6 stock income.
  Attributes: total RSU income in CZK (itemized by vesting event), total ESPP income in
  CZK (itemized by offering period), combined total to add to employer base salary.

- **TaxYearSummary**: The complete picture for one year. Combines EmployerCertificate
  base salary and StockIncomeReport into total paragraph 6 row 31, and links
  ForeignIncomeReport to Priloha c. 3 rows.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given a complete set of 2024 broker PDFs (Morgan Stanley + Fidelity), the
  tool produces row 321 as the combined dividend total from both brokers converted to CZK
  at the CNB annual average rate, and row 323 as the combined withholding from both
  brokers, each within ±1 CZK of the arithmetically correct value. Note: the sample 2024
  declaration filed by the user omitted Fidelity ESPP account dividends from §8; the
  tool's output will differ from that filing and represent the tax-accurate figure.

- **SC-002**: Given the 2024 Potvrzeni and broker PDFs, the tool prints a paragraph 6
  total (base + RSU + ESPP) that matches the declared row 31 value (2,931,496 CZK) within
  plus or minus 1 CZK.

- **SC-003**: A user with no prior knowledge of the Czech tax form can run the tool from
  the command line and obtain all values needed for both paragraph 6 additional rows and
  Priloha c. 3 in under 5 minutes.

- **SC-004**: The tool correctly classifies 100% of dividend, RSU, and ESPP events from
  both Morgan Stanley and Fidelity statement formats used in the verified test set.

- **SC-005**: Every printed value references its source (which file, which transaction,
  which formula) so the user can trace and verify each number independently.

- **SC-006**: The tool never silently produces a zero or blank result — if extraction
  fails for any input, it prints a specific and actionable error message to stderr.

- **SC-007**: A full run processing up to 5 PDFs (4 quarterly broker statements plus
  Potvrzeni) completes in under 30 seconds on a standard laptop.

## Assumptions

- The tax year in scope is a full calendar year (1 January to 31 December), consistent
  with the Czech DPFDP7 form structure.
- The employer provides a Potvrzeni o zdanitelnych prijmech (MFin 5460) covering only
  the base salary. RSU and ESPP income are entirely absent from this certificate and must
  be self-declared by the employee as additional paragraph 6 rows.
- The source country of income is the United States (US) and the applicable
  double-taxation treaty method is the credit method (metoda zapoctu), as demonstrated
  in the sample 2024 declaration. All dividend and stock income is denominated in USD;
  non-USD currency income is out of scope and will be skipped with a warning.
- The CNB annual average exchange rate is the correct rate to use for conversion, based
  on confirmation from the sample declaration's declared values. Per-dividend-date rates
  are a future enhancement.
- No shares were sold during the tax year; capital gains from share disposals (paragraph
  10) are out of scope for this feature.
- The tool is a CLI application. All processing runs locally on the user's machine and no
  data is transmitted externally.
- Broker statement PDF formats are the standard Morgan Stanley quarterly format and the
  Fidelity year-end investment report format, as observed in the verified sample PDFs.
  Data extraction uses deterministic structured text parsing against these known layouts;
  AI-based extraction is explicitly out of scope and deferred as a future enhancement.
- Broker identity is determined by the broker name found in PDF text content. The income
  type mapping is fixed: Morgan Stanley → RSU vesting income + dividends; Fidelity →
  ESPP purchase income + dividends. This mapping is not user-configurable in this feature.
- ESPP shares are under a Section 423 Qualified plan with a 10% discount off the FMV at
  end of offering period, as confirmed by the sample statements.
- The FMV at RSU vesting date is the per-share deposit price shown in the Morgan Stanley
  statement, not the quarter-end closing price shown in the summary.
