# Decks

Create a useful, visually strong deck and attach accepted output. HTML-first means `slides.html` is the source of truth, `DESIGN.md` the design brief, and HTML is the layout surface and default deliverable; the PPTX is built from the rendered slides with editable text. SKILL.md's rules for source truth and verification apply here, and a deck never invents current dates, people, values, or claims.

## Workflow

1. Decide the output format, slide count, audience, and story spine before writing. Pick one deck archetype and make each slide's job, claim, proof, and visual structure clear.
2. Resolve revisions from the latest compatible artifact in recent same-conversation posts. Older PDF or Markdown files are supporting material. For an existing deck, work only in `artifacts/<deck-slug>/`, keep the same slug, and use `deck restore` when the controller-free source must be recovered. Treat `slides.html` as the canonical controller-free source; edit it in place with targeted changes and never rewrite an existing deck whole.
3. For a new deck, write the complete `slides.html` as a file in one step; do not assemble it through shell heredocs or echo. Write `DESIGN.md`, `deck-brief.md`, and `required-visible-text.txt` right after it, so they never delay the primary source file.
4. Put `data-visual-system` on the body and `data-slide-role` on every slide. Use the requested language and a complete HTML document, show the source facts, and write the spoken notes in `<aside class="notes">`. Through every edit keep the `design-source: DESIGN.md` marker, the slide count the brief requests, and the facts listed in `required-visible-text.txt`.
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

## Measured layout

With a browser, the build measures every slide after the fonts load and writes `build/review/geometry.json`: elements whose content is larger than their box, elements outside the slide, text that overlaps other text by at least 12% of the smaller text, and images stretched more than 5% away from their own ratio. The review reports each as `CONTENT_OVERFLOW`, `OUT_OF_FRAME`, `TEXT_OVERLAP`, or `IMAGE_DISTORTED` on the slide that has it, naming the element and its size. These are warnings; fix the ones that are real defects and leave a deliberate overlap alone. Without a browser there is no `geometry.json` and the review reports `GEOMETRY_NOT_MEASURED`: say the layout was not measured.

## Speaker notes

The text of each slide's `<aside class="notes">` is written into the PPTX notes, with or without a browser. A slide without notes gets none.

## Editable PPTX

With a browser, each PPTX slide is built from the rendered slide in three layers. Boxes the browser drew with a solid fill or solid borders become native shapes: rectangles, rounded rectangles with the measured corner radius, ellipses and straight rules, in paint order. Everything DrawingML cannot draw the same way (SVG, images, gradients, shadows, transforms, dashed borders) stays in a picture underneath, together with any box it would otherwise cover. On top sits one text box for every element that holds text, placed and styled as the browser drew it: font, size, weight, color, letter spacing, line height, alignment, bullets, numbering, line breaks and links. The recipient can edit every word and recolor or resize every card, bar and chip; `details.pptx.shapes` and `boxesKeptAsPicture` count them. Text boxes do not grow or shrink, so a much longer replacement runs past its box. The Paperlogy weights the deck uses are embedded in the file; `details.pptx.embeddedFonts` lists them. PowerPoint and LibreOffice 26.2 draw with the embedded faces; LibreOffice 24.2 and viewers that ignore embedded fonts substitute their own until Paperlogy is installed. A deck font other than Paperlogy is named but not embedded and reported as `FONT_NOT_EMBEDDED`. Rotated, skewed, filtered, gradient-clipped and SVG text stays in the picture and is reported as `TEXT_KEPT_AS_PICTURE`; charts and diagrams drawn in SVG are pictures too.

## Editing a delivered .pptx

When the user hands over a .pptx, or asks for a change to one that has no `slides.html` beside it, run `<skill>/scripts/office deck read <file.pptx>`. It lists each slide's number, layout name, shapes with their index and text, tables, and notes. Then change the file with `deck apply <file.pptx> <ops.json>`: a batch of `set_text`, `find_replace`, `set_notes`, `delete_slide`, and `reorder`, with every slide number and shape index taken from that read, applied whole or not at all. Pass `--dry-run` first when the batch is long, and `--output` to keep the original. `office guide deck` lists each operation's fields. Layouts, masters, and everything an operation does not touch are kept. A PPTX built here holds its text in text boxes, so `deck read` lists them; text that stayed in the picture cannot be edited this way. For anything larger than a wording change, edit `slides.html` and rebuild, or recover it with `deck restore`.

## Design contract

Use the vocabulary of title thesis, section divider, comparison, matrix, timeline, evidence card, recommendation, and closing ask. Reject shallow content: generic cards, claims without examples, raw `<table>` or bare `<ul>`, and slides that only restate the prompt. Add a worked example, target-versus-actual metrics, and risk/evidence/response/owner where relevant. End with a decision or next action.

The `deck-brief.md` states the story spine, slide count, visual system, signature move, and what would be too shallow. A board or quarterly deck needs KPI cards, status chips, variance bars, owner-date timelines, risk matrices, approval panels, or another recurring primitive, not the same 2x2 card dashboard on every slide. Read `references/deck/layouts.md` and `references/deck/minimal-design.md` first; use their `colors`, `typography`, and `layout` vocabulary, then consult `references/deck/composition-seeds.md`, `references/deck/visual-styles.md`, and `references/deck/webfonts.md` when needed.

Use claim-style titles that name the exact organization, product, and period, with the period worded as the source words it, Korean included. `required-visible-text.txt` holds one source fact or must-appear phrase per line. It is a source ledger, not a token filter; represent each fact naturally in rendered text.

## Source and visual quality

`DESIGN.md` may use Stitch-compatible YAML front matter followed by `Style Prompt`, `Visual Identity Gate`, `Scene`, `Design Thesis`, `Visual System`, `Signature Move`, and `Anti-default Check`. It must express a design thesis and a recurring signature move. A dark theme is not a visual system. Every slide should fill the 16:9 frame safely, avoid cropped or hidden text, and use readable type and meaningful visual hierarchy.

Do not use emoji as functional icons or bullets. Paperlogy is the default display and body font, with local WOFF2 fallback and the CSS stack `"Paperlogy", "Noto Sans KR", system-ui`. Follow `references/deck/webfonts.md` for web fonts and never paste base64 font data into source.

## Without a browser

When no browser can render the deck, the build falls back to a PPTX that re-lays the slide text into stock layouts, reported as `PPTX_WITHOUT_DESIGN`, and, where Pillow is installed, preview images drawn from the slide text. The fallback picks each slide's layout from its `data-slide-role`: `cover` or `title`, `summary`, `metrics`, `timeline`, `risk`, and `approval` select those layouts, and any other role gets the plain generic layout. The review then reports `visualEvidenceReliable: false`.

## Delivery rules

PDF and PPTX are derived from the same `slides.html`; deliver the source with generated output when requested. Do not claim visual acceptance when `visualEvidenceReliable` is false.
