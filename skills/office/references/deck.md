# Decks

A deck is two files you design yourself: `DESIGN.md`, its design system, and `slides.html`, one `<section>` per slide, built into `build/<deck-slug>.pdf`. There are no templates. The skill supplies the fonts, line icons, native charts, the company logo, photos and the checks. SKILL.md's rules for source truth apply: a deck never invents dates, people, values or claims, and design adds no text.

## Design first

Work in `artifacts/<deck-slug>/`. Run `<skill>/scripts/office guide slides`, then, as a command of its own, `<skill>/scripts/office guide design`. The host answers the design questions and gathers photos between the two commands, so never chain them; if `guide design` says InternKim is still gathering, run it again.

`guide design` gives the design intent chosen from the request (accent, mood, type pairing, density, imagery) and palette candidates derived from it, the logo, the photos, and the avoid-list. Write `DESIGN.md` with your file tool, never a heredoc:

```markdown
---
intent: "one line: the style and why it fits this subject and audience"
palette: primary
---
```

`palette` names one of the candidates. Optional lines choose from closed lists: `type` (paperlogy, freesentation or a2z; the intent sets it, paperlogy by default), `density` (airy, balanced or dense), `shape` (sharp, soft or round) and `weight` (the title weight the type ships). Colors, fonts, sizes, radius and shadow come from these choices, so DESIGN.md holds no hex, font name or size. A color the request names, or the logo's own color, is already in the candidates. Only when the person asks for a font by name, add `requested-font: "Exact Family Name"`: the build looks for it among the attachments, the data room, its cache and Google Fonts, embeds it, and when it finds none sets the deck in Paperlogy and reports `REQUESTED_FONT_UNAVAILABLE`, which your reply says, offering to rebuild when the person attaches the file.

A color the request names, or the logo's own color, becomes the accent. Run `<skill>/scripts/office check DESIGN.md`: it names a choice that is not on its list before any slide exists.

## Write slides.html

One `<style>` in `<head>` styles everything with the tokens the build puts on `:root` (`var(--accent)`, `var(--size-body)` and the rest `guide slides` lists; the build sets every font, and `font-family` in your CSS is dropped), and one `<section>` per slide of exactly 1600x900 px. Lay each slide out from the shape of its content, and give two slides in a row different compositions. Slide 1 is the cover; the last is the decision or next steps. Every title states the slide's conclusion in the request's language. A trend, ranking or share is a `<figure data-chart>` from the request's numbers, a native editable chart in the PPTX. Speaker notes go in `<aside class="notes">`.

`<skill>/scripts/office check slides.html` renders the slides and measures each against the same rule table as `DESIGN.md`. It refuses with the code, the slide and the selector; fix only that. UNSUPPORTED_CLAIM names a statement the request and its attachments do not support: restate it from them or drop it before building.

## Build and deliver

Run from `artifacts/<deck-slug>`, passing the slide count the user asked for and the source facts that must appear:

```json
{"command": "<skill>/scripts/office create build/<deck-slug>.pdf slides.html --slide-count 10 --required-text \"128M\" --required-text \"Q3 2026\"", "workingDirectoryPath": "artifacts/<deck-slug>"}
```

The output's extension picks the format: `build/<deck-slug>.pptx` writes the PowerPoint and the PDF beside it.

1. The build runs `office check` first and stops on any refusal, listing them all at once.
2. It then renders and measures every slide. The summary starts with the verdict:
   - `ACCEPTABLE`: deliver the file it names. Other issues are advice; do not redesign a slide that is clean.
   - `FIX ROUND 1 OF 2` or `2 OF 2`: fix only the listed defects by shortening, splitting or filling, then build again.
   - `STOP FIXING`: deliver and name the defects that remain.
3. When the build result names `visualReview`, deliver the file without opening the renders: the host asks a reviewer about every slide's render at delivery, repairs the slides it flags and reports what remains, which the reply then names. When it does not, open `build/review/contact-sheet-01.png` once before attaching and confirm the slides read as intended.

## Photos and logo

The photos a deck can use are the ones `guide design` lists: the request's attachments and the data room images the requester can read. Use them readily, on the cover, a divider or beside what they show, and skip one that does not fit. Point `src` at the listed path and crop with `object-fit: cover` in a frame of your own; the build sets each photo's focal point. A caption or a fact about a photo comes only from its title, its summary or the request. Never put a grey box or a placeholder where a photo would go.

When the company has a logo, the build places it on the cover and the closing slide, in a corner no text covers, with a plate behind it when its background needs one; do not write `<img data-logo>` and keep a corner free. No emoji.

Only when the person asks for photos to be found, `<skill>/scripts/office image "warehouse shelves" images/warehouse.jpg` saves up to three public-domain candidates for an English query, with each one's ratio and source page; keep the one that shows the subject, delete the rest, and name its source in `.source`.

## PPTX

The PPTX is built from the rendered slides: every word is an editable text box, boxes are native shapes, each table is a native table, each chart a native chart, and the shipped fonts the slides use are embedded.

## Editing a delivered .pptx

When the user hands over a .pptx, or asks for a change to one with no `slides.html` beside it, run `<skill>/scripts/office read <file.pptx>`: each shape's index, kind, box and text style, with tables, charts and notes. Write the change as one batch for `office apply <file.pptx> <ops.json>` with every number taken from that read; `<skill>/scripts/office guide apply pptx` lists the operations. The batch applies whole or not at all; pass `--dry-run` to preview and `--output` to keep the original. Each layout problem the result reports carries a `fix`: the operation to apply as it is, or, when no single operation fits the text, an empty list and a `suggestion` to shorten or split it. Before delivering, run `office check <file.pptx>` and look at its contact sheet; if it reports `PPTX_NOT_RENDERED`, say the slides were not seen. Text a built deck kept as a picture cannot be edited this way; for a larger change to a built deck, edit `slides.html` and rebuild, or recover it with `office convert`.
