# Minimal Black-and-White DESIGN.md Reference

Use this as a reference for sober analytical decks. Do not copy it blindly; adapt the rationale, emphasis, and layout choices to the user's topic.

```yaml
---
colors:
  background: "#FAFAFA"
  surface: "#FFFFFF"
  ink: "#111111"
  muted: "#6B7280"
  accent: "#111111"
  line: "#D4D4D8"
typography:
  display: "Paperlogy, Noto Sans KR, system Korean sans"
  body: "Paperlogy, Noto Sans KR, system Korean sans"
layout:
  canvas: "16:9"
  margin: "64px"
  rhythm: "8px"
  radius: "8px"
---

# Visual Direction

Black-and-white analytical presentation with restrained lines, compact hierarchy, vendored Paperlogy typography, and generous whitespace. Use a thin top rule, conclusion-first titles, quiet cards, comparison columns, matrices, and recommendation blocks. Avoid decorative gradients, stock-like backgrounds, and bullet-only slides.
```

## HTML Slide Style Notes

- Keep `<!-- design-source: DESIGN.md -->` near the top of `slides.html`.
- Put the vendored Paperlogy WOFF2 `@font-face` rules from `references/deck/webfonts.md` near the top of the `slides.html` style block.
- Use `1600px × 900px` as the slide layout coordinate system: `.slide { width: 1600px; height: 900px; }`.
- Add `@page { size: 1600px 900px; margin: 0; }` so PDF export uses the same geometry.
- Keep HTML, PDF, render-review screenshots, and PPTX image export on the same `1600px × 900px` geometry.
- Use `font-family: "Paperlogy", "Noto Sans KR", system-ui, -apple-system, BlinkMacSystemFont, "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif;` for both slide body and display text unless the user requests another font.
- Keep the palette almost monochrome; reserve accent only for rules, tags, or one key number.
- Use semantic HTML containers inside each slide: `.frame`, `.eyebrow`, `.takeaway`, `.cards`, `.card`, `.comparison`, `.matrix`, `.timeline`, `.recommendation`.
- Use fit-safe layout defaults: `.frame` as fixed 16:9 grid or flex, variable content tracks as `minmax(0, 1fr)`, and text containers with `min-width: 0`, `min-height: 0`, and `overflow-wrap: anywhere`.
- Do not hide variable text with `overflow: hidden` or `overflow: clip`; reduce copy, split cards, or lower type size instead.
- Keep line budgets tight: title 1-2 lines, takeaway 1-2 lines, cards 2-4 lines, matrix cells 2-3 lines, timeline steps 2-3 lines.
- Treat CSS as overflow prevention, not proof. Confirm final fit in the render review contact sheets and matching fit-review text files.
- Keep radius at 8px or less unless the deck topic clearly asks for a softer visual language.
- Prefer one-sentence conclusions over topic labels. For example, write "Operational separation makes failures auditable" instead of "Architecture".
- If a contact sheet looks clean but thin, improve the slide's substance before changing decoration. Add a worked example, specific workflow, decision matrix, concrete tradeoff, or recommendation.
- Keep each slide tied to the deck story spine: situation, tension, thesis, proof, and close.
