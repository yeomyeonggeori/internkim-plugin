# Decks

A deck is one file, `slides.html`, written with the built-in kit and built into `build/<deck-slug>.pdf`. The kit supplies type, spacing, colors, footer, page numbers and charts, so you write short HTML and no CSS. SKILL.md's rules for source truth apply: a deck never invents dates, people, values or claims.

## Write slides.html

Work in `artifacts/<deck-slug>/`. First run `<skill>/scripts/office guide slides`: it gives the slide order rules, every layout with its purpose and parts, and the chart attributes. Then run `<skill>/scripts/office guide design`: it says the deck's design, which InternKim chooses from the request, and lists the photos and the logo the deck can use. Then write the whole file in one step with your file tool, never through a heredoc. To change an existing deck, edit its `slides.html` in place; `office convert build/<deck-slug>.html slides.html` recovers it from a delivered `.html`.

```html
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Sample Electronics Q3 2026 Business Review</title></head>
<body>
<section data-layout="cover">
  <p class="eyebrow">Q3 2026 business review</p>
  <h1>Q3 revenue reached $128M, 6% above target</h1>
  <p class="lead">The premium line and B2B contracts drove the growth.</p>
  <p class="meta">Strategy team, Alex Sample · October 6, 2026</p>
  <aside class="notes">Q3 revenue was $128M, 6% above target.</aside>
</section>
<section data-layout="chart">
  <h2>Revenue grew for four quarters in a row</h2>
  <figure data-chart="column" data-labels="4Q25, 1Q26, 2Q26, 3Q26" data-values="96, 104, 113, 128" data-unit="M" data-highlight="3Q26"><figcaption>Quarterly revenue in $M. Source: Finance</figcaption></figure>
  <div class="insight"><p class="value">+33%</p><p>growth in one year</p></div>
  <aside class="notes">Revenue rose 33% in a year, from $96M to $128M.</aside>
</section>
<section data-layout="closing">
  <h2>Three approvals today let us launch in November</h2>
  <ol><li>A $6M budget</li><li>Contracts with two partners</li><li>Launch on November 3</li></ol>
  <aside class="notes">With these three decisions today, we launch in November.</aside>
</section>
</body>
</html>
```

- Every part is a direct child of its `<section>`.
- A title states the slide's conclusion as a sentence in the request's language. `<em>` colors key words.
- Choose each slide's layout from the shape of its content, by the content shapes `office guide slides` lists; write the other slides from it rather than from this example.
- Follow the cover and imagery `office guide design` names. Without photos, a `data-icon` on cards, metrics, steps and agenda or closing items gives the deck a visual rhythm.
- The design is applied by the build: write no `data-theme`, colors or fonts unless the request names them.

## Build and deliver

Run from `artifacts/<deck-slug>`, passing the slide count the user asked for and the source facts that must appear:

```json
{"command": "<skill>/scripts/office create build/<deck-slug>.pdf slides.html --slide-count 10 --required-text \"128M\" --required-text \"Q3 2026\"", "workingDirectoryPath": "artifacts/<deck-slug>"}
```

The output's extension picks the format: `build/<deck-slug>.pptx` writes the PowerPoint and the PDF beside it. `<skill>/scripts/office check slides.html` runs the first stage alone.

1. The build first checks the markup of `slides.html` and stops on any problem it finds, listing them all at once, each naming the slide and the fix.
2. It then renders and measures every slide. The summary starts with the verdict:
   - `ACCEPTABLE`: deliver the file it names. Other issues are advice; do not redesign a slide that is clean.
   - `FIX ROUND 1 OF 2` or `2 OF 2`: fix only the listed defects by shortening, splitting or filling, then build again.
   - `STOP FIXING`: deliver and name the defects that remain.
3. When the build result names `visualReview`, deliver the file without opening the renders: the host asks a reviewer about every slide's render at delivery, repairs the slides it flags and reports what remains, which the reply then names. When it does not, open `build/review/contact-sheet-01.png` once before attaching and confirm the slides read as intended.

## Images

The photos a deck can use are the ones `office guide design` lists: the request's attachments and the data room images the requester can read. Use each one that shows the deck's subject, on the cover, a section divider or an `image` slide beside what it shows, and skip one that does not fit. Point `src` at the listed path; the kit crops each photo to its frame, and `data-focus="top"`, `bottom`, `left` or `right` keeps that side in view. A caption or a fact about a photo comes only from its title, its summary or the request. Never put a grey box or a placeholder where a photo would go; without a fitting photo, use another layout. No emoji.

Only when the person asks for photos to be found, `<skill>/scripts/office image "warehouse shelves" images/warehouse.jpg` saves up to three public-domain candidates for an English query, with each one's ratio and source page; keep the one that shows the subject, delete the rest, and name its source in `.source`.

## Custom design

A brand that needs more than `data-accent` adds a `<style>` that sets the theme tokens (`--accent`, `--accent-2`, `--ink`, `--bg`, `--surface`) on `:root`. A `DESIGN.md` beside `slides.html` is optional; the colors in its front matter join the palette. The check reports any other color as `OFF_PALETTE_COLOR`.

## PPTX

The PPTX is built from the rendered slides: every word is an editable text box, boxes are native shapes, diagram arrows are connectors attached to their boxes, each kit chart is a native chart with its data, each table is a native table, and the shipped fonts the slides use are embedded.

## Editing a delivered .pptx

When the user hands over a .pptx, or asks for a change to one with no `slides.html` beside it, run `<skill>/scripts/office read <file.pptx>`: each shape's index, kind, box and text style, with tables, charts and notes. Write the change as one batch for `office apply <file.pptx> <ops.json>` with every number taken from that read; `<skill>/scripts/office guide apply pptx` lists the operations. The batch applies whole or not at all; pass `--dry-run` to preview and `--output` to keep the original. Each layout problem the result reports carries a `fix`: the operation to apply as it is, or, when no single operation fits the text, an empty list and a `suggestion` to shorten or split it. Before delivering, run `office check <file.pptx>` and look at its contact sheet; if it reports `PPTX_NOT_RENDERED`, say the slides were not seen. Text a built deck kept as a picture cannot be edited this way; for a larger change to a built deck, edit `slides.html` and rebuild, or recover it with `office convert`.
