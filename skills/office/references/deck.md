# Decks

A deck is one file, `slides.html`, that you design and style yourself, built into `build/<deck-slug>.pdf`. The skill supplies the fonts, line icons, the company logo and photos, and the checks: contrast, overflow and overlap, the palette, the smallest type and a visual review of every slide. SKILL.md's rules for source truth apply: a deck never invents dates, people, values or claims.

## Write slides.html

Work in `artifacts/<deck-slug>/`. There are no templates: you design the deck yourself. First run `<skill>/scripts/office guide slides`; it gives the canvas, the fonts, the icons and the checks. Then run `<skill>/scripts/office guide design`, which lists the photos and the logo the deck can use. Then write two files with your file tool, never through a heredoc.

1. `DESIGN.md`, the deck's design system, decided from the request's subject, audience and purpose before any slide:

```markdown
---
intent: "one line: the style and why it fits this subject and audience"
colors:
  bg: "#FBFAF7"
  ink: "#1A1C20"
  muted: "#6B6F76"
  accent: "#1F6F5C"
  accent-2: "#C98A2B"
  surface: "#EFEDE6"
fonts:
  display: Pretendard
  body: Pretendard
spacing:
  margin: 96px
  gap: 32px
---
```

At most six colors, picked so text reads at 4.5:1 on its background. Fonts are the shipped ones `office guide slides` lists.

2. `slides.html`: one `<style>` in `<head>` that sets the design system's tokens on `:root` and styles everything, and one `<section>` per slide of exactly 1600x900 px. Lay each slide out from the shape of its content: a key number large, a sequence as steps, a comparison side by side, a trend as a chart you draw in HTML or SVG from the request's numbers. Give two slides in a row different compositions. Slide 1 is the cover; the last is the decision or next steps. Every title states the slide's conclusion in the request's language. Speaker notes go in `<aside class="notes">`.

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

The photos a deck can use are the ones `office guide design` lists: the request's attachments and the data room images the requester can read. Use each one that shows the deck's subject, on the cover, a section divider or an `image` slide beside what it shows, and skip one that does not fit. Point `src` at the listed path and crop it with `object-fit: cover` in a frame of your own. A caption or a fact about a photo comes only from its title, its summary or the request. Never put a grey box or a placeholder where a photo would go; without a fitting photo, design the slide without one. Place the company logo yourself, at one size and place on every slide, from the path `office guide design` gives. No emoji.

Only when the person asks for photos to be found, `<skill>/scripts/office image "warehouse shelves" images/warehouse.jpg` saves up to three public-domain candidates for an English query, with each one's ratio and source page; keep the one that shows the subject, delete the rest, and name its source in `.source`.

## PPTX

The PPTX is built from the rendered slides: every word is an editable text box, boxes are native shapes, diagram arrows are connectors attached to their boxes, each table is a native table, and the shipped fonts the slides use are embedded.

## Editing a delivered .pptx

When the user hands over a .pptx, or asks for a change to one with no `slides.html` beside it, run `<skill>/scripts/office read <file.pptx>`: each shape's index, kind, box and text style, with tables, charts and notes. Write the change as one batch for `office apply <file.pptx> <ops.json>` with every number taken from that read; `<skill>/scripts/office guide apply pptx` lists the operations. The batch applies whole or not at all; pass `--dry-run` to preview and `--output` to keep the original. Each layout problem the result reports carries a `fix`: the operation to apply as it is, or, when no single operation fits the text, an empty list and a `suggestion` to shorten or split it. Before delivering, run `office check <file.pptx>` and look at its contact sheet; if it reports `PPTX_NOT_RENDERED`, say the slides were not seen. Text a built deck kept as a picture cannot be edited this way; for a larger change to a built deck, edit `slides.html` and rebuild, or recover it with `office convert`.
