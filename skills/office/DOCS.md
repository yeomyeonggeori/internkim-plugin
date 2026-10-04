# Source-bound generation

This page describes how the `office` skill makes a document whose facts come only from where they may come from: the request, its attachments, the runtime, and arithmetic over those. It is the design behind `merge <schema>` and the workbook declaration, the evidence for it, and the plan for the paths that do not use it yet.

## The problem

A run of 24 business-document requests on the default host model (`z-ai/glm-5.3-flash`) produced documents that read well and were wrong in ways nobody asked for:

| Kind of defect | Example from the run |
| --- | --- |
| A value the runtime knows, typed by the model | minutes signed by an author who does not exist, a letter dated a day the model chose |
| Content the request did not give | report achievements, contract clauses, a paragraph in a filled form |
| Arithmetic written by hand | `E19=(F12-F5)/F5` under a "Q4" header that compared annual totals |
| Missing data shown as data | a quarter that was not reported, shown as 0; an empty "annual" column |
| Presentation left to chance | no number formats in a workbook |

Each was possible because the model wrote the whole document: the layout, the values it was given, the values it could have been told, and the values it should have computed. A check after the fact catches some of this and teaches the model to route around the check. The design removes the opportunity instead.

## One schema format

Every document the skill generates from a request is drawn from a schema. A schema is a JSON file that names four things:

- **given** fields, the only values the model writes, each typed (`text`, `person`, `organization`, `date`, `amount`, `quantity`, `percent`, `boolean`, or a list of records);
- **known** fields, which the runtime fills (`requester`, `today`, `document.number`, `company.<field>`);
- **derived** fields, expressions over the others (`money(items.quantity * items.unitPrice)`, `sum(items.amount)`, `words(grandTotal)`);
- the **layout**, which places fields by name (`{recipient}`, `{validDays:number}`) and is never written by the model.

The bundled schemas are `kr/quote`, `intl/invoice`, `kr/meeting-minutes`, `report` and `letter`, under `assets/schemas/`. A company's own form becomes a schema too: `office convert form.docx form.schema.json` reads each empty cell beside or under a label as a field and each table of empty numbered rows as a list. A person then types each field once (`known`, `expression`, `handwritten` or `ignore` where it is not a given value), and the same file fills that form every time.

The model's whole job on this path is one JSON object of given values:

```
office guide kr/quote                 # prints the given fields as JSON Schema
office merge kr/quote quote.values.json quote.pdf
```

`merge` validates the values against the schema, resolves the known fields, computes the derived ones, draws the layout and writes the file. A field the request does not state is `null`; the result's `details.blanks` lists every blank, so the reply can name them and offer to complete the same file.

### A file the command validates

`office guide <schema>` prints the given fields and `merge` validates them; nothing is added to the host's tool schemas. A forced `response_format` was tried against the same requests. On one upstream provider the constrained decoder produced a quotation with fourteen items the request never named, and on another it returned field names the schema does not have (`price`, `amount`) despite `strict`. OpenRouter routes one model to several providers, and each enforces a strict schema its own way or ignores it. A validation in our own command is the same everywhere, and its error names the field path and what it takes, which the model fixes in one step.

The JSON Schema `guide` prints keeps to the portable subset in internkim's AGENTS.md: string enums only, no `$ref`, no `const`, and depth bounded by the schema. A given field is required and nullable unless the schema marks it optional, so the model decides each one; an optional field is one a document can leave out entirely, such as a contact person.

### Typed values

| Type | The model writes | The layout draws |
| --- | --- | --- |
| `date` | `2026-10-16`, `2026-10-16 14:00`, `14:00`, `2026-10`, or `start/end` | the date as the document's language writes it |
| `amount` | a plain number, `1350000` | grouped digits with the field's currency, right-aligned in tables |
| `quantity` | a plain number | grouped digits with the unit |
| `percent` | the number shown, `18` for 18% | `18%` |
| `person`, `organization`, `text` | the request's words | as written |
| `boolean` | `true`, `false` or `null` | what the layout makes of it, such as the tax-free marker on a quotation row |

