# Decks

A deck is one file, `slides.html`, written with the built-in kit and built into `build/<deck-slug>.pdf`. The kit supplies type, spacing, colors, footer, page numbers and charts, so you write short HTML and no CSS. SKILL.md's rules for source truth apply: a deck never invents dates, people, values or claims.

## Write slides.html

Work in `artifacts/<deck-slug>/`. Write the whole file in one step with your file tool, never through a heredoc. To change an existing deck, edit its `slides.html` in place; `deck restore` recovers it from a delivered `.html`.

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
  <aside class="notes">발표자가 이 슬라이드에서 할 말</aside>
</section>
<!-- one <section data-layout="..."> per slide -->
</body>
</html>
```

- `data-theme`: `editorial` (warm paper, the default), `corporate` (white and blue), `midnight` (dark), `swiss` (white, black and red). A brand color goes in `data-accent="#E4002B"` on `<body>`.
- Every part is a direct child of its `<section>`.
- A title states the slide's conclusion as a sentence in the request's language. `<em>` colors key words.
- Any slide takes `.eyebrow` (kicker), `.lead` (subtitle), `.takeaway` (conclusion band), `.source` (source line, shown in the footer) and `<aside class="notes">` (speaker notes).
- `.pick` highlights one card, column, KPI or table row; `.up` and `.down` color a change.

## Layouts

Choose each slide's layout from its content. Three slides in a row never share a layout, and six or more slides use at least three.

| Content | Layout |
| --- | --- |
| order of the talk | `agenda` |
| part divider | `section` |
| one sentence to remember | `statement` |
| one number that carries the point | `number` |
| two to four metrics, one unit system | `kpi` |
| two to four parallel points | `cards` |
| two options or before and after | `comparison` |
| three to six steps or dates | `timeline` |
| rows the audience must read | `table` |
| trend, ranking or share | `chart` |
| a person's words | `quote` |
| a photo that shows the subject | `image` |
| the decision or next actions | `closing` |

```html
<section data-layout="agenda"><h2>오늘 다룰 내용</h2><ol><li>3분기 성과</li><li>지역별 실적</li><li>4분기 계획</li></ol></section>
<section data-layout="section"><p class="eyebrow">02</p><h2>지역별 실적</h2></section>
<section data-layout="statement"><h2>사장님은 하루 <em>47분</em>을 재고 확인에 씁니다</h2></section>
<section data-layout="number"><h2>빠른 배송이 재구매를 늘립니다</h2><p class="value">+9%p</p><p class="label">재구매율 차이</p><ul><li>3일 이내 46%</li><li>4일 이상 37%</li></ul></section>
<section data-layout="kpi"><h2>매출과 이익 모두 목표를 넘었습니다</h2>
  <div class="kpi"><p class="value">128억</p><p class="label">매출</p><p class="up">목표 대비 +6%</p></div>
  <div class="kpi"><p class="value">14.2%</p><p class="label">영업이익률</p><p class="up">+2.1%p</p></div></section>
<section data-layout="cards"><h2>두 기능으로 재고 업무를 줄입니다</h2>
  <div class="card"><p class="label">알림</p><h3>품절 전 알림</h3><p>품절 3일 전에 알립니다.</p></div>
  <div class="card"><p class="label">추천</p><h3>발주 추천</h3><p>적정 수량을 제안합니다.</p></div></section>
<section data-layout="comparison"><h2>물류비 상승에 대응책이 있습니다</h2>
  <div class="column"><p class="label">리스크</p><h3>배송 지연</h3><ul><li>평균 4.1일</li></ul></div>
  <div class="column pick"><p class="label">대응</p><h3>권역 물류센터</h3><ul><li>11월 1일 가동</li></ul></div></section>
<section data-layout="timeline"><h2>세 단계로 물류를 바로잡습니다</h2>
  <div class="step done"><p class="label">10월</p><h3>배송사 계약</h3><p>단가를 정합니다.</p></div>
  <div class="step"><p class="label">11월</p><h3>센터 가동</h3><p>당일 출고합니다.</p></div>
  <div class="step"><p class="label">12월</p><h3>성과 보고</h3><p>결과를 보고합니다.</p></div></section>
<section data-layout="table"><h2>수도권이 성장을 이끌었습니다</h2>
  <table><tr><th>지역</th><th>매출</th><th>달성률</th></tr><tr class="pick"><td>수도권</td><td>58억</td><td>112%</td></tr><tr><td>영남</td><td>31억</td><td>107%</td></tr></table>
  <p class="source">출처: 영업관리팀, 2026년 9월 30일 기준</p></section>
