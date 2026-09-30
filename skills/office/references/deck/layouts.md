# Presentation Layouts

Use these as authoring patterns for `slides.html`. They are not templates to copy wholesale; choose the structure that fits each slide and write concise CSS classes in the deck style block.

Use explicit HTML containers inside each `<section class="slide">`. Avoid default title-plus-bullets as the main layout.

Every layout needs a content reason. Choose it because it helps the audience compare, decide, understand a workflow, or trust a recommendation. Do not use cards or matrices as decoration for thin copy.

Common page skeleton:

- `.frame`: full slide inner layout
- `.eyebrow`: small section label or slide role
- `.takeaway`: one-sentence conclusion band
- `.body`: structured content area

## Thesis

Use for the title slide or a slide with one strong claim.

- One headline claim
- One short supporting line
- Two or three proof points
- HTML shape: `.frame.thesis`, large claim, short subtitle, compact proof row

## Cards

Use for peer items such as capabilities, strengths, risks, features, or recommendations.

- Three or four cards in a grid
- Each card has a short label and one compact sentence
- Avoid long bullet lists inside cards
- HTML shape: `.cards` containing `.card` blocks with label, headline, and one explanation

## Comparison

Use for pros versus cons, before versus after, or option A versus option B.

- Two balanced columns
- Same row structure on both sides
- End with one takeaway line
- HTML shape: `.comparison` with two `.panel` children and matched row structure

## Matrix

Use for decisions, tradeoffs, priorities, or evaluation.

- Rows are criteria
- Columns are options, scores, or implications
- Keep cells short enough to scan
- HTML shape: `.matrix` using CSS grid; highlight only the selected/recommended column or row

## Timeline

Use for process, sequence, rollout, or phases.

- Three to five steps
- Each step has a phase label and an outcome
- Avoid detailed paragraphs
- HTML shape: `.timeline` with `.step` blocks and thin connector lines

## Evidence Stack

Use for analytical reasoning.

- Observation
- Interpretation
- Implication
- Optional confidence or caveat
- HTML shape: `.evidence-stack` with three stacked bands and one final implication

## Recommendation

Use for the final slide.

- Decision or verdict
- Two or three reasons
- Next action
- HTML shape: `.recommendation` with verdict, rationale cards, and next-step footer

## Worked Example

Use when the deck needs to prove that a workflow, tool, or concept is real.

- Input or starting state
- Action or transformation
- Output or decision
- One limitation or guardrail
- HTML shape: `.worked-example` with before/action/after panels and a short caveat

## Decision Narrative

Use when the deck must persuade rather than describe.

- Situation or constraint
- Two or three options
- Evaluation criteria
- Recommended option
- Next action
- HTML shape: `.decision-narrative` with a compact criteria matrix and a recommendation footer

## Consulting Page

Use for analytical decks that need to feel sharper than a normal report.

- Thin top rule
- Assertion title, not topic title
- One-sentence takeaway band
- Three structured cards, a matrix, or a two-column argument area
- Quiet footer with slide number or source when useful
- HTML shape: `.frame.consulting`, `.top-rule`, `.eyebrow`, `.takeaway`, `.content-grid`

## CSS Hints

Define only the classes the deck actually uses. Useful names:

- `.cards`
- `.card`
- `.comparison`
- `.matrix`
- `.timeline`
- `.evidence-stack`
- `.takeaway`
- `.frame`
- `.eyebrow`
- `.top-rule`
- `.panel`
- `.content-grid`
- `.recommendation`

Keep the visual language minimal: black-and-white first, restrained lines, enough whitespace, and no decorative gradients.

If a slide feels generic, change the content structure before changing the styling. Add a concrete example, scenario number, contrast, caveat, or decision criterion.