Typing lets the renderer own formatting. It is also a shape check on exact text: `2026-09-30 14:02 KST` is refused as a date with a message naming the accepted forms. That is a format rule and makes no judgment about meaning.

### Known values: one binding

Every known value reaches `office` through one file, the runtime context, which the environment variable `OFFICE_RUNTIME_CONTEXT` names. The host writes it for the task. The model never writes it and never passes a value or a path from it.

```json
{
  "requester": {"name": "이샘플", "email": "sample@example.com"},
  "today": "2026-10-04",
  "company": {"ko": "<task temp>/company-profile.json", "en": "<task temp>/company-profile.en.json"},
  "registeredDocuments": [{"documentNumber": "SAMPLE-20261004-001"}]
}
```

| Field | Source |
| --- | --- |
| `requester` | the task's requester |
| `today` | the company's date for the task |
| `company.<field>` | the `company-profile.json` that `company_info_get` writes into the task directory, with the kept seal and logo beside it |
| `document.number` | the last entry `company_document_register` appended to `registeredDocuments` |

On a later `merge` to the same output, the known values come from the snapshot `merge` wrote beside the file (`<output>.source.json`). Completing a blank therefore keeps the document's number, date and letterhead even after the profile changes, and a value that was blank in the snapshot is resolved again.

The catalog forms that still have a Markdown spec read the same binding: `merge` prints their letterhead, seal and logo from the profile the runtime context names for the form's language, and their values have no company field. A form with no recorded profile prints its letterhead as blanks and lists them.

### Expressions

One small expression language serves schema `derived` fields and workbook views, parsed in `scripts/schemas/expression.py`:

| Group | Functions |
| --- | --- |
| row | `floor`, `round`, `if`, `money`, `words`, `addDays`, `+ - * /`, parentheses |
| list | `sum`, `count` over a list field such as `items.amount` |
| view | `change`, `percentChange`, `share` over a dimension |

`money` rounds the way the schema's jurisdiction rounds, and `words` writes the jurisdiction's amount in words. A `null` stays `null` through every function, so a missing price leaves its line, the total and the amount in words blank. A schema must not turn a missing input into a number: the evaluation caught `intl/invoice` computing tax as `if(taxRatePercent, …, 0)`, which printed "Tax 0" on every invoice whose request named no rate. The rate is now a required given field, and an unstated rate leaves tax and total blank.

## Reports and letters

`report` and `letter` are schemas whose given fields are sections of typed blocks: `paragraph`, `items`, `table`, `fields` and `chart`. An item carries its own typed `date`, `owner`, `due`, `quantity`, `amount`, `percent` and `status`. A table declares typed columns and can add a total row, and a chart names labels and series. Author and date are known fields, so the model has nowhere to type them.

A paragraph is still free prose. It is the one place on this path where a fact the request does not state can still enter a document, as the failure modes below record.

## Workbooks

A new workbook is declared, never hand-written. The model writes `<title>.workbook.json`:

```json
{
  "kind": "workbook",
  "tables": [{"name": "Data", "columns": [
      {"name": "Year"}, {"name": "Quarter"}, {"name": "Region"},
      {"name": "Revenue", "type": "amount", "unit": "백만원"}],
    "rows": [[2025, "1분기", "수도권", 820], [2026, "3분기", "호남", null]]}],
  "views": [{"sheet": "Summary", "title": "By quarter", "rows": ["Quarter"], "columns": "Year",
             "measure": "Revenue", "totals": true,
             "add": [{"name": "YoY", "expression": "percentChange(Revenue, Year)"}]}],
  "charts": [{"view": "By quarter", "type": "line"}]
}
```

`office create book.xlsx book.workbook.json` compiles it. The compiler:

- writes every view cell as a live `SUMIFS` over the source table, keyed by the row's and the column's members, so a cell can only sum the rows of its own coordinate;
- leaves a cell blank when no source row it covers has a value, so a quarter that was not reported is never 0;
- writes a sum that misses some of its rows as the sum of the values given, marks it `*` through its number format, and writes a note under the view naming each missing input;
- writes `percentChange` and `change` only between cells that are complete and cover the same number of source rows, and an arithmetic column such as a variance only between measures that cover the same records, which is what makes the annual-total-under-a-quarter-header formula impossible;
- divides `share` by the view's own total, and marks the share `*` when either side is partial;
- adds total rows and, for members that add up, a total column;
- takes number formats from each column's type and unit, and from each computed column's type;
- puts one merged group header over a computed column added for several members, with the members as its sub-headers, and wraps a header at its spaces instead of widening the column the views above share;
- starts every chart on a page of its own, so no printed page cuts one;
- draws charts over the member cells, with missing and partial values as gaps, and labels a view with two row dimensions by both members;
- returns `details.blanks` (each `null` input cell, named by its dimensions) and `details.views` (each view as it displays), so the model checks the result without reading the file back.

The model never writes a formula or a cell reference here. Changing a workbook the person already has keeps the `read` then `apply` path in `references/sheet.md`.

## What the model still decides

- which schema fits the request, and which output format;
- every given value, copied from the request or the attachment, or `null`;
- for a report or letter, the sections, the block kinds and the wording of paragraphs and item text;
- for a workbook, the tables' columns and roles, the views, the computed columns and the charts;
- what the reply says about blanks and what it asks the person.

Deterministic code supplies what the model cannot know (the requester, the date, the company, the number) and what it should not compute by hand (totals, tax, words, formulas, formats).

## The proposed direction and where it changed

The proposal was a typed fact sheet with a verbatim quote per fact, references from the document to fact ids, refusal of bare literals in prose, a workbook declaration, typed values, and removing `--forbidden-text`. The workbook declaration, typed values and injected known facts are built as proposed. The rest changed, for the reasons below.

**Quotes verify the wrong step.** A probe asked the model for a fact sheet on five requests, three times each, with this contract: `{"facts": [{"id", "kind", "value", "source", "quote"}], "missing": [...]}`, every quote checked as an exact substring of the request or the attachment text. The model quoted exactly: 1 quote in 219 failed the check, and that one quoted the system prompt. Invention in the 24-sample run did not happen while listing facts. It happened while writing the document, and a quote proves a fact was copied without saying anything about what the document then adds around it.

