# Presentation Visual Styles

Use this before writing `slides.html` when the user cares about deck quality, executive polish, board/investor communication, or when an early contact sheet feels generic.

The point is not to constrain creativity. The point is to force a real visual identity decision before HTML authoring, then let the model invent within that identity.

## Visual Identity Gate

Before writing HTML, choose one named style and record it in `deck-brief.md` and `DESIGN.md`.

`DESIGN.md` should include:

- `## Style Prompt`: one paragraph naming the style, audience, visual tradition, and recurring primitive.
- `## Visual Identity Gate`: the concrete type, color, spacing, primitive, and anti-pattern decisions that make the deck recognizable.
- `## Anti-default Check`: what would make the deck look like a generic AI card grid, and what the deck does instead.

`slides.html` should include:

- `data-visual-system="<style-name>"` on `<body>` or each slide.
- `data-slide-role="<job>"` on every `<section class="slide">`.
- One recurring primitive class that is not just `.card`, such as `.decision-rail`, `.variance-band`, `.risk-ledger`, `.evidence-wall`, `.launch-gate`, or `.journey-map`.

If you are reaching for default colors, generic cards, or a decorative sidebar before you can name the visual system, pause and pick a stronger style.

## Style Library

### Swiss Board

Best for executive decisions, quarterly reviews, board updates, and investor memos.

- Type: large claim titles, compact labels, strict alignment, confident whitespace.
- Color: off-white surface, ink, one sharp accent, muted grid lines.
- Primitive: decision rail, variance band, status chip, owner-date chip.
- Avoid: colored side stripes, soft shadow cards, equal-weight card grids.

### Operating Memo

Best for sober strategic reports and internal recommendations.

- Type: restrained but assertive; title makes the conclusion.
- Color: paper, ink, gray rules, one signal color.
- Primitive: implication band, proof table converted into a decision matrix, right-side recommendation ledger.
- Avoid: decorative hero layouts, oversized labels, repeated KPI tiles.

### Evidence Atlas

Best for research, synthesis, market scans, and recommendation decks.

- Type: evidence labels stay small but readable; interpretation is visually louder than raw facts.
- Color: light field, dark ink, source-confidence accents.
- Primitive: evidence wall, confidence tag, interpretation band, implication footer.
- Avoid: many equal evidence cards with no hierarchy.

### Launch Console

Best for launches, product rollouts, roadmap gates, and cross-functional plans.

- Type: dense operational labels with clear phase names.
- Color: neutral cockpit surface with green/amber/red status only where it carries meaning.
- Primitive: launch gate, readiness lane, blocker tag, next-checkpoint chip.
- Avoid: dark sci-fi dashboards, glowing panels, unlabeled progress bars.

### Risk Ledger

Best for risks, incidents, compliance, and board escalation.

- Type: severity and owner are fast to scan; evidence remains factual.
- Color: quiet base with severity accents, not alarmist color flooding.
- Primitive: risk ledger, escalation lane, trigger marker, response owner.
- Avoid: dramatic warning gradients, vague risk cards.

### Field Signal

Best for customer deployments, hardware/software operations, site reports, and pilots.

- Type: grounded labels, observed signal, operational implication.
- Color: clean industrial neutrals with one field accent.
- Primitive: site strip, signal band, action marker, constraint chip.
- Avoid: stock-photo polish and abstract SaaS cards.

## Anti-Patterns The Review Should Catch

- Topic titles such as `Overview`, `Summary`, `Roadmap`, or `Risks` without a claim.
- A deck dominated by repeated `.grid` plus `.card` sections.
- White rounded cards with both a border and a large soft shadow; in review language, bordered cards with soft shadows.
- Colored side stripes used as the main identity.
- Tiny left rails, label stacks, or status chips that cannot be read in a 4-up contact sheet.
- Raw tables or bare lists presented as finished slides.
- A slide with no declared `data-slide-role`.
- A deck with no named `data-visual-system`.

## Revision Moves

- Replace repeated card grids with a rail, matrix, variance scoreboard, risk ledger, evidence wall, launch gate, or journey map.
- Make the title a conclusion, then make the proof object support that conclusion.
- Remove decorative rails unless they carry status, owner, date, decision, or source meaning.
- If a contact sheet looks weak, change the composition first. Color and font tweaks come after structure.
