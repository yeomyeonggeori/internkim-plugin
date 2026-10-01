# Decks

A deck is one file, `slides.html`, written with the built-in kit and built into `build/<deck-slug>.pdf`. The kit supplies type, spacing, colors, footer, page numbers and charts, so you write short HTML and no CSS. SKILL.md's rules for source truth apply: a deck never invents dates, people, values or claims.

## Write slides.html

Work in `artifacts/<deck-slug>/`. First run `<skill>/scripts/office guide deck`: it gives the slide order rules, the themes, every layout with its purpose and parts, and the chart attributes. Then write the whole file in one step with your file tool, never through a heredoc. To change an existing deck, edit its `slides.html` in place; `deck restore` recovers it from a delivered `.html`.

```html
<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>샘플전자 2026년 3분기 사업 리뷰</title></head>
<body data-theme="corporate">
<section data-layout="cover">
  <p class="eyebrow">2026년 3분기 사업 리뷰</p>
  <h1>3분기 매출 128억 원, 목표를 6% 넘었습니다</h1>
  <p class="lead">프리미엄 라인과 B2B 계약이 성장을 이끌었습니다.</p>
  <p class="meta">전략기획팀 이샘플 · 2026년 10월 6일</p>
  <aside class="notes">3분기 매출은 128억 원으로 목표를 6% 넘었습니다.</aside>
</section>
<section data-layout="chart">
  <h2>매출은 네 분기 연속 늘었습니다</h2>
  <figure data-chart="column" data-labels="4Q25, 1Q26, 2Q26, 3Q26" data-values="96, 104, 113, 128" data-unit="억" data-highlight="3Q26"><figcaption>분기 매출, 단위 억 원, 출처: 재무팀</figcaption></figure>
  <div class="insight"><p class="value">+33%</p><p>1년 사이 증가</p></div>
  <aside class="notes">1년 전 96억 원에서 128억 원으로 33% 늘었습니다.</aside>
</section>
<section data-layout="closing">
  <h2>세 가지를 승인해 주십시오</h2>
  <ol><li>예산 6억 원</li><li>파트너 두 곳 계약</li><li>11월 3일 출시</li></ol>
  <aside class="notes">오늘 이 세 가지를 결정해 주시면 11월에 출시합니다.</aside>
</section>
</body>
</html>
```

- Every part is a direct child of its `<section>`.
- A title states the slide's conclusion as a sentence in the request's language. `<em>` colors key words.
- Choose each slide's layout from its content. `office guide deck` lists every layout with its purpose and parts, and every chart attribute; write the other slides from it rather than from this example.

## Build and deliver

Run from `artifacts/<deck-slug>`, passing the slide count the user asked for and the source facts that must appear:

```json
{"command": "<skill>/scripts/office deck build --slide-count 10 --required-text \"128억\" --required-text \"2026년 3분기\"", "workingDirectoryPath": "artifacts/<deck-slug>"}
```

It writes `build/<deck-slug>.pdf`; add `--format pptx` for PowerPoint or `--format all` for both. `<skill>/scripts/office deck check` runs its first stage alone.

1. The build first checks the markup of `slides.html` and stops on any problem it finds, listing them all at once, each naming the slide and the fix.
2. It then renders and measures every slide. The summary starts with the verdict:
   - `ACCEPTABLE`: deliver the file it names. Other issues are advice; do not redesign a slide that is clean.
   - `FIX ROUND 1 OF 2` or `2 OF 2`: fix only the listed defects by shortening, splitting or filling, then build again.
   - `STOP FIXING`: deliver and name the defects that remain.
3. Before attaching, open `build/review/contact-sheet-01.png` once and confirm the slides read as intended.

## Images

Use a photo only when it shows what the slide is about, in a `cover` or `image` slide. `<skill>/scripts/office deck image "warehouse shelves" images/warehouse.jpg` saves up to three public-domain candidates for an English query, with each one's ratio and source page; look at them, keep the one that shows the subject, and delete the rest. The kit crops it to fill its frame. Never put a grey box or a placeholder where a photo would go; without a fitting photo, use another layout. Name the photo's source in `.source`. No emoji.

## Custom design

A brand that needs more than `data-accent` adds a `<style>` that sets the theme tokens (`--accent`, `--accent-2`, `--ink`, `--bg`, `--surface`) on `:root`; they replace those of the `data-theme` it names. A `DESIGN.md` beside `slides.html` is optional; the colors in its front matter join the palette. The check reports any other color as `OFF_PALETTE_COLOR`.

## PPTX

The PPTX is built from the rendered slides: every word is an editable text box, boxes are native shapes, diagram arrows are connectors attached to their boxes, each kit chart is a native chart with its data, each table is a native table, and the shipped fonts the slides use are embedded.

## Editing a delivered .pptx

When the user hands over a .pptx, or asks for a change to one with no `slides.html` beside it, run `<skill>/scripts/office deck read <file.pptx>`: each shape's index, kind, box and text style, with tables, charts and notes. Write the change as one batch for `deck apply <file.pptx> <ops.json>` with every number taken from that read; `<skill>/scripts/office guide deck apply` lists the operations. The batch applies whole or not at all; pass `--dry-run` to preview and `--output` to keep the original. Each layout problem the result reports carries a `fix`: the operation to apply as it is, or, when no single operation fits the text, an empty list and a `suggestion` to shorten or split it. Before delivering, run `deck check <file.pptx>` and look at its contact sheet; if it reports `PPTX_NOT_RENDERED`, say the slides were not seen. Text a built deck kept as a picture cannot be edited this way; for a larger change to a built deck, edit `slides.html` and rebuild, or recover it with `deck restore`.