<section data-layout="chart"><h2>매출은 네 분기 연속 늘었습니다</h2>
  <figure data-chart="column" data-labels="4Q25, 1Q26, 2Q26, 3Q26" data-values="96, 104, 113, 128" data-unit="억" data-highlight="3Q26"><figcaption>분기 매출, 단위 억 원</figcaption></figure>
  <div class="insight"><p class="value">+33%</p><p>1년 사이 증가</p></div></section>
<section data-layout="quote"><blockquote>주말에 재고를 세는 일이 없어졌어요.</blockquote><p class="by">박예시 · 점주</p></section>
<section data-layout="image"><img src="images/warehouse.jpg" alt="창고"><h2>주문부터 입고까지 자동입니다</h2><p>판매 데이터를 매시간 가져옵니다.</p></section>
<section data-layout="closing"><h2>세 가지를 승인해 주십시오</h2><ol><li>예산 6억 원</li><li>파트너 두 곳 계약</li><li>11월 3일 출시</li></ol></section>
```

## Charts

A chart is data in attributes; the kit draws it with value labels and the theme's colors. `data-chart` is `column`, `bar`, `stacked`, `line`, `donut` or `pie`. Give `data-labels` and `data-values` with one plain number per label, or several series as `data-series="2025: 82, 96; 2026: 90, 110"`. The unit goes in `data-unit`, never in the numbers. `data-highlight="3Q26"` draws one label in the accent and mutes the rest. Put the unit, period and source in `<figcaption>`. Keep one unit and one source per chart.

## Build and deliver

Run from `artifacts/<deck-slug>`, passing the slide count the user asked for and the source facts that must appear:

```json
{"command": "<skill>/scripts/office deck build --slide-count 10 --required-text \"128억\" --required-text \"2026년 3분기\"", "workingDirectoryPath": "artifacts/<deck-slug>"}
```

It writes `build/<deck-slug>.pdf`; add `--format pptx` for PowerPoint or `--format all` for both. `<skill>/scripts/office deck check` runs its first stage alone.

1. The build first checks the markup of `slides.html`: an unknown layout, a missing part, a repeated layout, a placeholder such as `XX` or `TODO`, a missing required fact, a wrong slide count, chart numbers that do not parse, or a missing image stops it. Each issue names the slide and the fix.
2. It then renders and measures every slide. The summary starts with the verdict:
   - `ACCEPTABLE`: deliver the file it names. Other issues are advice; do not redesign a slide that is clean.
   - `FIX ROUND 1 OF 2` or `2 OF 2`: fix only the listed defects (text that overflows or overlaps, content off the slide, a missing fact, an off-palette color, tiny text) by shortening or splitting, then build again.
   - `STOP FIXING`: deliver and name the defects that remain.
   - `NOT MEASURED`: neither bun nor node 18 could draw the slides, so there is no PDF; deliver `build/<deck-slug>.html` and say the layout was not checked.
3. Before attaching, open `build/review/contact-sheet-01.png` once and confirm the slides read as intended.

## Images

Use a photo only when it shows what the slide is about, in a `cover` or `image` slide. `<skill>/scripts/office deck image "warehouse" images/warehouse.jpg` saves a public-domain photo and reports its ratio and source page; look at the file and drop it if it shows something else. The kit crops it to fill its frame. Never put a grey box or a placeholder where a photo would go; without a fitting photo, use another layout. Name the photo's source in `.source`. No emoji.

## Custom design

A brand that needs more than `data-accent` adds a `<style>` that sets the theme tokens (`--accent`, `--accent-2`, `--ink`, `--bg`, `--surface`) on `:root`. A `DESIGN.md` beside `slides.html` is optional; the colors in its front matter join the palette. The check reports any other color as `OFF_PALETTE_COLOR`.

## PPTX

The PPTX is built from the rendered slides: every word is an editable text box, boxes and chart bars are native shapes, line and donut strokes stay in a picture, and Paperlogy is embedded.

## Editing a delivered .pptx

When the user hands over a .pptx, or asks for a change to one with no `slides.html` beside it, run `<skill>/scripts/office deck read <file.pptx>`: each shape's index, kind, box and text style, with tables, charts and notes. Write the change as one batch for `deck apply <file.pptx> <ops.json>` with every number taken from that read; `<skill>/scripts/office guide deck apply` lists the operations. The batch applies whole or not at all; pass `--dry-run` to preview and `--output` to keep the original. Each layout problem the result reports carries a `suggestion` that is an operation to apply as it is. Before delivering, run `deck check <file.pptx>` and look at its contact sheet; if it reports `PPTX_NOT_RENDERED`, say the slides were not seen. Text a built deck kept as a picture cannot be edited this way; for a larger change to a built deck, edit `slides.html` and rebuild, or recover it with `deck restore`.

## Without bun or node

The build then writes a PPTX that re-lays the slide text into stock layouts, reported as `PPTX_WITHOUT_DESIGN`, and no PDF. Say so when delivering.