**The fact sheet asks the model what the document needs.** Each sheet also listed what was missing: 49 items across the fifteen sheets. Most were not needed or were known to the runtime (the author, the issue date, the company's bank account, a total it could compute, the revenue impact of an outage), and the needed load-test owner and meeting place were missed in three sheets. Asking the person about that list would ask useless questions and skip a real one. The same requests filled against schemas named the needed blanks in every valid run and nothing else, because the schema says what the document holds. The fact sheet did get one thing right that the schemas missed: it flagged an invoice's unstated tax treatment, which led to the `intl/invoice` fix above.

**References are field names.** A schema field is the reference: the layout says `{validDays:number}` and the renderer formats the value by its type. A separate fact-id layer adds a step and tokens without a constraint the schema does not already enforce.

**Literal refusal is not built.** Refusing a bare number or date in prose would push the model to spell numbers out or move them into an item's text. The fields that carry facts are already typed. A pattern over prose is the kind of filter AGENTS.md rules out, and decision 2 below closes the paragraph hole with a claim check instead.

**`--forbidden-text` goes when the generic paths go.** Nothing on the schema or declaration path uses it. `references/doc.md` still asks for it on the free-Markdown path, and it is deleted together with that step.

## Failure modes

| Situation | What happens |
| --- | --- |
| The request lacks a value the schema needs | the field is `null`, drawn as a blank line or an empty cell, listed in `details.blanks`; the reply names it and offers to complete the same file |
| The person sends the value later | the values file gets that field and the same `merge` or `create` runs to the same output; number and date are kept from the snapshot |
| A given value has the wrong shape | `merge` fails before writing, naming the field path and what it accepts; an unknown field name lists the fields there are |
| The runtime does not know a known value | the field is blank and listed as `<field> (<provider>)`, never filled by the model |
| No schema fits the request | the free-Markdown path in `references/doc.md` stays, with its checks, until a schema covers the case |
| A paragraph states something the request does not | still possible; the schema guidance pairs "write it from the request" with "never add", which is a prompt and does not prevent it |
| The model writes its own script instead of the declaration | possible today through `office python`; the evaluation measured it and the rollout closes it |
| The model asks for a value a known or derived field covers | cannot happen through the command: those fields are not in the guide's JSON Schema |

## Evaluation

Eleven requests written for this evaluation, independent of the 24 samples: three documents (a Korean weekly report, an English postmortem from an attached log, a Korean office-move notice with an undecided phone number), five forms (Korean minutes and a Korean quotation, each with and without a named file format, and an English invoice from an attached timesheet with a missing PO number), and three workbooks (Korean regional sales with an unreported quarter, an English budget-versus-actual CSV with a missing month, English channel orders with a missing cell). Each ran at least three times per arm on `z-ai/glm-5.3-flash` through the bluecollar harness, with the skill as the only difference: **baseline** is `main` at #63, **prototype** is this branch. Workbooks W1 and W2 got runs 4 and 5 in both arms after host and provider failures left them thin. A third arm, **routed**, is the prototype with one sentence of `SKILL.md` changed, described below.

Counting was done by hand by one grader who could see the arm, which is the main weakness of these numbers. An invented fact is a claim in the delivered file about an event, condition, value, person, date or obligation that the request, its attachment, the runtime context and arithmetic over those do not support. Courtesy formulas, headings, and saying that an undecided value will be announced do not count. A wrong computation is a figure that differs from what the sources give, or that compares or totals values of different coverage without marking it. The pull request that introduced this page carries each graded run's one-line note, the requests and the harness.

| Case | Arm | Files delivered | Invented facts | Wrong computations | Failed `office` calls / all | Median s to first delivery | Median model tokens to first delivery |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D1 weekly report (ko) | baseline | 3/3 | 1 | | 5 / 33 | 264 | 344k |
| | prototype | 3/3 | 0 | | 0 / 14 | 75 | 62k |
| D2 postmortem from a log (en) | baseline | 3/3 | 3 | | 0 / 6 | 92 | 66k |
| | prototype | 3/3 | 0 | | 0 / 15 | 91 | 99k |
| D3 office-move notice (ko) | baseline | 3/3 | 7 | | 1 / 12 | 101 | 93k |
| | prototype | 3/3 | 1 | | 1 / 11 | 165 | 113k |
| P1F minutes as PDF (ko) | baseline | 3/3 | 2 | | 1 / 22 | 197 | 173k |
| | prototype | 3/3 | 0 | | 2 / 18 | 231 | 149k |
| P2F quotation as PDF (ko) | baseline | 2/3 | 0 | | 1 / 12 | 111 | 135k |
| | prototype | 3/3 | 0 | | 2 / 14 | 108 | 77k |
| P3 invoice from a timesheet (en) | baseline | 2/3 | 0 | | 1 / 11 | 130 | 172k |
| | prototype | 3/3 | 0 | | 2 / 18 | 87 | 98k |
| W1 regional sales (ko) | baseline | 1/5 | 0 | 3 | 4 / 28 | 366 | 646k |
| | prototype | 4/5 | 0 | 4 | 2 / 16 | 255 | 214k |
| | routed | 3/3 | 0 | 0 | 4 / 26 | 306 | 383k |
| W2 budget vs actual CSV (en) | baseline | 5/5 | 0 | 14 | 13 / 53 | 158 | 319k |
| | prototype | 2/5 | 0 | 0 | 1 / 11 | 48 | 87k |
| W3 channel orders (en) | baseline | 3/3 | 0 | 4 | 4 / 20 | 193 | 224k |
| | prototype | 3/3 | 0 | 0 | 2 / 18 | 59 | 62k |
| **All but routed** | **baseline** | **25/31** | **13** | **21** | **30 / 197** | **158** | **173k** |
| | **prototype** | **27/31** | **1** | **4** | **12 / 135** | **108** | **100k** |

Requests with no file format named (P1 minutes, P2 quotation) never reached the skill in either arm: the host's intake classified them as replies and answered in chat Markdown, or withheld the write tools. They measure host intake and are reported apart.

Runs without a file, and why:

| Cause | Baseline | Prototype |
| --- | --- | --- |
| Time limit while building a workbook by hand, through model calls of one to three minutes | W1 runs 1, 4, 5 | |
| One provider call hung for seven minutes before any tool ran | W1 run 3 | W1 run 3 |
| After one `file_read` of a guessed relative path returned not-found, the host exposed only `file_read` until it stalled | | W2 runs 1, 3, 5 |
| The host narrowed the tools to `company_document_register` for eleven steps | P3 run 2 | |
| The model ended with a progress sentence before registering the quotation | P2F run 2 | |

The first row is the cost of building a workbook by hand, the last is the model, and the three between are host or provider behaviour. The `file_read` narrowing hit only the prototype here, but nothing in the skill causes it: both arms name their references by skill-relative path.

### What the numbers say

- **Invented facts nearly disappeared from documents and forms.** Every invented fact in the baseline sat in content the model composed: a discussion line in minutes, a report date it chose, instructions and reasons in a notice, purposes added to action items. On the schema path the author, dates and company are known fields, and an item has only the typed slots the request can fill. The one remaining invention is a sentence in a letter paragraph telling recipients where to send documents, the hole named under failure modes.
- **Every wrong computation in the prototype came from a run that bypassed the declaration.** In two of the five W1 prototype runs the model wrote its own openpyxl script and ran it through `office python`; both reproduced the baseline's defects (an annual change between unequal periods, a quarterly change computed without one region). Every run that declared its workbook (2 W1 prototype, 3 W1 routed, 2 W2, 3 W3) had none: missing inputs stayed blank, partial sums were marked, and no comparison crossed unequal coverage.
- **One sentence closed the bypass in this sample.** The routed arm scopes `office python` to work no verb covers and says a new document, form or workbook comes only from `merge` or `create`; its three W1 runs all declared. Prototype runs 4 and 5 also declared without that sentence, so the sample is small: two bypasses in four delivered runs against none in three. The sentence is now in this branch's `SKILL.md`, and decision 1 below is the deterministic close.
- **The model fixed a refused value in one step.** Each `merge` or `create` refusal named the field path and was followed by a valid call, which is why the prototype has fewer failed calls.
- **The evaluation found five defects in the prototype**, three fixed after it with a test each: the invoice's unstated tax rate printed as 0, a year declared as a quantity printed as `2,025`, and a unit repeated in its own header (`units (units)`). Two remain: the model can `apply` over a compiled workbook's cells (it wrote `집계 전` into a blank input), and a letter table cell typed as text keeps ISO dates.

## Cost

The schema path replaces the model's longest output (a whole document in Markdown, or a hand-built workbook with formulas) with a short JSON object, and adds one `guide` call before it. In isolation a given-values object took a median 7.0 s and 1,098 completion tokens; a fact sheet took 8.4 s and 1,749 tokens before any document was written, so it would have been an extra step on top of writing. In the agent loop, documents and forms reached their first delivered file in the same median time in both arms, 112 s, on 100k model tokens for the prototype against 167k. Workbooks are where time moved: a median 104 s and 124k tokens against 193 s and 319k, and the baseline lost three of five W1 runs to the five-minute budget of a low-level task while building by hand.

## Migration

| Path today | Becomes | What is deleted |
| --- | --- | --- |
| `merge <jurisdiction>/<form>` with content JSON per spec (`references/paperwork/*/*.md`) | a schema per form; the three bundled schemas are the pattern | each form's Markdown spec once its schema exists, `paperwork/template_context.py` field mapping, the hand-written company and number fields in content JSON |
| `create <title>.docx <title>.md` for reports, memos, letters | `merge report` / `merge letter` | the free-Markdown step for those kinds; `--required-text` and `--forbidden-text` in `references/doc.md` |
| `create <title>.xlsx <data>.csv`, then `apply` formulas | `create <title>.xlsx <title>.workbook.json` | formula writing in `references/sheet.md` for new workbooks |
| a company's own .docx or .xlsx form filled with `merge` placeholders | `convert form.docx form.schema.json` once, then `merge form.schema.json` | nothing until the placeholder path has no users |
| deck `slides.html` | unchanged in this step | nothing yet |

Editing a person's existing file (`read` then `apply`) does not change. In this prototype the legacy specs for `kr/quote`, `intl/invoice` and `kr/meeting-minutes` still exist but are unreachable, because a bundled schema's name takes precedence in `merge`; the rollout deletes them.

## Rollout order

Roll out, in this order. Each step ships on its own and deletes what it replaces.

1. **New workbooks through the declaration only.** Keep the routing sentence, delete formula writing for new workbooks from `references/sheet.md`, and make `apply` refuse to overwrite a compiled view or a declared input of a workbook built from a declaration, naming the declaration to change instead. The snapshot beside the file says which ranges were compiled, so the guard reads an identifier and judges nothing.
2. **The runtime context, written by the host.** Blueclaw writes `OFFICE_RUNTIME_CONTEXT` for each task: requester, the company's date, the paths `company_info_get` writes, and each registered document. #64's letterhead, seal and logo drawing lands on that binding in place of a company path in the values. Without the host writing this file, a schema prints its known fields as blanks, so no form moves before this step.
3. **Catalog forms, one schema each.** Minutes, quotation and invoice first (bundled here), then transaction statement, purchase order, weekly report, business trip report, approval and expense requests, then certificates, then contracts on top of #62's typed terms. Each schema deletes its `references/paperwork/*/<form>.md` spec and its content-JSON mapping.
4. **Reports, memos and letters through `report` and `letter`.** This deletes the free-Markdown step for those kinds, with `--required-text` and `--forbidden-text`.
5. **Decks last**, after deciding whether slide charts draw from typed series the way workbook views do.

Two host defects found here are worth fixing alongside step 2: the palette narrowed to `file_read` after one not-found, and requests with no named format being answered in chat without the skill.

## Decisions

1. **The host delivers a new office file only with its snapshot.** `file_deliver` refuses a `.docx`, `.xlsx`, `.pptx` or `.pdf` the task wrote when `<file>.source.json` is missing, and says to make it with `merge` or `create`. A file the person attached, or one older than the task, is delivered as it is. The check reads an identifier and the file's age, never its content.
2. **A letter keeps one free paragraph slot.** A courtesy or human-touch line written by the model is allowed, because occasional warmth is wanted. A separate claim check classifies each model-written unit as source, derived, courtesy or claim, and blanks only the claims; the schema does not fix courtesy text in the layout.
3. **The compiler labels unequal coverage.** When a member a view lays out covers fewer members of another dimension than its siblings, a note under the view names it, such as "Unequal coverage: 2026 (3 of 4 Quarter)". That holds for a dimension a change compares across and for one the view sums away, so a year of three quarters is never totaled beside a year of four without the mark.
4. **A jurisdiction's default tax stays.** `kr/quote` charges 10% VAT on each row the request does not mark exempt, as Korean quotations do. `intl/invoice` requires a stated rate and leaves tax and total blank without one.
5. **An attached table is read through `csvPath`.** While the runtime context lists an attached CSV or TSV, a declaration that types its rows is refused and names `csvPath`.
