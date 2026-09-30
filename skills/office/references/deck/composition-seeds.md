# Presentation Composition Seeds

Use these when a deck feels sparse, generic, or too close to title-plus-bullets. They are not templates. Borrow the structure that clarifies the user's facts, then change the visual metaphor, density, labels, and rhythm to fit the deck.

## Creative Guardrails

- Pick one visual system for the deck: board cockpit, operating memo, product map, research wall, launch control, field report, or another metaphor that fits the subject.
- Repeat three to five useful primitives across slides: metric tile, variance bar, decision rail, evidence strip, owner-date chip, dependency tag, status badge, or source footnote.
- Make density meaningful. Add structure only when it improves comparison, decision-making, or trust.
- Preserve exact source facts before styling. Visual invention must not replace required names, dates, owners, targets, actuals, missing values, or caveats.
- Keep slides scan-first: assertion title, visible proof, implication or ask.

## Board Cockpit

Good for executive reviews, quarterly updates, and investor-style decisions.

- Cover: left side assertion and approval ask; right side compact decision stack with target, actual, variance, and status chips.
- Dashboard: top row of status tiles; lower row of decision-required panels with owner, deadline, and impact.
- Metrics: KPI cards connected by variance bars; include one missing-data strip if any value is unavailable.
- Roadmap: horizontal rail with milestone cards, owner-date chips, dependency tags, and unlocked decision.
- Risks: two-by-two risk matrix or stacked risk cards; each item keeps risk, evidence, response, owner, and trigger.

## Operating Memo

Good when the deck needs to feel analytical without becoming rigid.

- Each slide starts with a claim title and one-sentence implication band.
- Use one large proof surface per slide: matrix, comparison grid, timeline, or evidence stack.
- Keep a narrow right rail for recommendation, owner, date, or open decision.
- Use quiet separators, strong alignment, and compact labels instead of decorative effects.

## Risk Room

Good for board reviews, incident retrospectives, compliance updates, and operational planning.

- Make the main slide object a risk wall: each risk has severity, evidence, response, owner, and trigger.
- Use escalation lanes instead of repeated cards: watch, active mitigation, decision needed.
- Pair missing data with a visible gap marker and next owner instead of hiding it in a note.
- Avoid dramatic color alarms unless the decision truly needs urgency.

## Timeline Rail

Good for roadmaps, launches, hiring plans, release trains, and operational milestones.

- Use a strong horizontal or vertical rail as the recurring structure.
- Attach owner-date chips, dependency tags, and status badges directly to each milestone.
- Show what each milestone unlocks; a date without consequence is only a calendar.
- Keep the rail visually stable while varying slide-specific proof panels.

## Evidence Wall

Good for research synthesis, investor updates, market scans, and recommendation decks.

- Cluster evidence into groups with confidence, source, or freshness labels.
- Pair each proof item with interpretation and implication.
- Let one slide feel like a curated wall of evidence, then follow with a clean recommendation.
- Avoid equal-weight evidence cards when one finding should clearly lead the story.

## Product Map

Good for launches, feature proposals, capability decks, and product strategy.

- Show the user journey or workflow as the main structure.
- Attach metrics, constraints, or risks to the relevant stage instead of placing them in a separate bullet list.
- Use before-action-after panels for worked examples.
- Close with a decision panel that names what changes after approval.

## Research Wall

Good for synthesis, competitive reviews, and evidence-heavy reports.

- Group findings into clusters with visible source or confidence labels.
- Pair each observation with interpretation and implication.
- Use contrast panels for alternatives or market positions.
- End with a recommendation that traces back to the strongest evidence cluster.

## Launch Control

Good for launch readiness, GTM planning, and multi-team execution.

- Use one central launch readiness strip: product, sales, support, risk, decision.
- Give each lane a status, owner, next checkpoint, and blocker.
- Make the final ask feel like clearing a launch gate, not a generic approval slide.

## Field Report

Good for pilots, customer deployments, operations reviews, and hardware/software rollouts.

- Use the physical or operational context as the organizing metaphor.
- Show site state, observed signal, operational implication, and required action.
- Bring metrics close to the place or workflow they affect.
- Keep the tone factual and grounded; avoid stock-like polish that hides field reality.

## CSS Shape Hints

- Build with CSS grid first; use absolute positioning only for fixed decorative marks or labels.
- Prefer reusable deck-local classes such as `.metric-tile`, `.variance-bar`, `.decision-rail`, `.evidence-strip`, `.owner-chip`, `.status-badge`, and `.source-note`.
- Use stable dimensions for repeated objects so status labels, values, and owner names do not resize the layout.
- Create hierarchy through scale, weight, spacing, and borders before adding color.
- If the deck has three slides with the same card grid, change the third one into a rail, matrix, wall, or map.
- Let tables be raw material, not the final visual form: convert them into variance bars, comparison bands, or risk matrices when the audience needs judgment.
