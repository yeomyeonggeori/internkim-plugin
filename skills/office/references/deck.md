# Decks

A deck is designed top-down in stages, one file per stage, each checked before the next starts. There are no templates: you compose every page. The skill supplies the fonts, line icons, native charts, the company logo, photos and the checks. SKILL.md's rules for source truth apply: a deck never invents dates, people, values or claims, and design adds no text.

Work in `artifacts/<deck-slug>/`. Run `<skill>/scripts/office guide slides`, then `<skill>/scripts/office guide design`, which on InternKim gathers the photos and chooses the typeface before it answers. Write every file with your file tool, never a heredoc.

| Stage | File | Check |
| --- | --- | --- |
| 1 style sheet | `DESIGN.md` | `office check DESIGN.md` |
| 2 outline | `outline.json` | `office check outline.json` |
| 3 pages | `pages/01.html`, `pages/02.html`, … one per outline page | `office check pages/NN.html` after writing each |
| 4 build | `build/<deck-slug>.pptx` | the build's verdict |

## 1. Style sheet

`guide design` gives the shape. The front matter holds concrete colors and sizes, each color a `#RRGGBB` value you choose for this deck's subject, audience and company:

```markdown
---
style: "one sentence: the design language and why it fits this subject and audience"
colors:
  text: "#RRGGBB"
  accent: "#RRGGBB"
  secondary: "#RRGGBB"
  surface: "#RRGGBB"
  line: "#RRGGBB"
backgrounds:
  cover: "#RRGGBB"
  content: "#RRGGBB"
  data: "#RRGGBB"
  closing: "#RRGGBB"
sizes:
  display: "128px"
  title: "64px"
  body: "30px"
  small: "22px"
---
```

A color the request names, or the logo's own color, becomes the accent; otherwise the subject's mood picks it. Only when the person asks for a font by name, add `requested-font: "Exact Family Name"`: the build looks for it among the attachments, the data room, its cache and Google Fonts, embeds it, and when it finds none sets the deck in Paperlogy and reports `REQUESTED_FONT_UNAVAILABLE`, which your reply says, offering to rebuild when the person attaches the file.

## 2. Outline

`outline.json` holds every page's content before any page exists: a core hook, then per page its title, type, brief (one fact per line, with the real figures), figures (each number the page charts or shows large, as `{"label", "value", "unit"}`) and the listed photos it shows. Pass the slide count the user asked for: `office check outline.json --slide-count 10`. On InternKim the same command judges the outline's statements against the request and chooses each page's layout, without asking the person; when it passes, it lists every page's layout. `UNSUPPORTED_CLAIM` names a statement the request and its attachments do not support: restate it from them or drop it.

## 3. Pages

One page per step: the check names the next page's outline entry; re-read `DESIGN.md`, write `pages/NN.html` from that entry alone as one `<section>` with its own `<style>` and its title as an empty `<h1 data-title></h1>` the build fills, run `office check pages/NN.html`, and fix it until it passes before writing the next. The check measures that page alone: parts outside the page, content spilling out of its box, parts drawn over each other and text below the size floors. It warns when the page paints a color the style sheet does not name, or lacks the outline entry's photo, and refuses a chart whose values are not the entry's figures or whose axis mixes units. Speaker notes go in `<aside class="notes">`. A trend, ranking or share is a `<figure data-chart>` from the brief's numbers, a native editable chart in the PPTX: a count beside two percentages is a KPI beside a chart.

## 4. Build and deliver

Run from `artifacts/<deck-slug>`, passing the source facts that must appear:

```json
{"command": "<skill>/scripts/office create build/<deck-slug>.pptx . --slide-count 10 --required-text \"128M\" --required-text \"Q3 2026\"", "workingDirectoryPath": "artifacts/<deck-slug>"}
```

The output's extension picks the format: `.pptx` writes the PowerPoint and the PDF beside it. The build checks every stage again, then renders and measures every page. The summary starts with the verdict:

- `ACCEPTABLE`: deliver the file it names. When the build result names `visualReview`, deliver without opening the renders: the build already reviewed every page's render, repaired the pages it flagged and reported what remains, which the reply then names.
- `FIX ROUND 1 OF 2` or `2 OF 2`: fix only the listed defects in their page files, keep the copy, facts, palette and composition, and build again.
- `STOP FIXING`: deliver and name the defects that remain.

When the result names no `visualReview`, open `build/review/contact-sheet-01.png` once before attaching and confirm the pages read as intended.

## Photos and logo

The photos a deck can use are the ones `guide design` lists: the request's attachments and the data room images the requester can read. A page that shows one names it in its outline entry's `photos`; crop it with `object-fit: cover` in a frame of your own, and the build sets each photo's focal point. A caption or a fact about a photo comes only from its title, its summary or the request. Never put a grey box or a placeholder where a photo would go.

When the company has a logo, the build places it on the cover and the closing page, in a corner no text covers, with a plate behind it when its background needs one; do not write `<img data-logo>` and keep a corner free. No emoji.

Only when the person asks for photos to be found, `<skill>/scripts/office image "warehouse shelves" images/warehouse.jpg` saves up to three public-domain candidates for an English query, with each one's ratio and source page; keep the one that shows the subject, delete the rest, and name its source in `.source`.

## PPTX

The PPTX is built from the rendered pages: every word is an editable text box, boxes are native shapes, each table is a native table, each chart a native chart, and the shipped fonts the pages use are embedded.

## Editing a delivered .pptx

When the user hands over a .pptx, or asks for a change to one with no deck folder beside it, run `<skill>/scripts/office read <file.pptx>`: each shape's index, kind, box and text style, with tables, charts and notes. Write the change as one batch for `office apply <file.pptx> <ops.json>` with every number taken from that read; `<skill>/scripts/office guide apply pptx` lists the operations. The batch applies whole or not at all; pass `--dry-run` to preview and `--output` to keep the original. Each layout problem the result reports carries a `fix`: the operation to apply as it is, or, when no single operation fits the text, an empty list and a `suggestion` to shorten or split it. Before delivering, run `office check <file.pptx>` and look at its contact sheet; if it reports `PPTX_NOT_RENDERED`, say the slides were not seen. Text a built deck kept as a picture cannot be edited this way; for a larger change to a built deck, edit its page files and rebuild, or recover it with `office convert`.
