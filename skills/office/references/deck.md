# Decks

Create a useful, visually strong deck and attach accepted output. HTML-first means `slides.html` is the source of truth, `DESIGN.md` the design brief, and HTML is the layout surface and default deliverable; PPTX is image-backed by default. SKILL.md's rules for source truth and verification apply here, and a deck never invents current dates, people, values, or claims.

## Workflow

1. Decide the output format, slide count, audience, and story spine before writing. Pick one deck archetype and make each slide's job, claim, proof, and visual structure clear.
2. Resolve revisions from the latest compatible artifact in recent same-conversation posts. Older PDF or Markdown files are supporting material. For an existing deck, work only in `artifacts/<deck-slug>/`, keep the same slug, and use `deck restore` when the controller-free source must be recovered. Treat `slides.html` as the canonical controller-free source; edit it in place with targeted changes and never rewrite an existing deck whole.
3. For a new deck, write the complete `slides.html` as a file in one step; do not assemble it through shell heredocs or echo. Add `DESIGN.md`, `deck-brief.md`, and `required-visible-text.txt` immediately so they must not delay the primary source file.
4. Put `data-visual-system` on the body and `data-slide-role` on every slide. Use the requested language, a complete HTML document, visible source facts, and spoken notes in `<aside class="notes">`. Preserve the design-source marker, requested slide count, source-fact ledger intent.
5. Build from the persistent artifact workspace. The command shape is:

   ```json
   {"command": "<skill>/scripts/office deck build", "workingDirectoryPath": "artifacts/<deck-slug>"}
   ```

   For a final PPTX conversion use:

   ```json
   {"command": "FORMATS=pptx <skill>/scripts/office deck build", "workingDirectoryPath": "artifacts/<deck-slug>"}
   ```

   With no `FORMATS`, it creates `build/<deck-slug>.html` plus review evidence. Use `FORMATS=pptx` only for the final conversion, then deliver `artifacts/<deck-slug>/build/<deck-slug>.html` or `artifacts/<deck-slug>/build/<deck-slug>.pptx`. Run the command as one shell command line from that working directory.
6. Read the build's result: its issues carry every preflight, render, and review warning with a code, and `office guide deck` explains each code. Then inspect `slide-review.json`, contact sheets, `fit-review-XX.md`, and rendered image evidence. Check `needsDesignRevision`, `qualityGatePassed`, `visualQualityScore`, `visualEvidenceReliable`, expected visible text, and design warnings. Revise `slides.html` with targeted edits while the score improves. A clean export is not acceptance. Remaining review notes are not a delivery blocker after the required review loop. Do not spend delivery budget creating or attaching internal review-decision files.
7. Attach every accepted output when more than one file is delivered. Check an existing .pptx with `deck validate`.

## Design contract

Use the vocabulary of title thesis, section divider, comparison, matrix, timeline, evidence card, recommendation, and closing ask. Reject shallow content: generic cards, claims without examples, raw `<table>` or bare `<ul>`, and slides that only restate the prompt. Add a worked example, target-versus-actual metrics, and risk/evidence/response/owner where relevant. End with a decision or next action.

Pick one deck archetype and make its `deck-brief.md` state the story spine, slide count, visual system, signature move, and what would be too shallow. A board or quarterly deck needs KPI cards, status chips, variance bars, owner-date timelines, risk matrices, approval panels, or another recurring primitive, not the same 2x2 card dashboard on every slide. Avoid bullet-only decks. Read `references/deck/layouts.md` and `references/deck/minimal-design.md` first; use their `colors`, `typography`, and `layout` vocabulary, then consult `references/deck/composition-seeds.md`, `references/deck/visual-styles.md`, and `references/deck/webfonts.md` when needed.

Use claim-style titles, exact organization, product, and period, and preserve original period wording exactly. Preserve exact source values and show `제공된 자료 없음` when a source value is missing. Required facts go one per line in `required-visible-text.txt`: one source fact or must-appear phrase per line. This is a source ledger, not a token filter; represent them naturally in rendered text. Do not replace Korean period wording.

## Source and visual quality

`DESIGN.md` may use Stitch-compatible YAML front matter followed by `Style Prompt`, `Visual Identity Gate`, `Scene`, `Design Thesis`, `Visual System`, `Signature Move`, and `Anti-default Check`. It must express a design thesis and a recurring signature move. A dark theme is not a visual system. Every slide should fill the 16:9 frame safely, avoid cropped or hidden text, and use readable type and meaningful visual hierarchy.

Do not use emoji as functional icons or bullets. Paperlogy is the default display and body font, with local WOFF2 fallback and the CSS stack `"Paperlogy", "Noto Sans KR", system-ui`. Follow `references/deck/webfonts.md` for web fonts and never paste base64 font data into source. With `PRESENTATION_PPTX_MODE=native`, native text-backed PPTX is available when editable text is explicitly required; otherwise use image-backed PPTX.

## Without a browser

When no browser can render the deck, the build falls back to a text-backed PPTX and, where Pillow is installed, preview images drawn from the slide text. The fallback picks each slide's layout from its `data-slide-role`: `cover` or `title`, `summary`, `metrics`, `timeline`, `risk`, and `approval` select those layouts, and any other role gets the plain generic layout. The review then reports `visualEvidenceReliable: false`.

## Delivery rules

HTML is the default deliverable. PDF and PPTX are derived from the same `slides.html`; deliver the source with generated output when requested. Do not claim visual acceptance when `visualEvidenceReliable` is false. Source review, rendered text checks, and the requested review loop are required before delivery.
