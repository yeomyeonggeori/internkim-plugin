# Paperlogy Font Assets

Paperlogy (페이퍼로지) 1.001, designed by Lee Juim (이주임) with the PPT YouTuber Kim Dogyun (페이퍼로지).

- Source: https://freesentation.blog/paperlogyfont
- Download: https://github.com/Freesentation/paperlogy/raw/refs/heads/main/Paperlogy-1.001.zip

- `Paperlogy-4Regular.woff2`: 400
- `Paperlogy-6SemiBold.woff2`: 600
- `Paperlogy-7Bold.woff2`: 700
- `Paperlogy-8ExtraBold.woff2`: 800

These are the four weights the deck kit selects. The release also has Thin, ExtraLight, Light, Medium and Black.

Each file is the release's TTF stored as WOFF2 with fontTools 4.62 (`fontTools.ttLib.woff2.compress(source, target, transform_tables=set())`). Leaving the glyph tables untransformed makes the skill's first-use unpacking fast; unpacking restores every table of the release file except DSIG, which WOFF2 does not carry. A deck exported as HTML carries these files as they are.

The release maps all 11,172 precomposed Hangul syllables but draws only 2,780 of them; the other 8,392 point at empty glyphs. Because the font claims those syllables, no renderer, browser or PowerPoint falls back to another font for them, and they come out blank. These files leave the 8,392 code points out of `cmap`, with every glyph and metric unchanged, so a syllable outside the 2,780 is drawn by the next font in the list. `tests/test_bundled_font_files.py` fails when a bundled face maps a visible character to an empty glyph.

Paperlogy is distributed under the SIL Open Font License 1.1. The license text from the release is `OFL.txt`.
