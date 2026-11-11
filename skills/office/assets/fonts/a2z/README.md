# A2Z Font Assets

A2Z (에이투지체) 1.001, designed by Lee Juim (이주임), the designer of Paperlogy.

- Source: https://freesentation.blog/a2z
- Download: https://github.com/Freesentation/A2Z/raw/refs/heads/main/v1.001/에이투지체-ttf-v1.001.zip

- `A2Z-4Regular.woff2`: 400, from `에이투지체-4Regular.ttf`
- `A2Z-7Bold.woff2`: 700, from `에이투지체-7Bold.ttf`

A deck that names A2Z draws its regular text in 400 and every heavier weight in 700. The release also has Thin, ExtraLight, Light, Medium, SemiBold, ExtraBold and Black.

Each file is the release's TTF stored as WOFF2 with fontTools 4.62 (`fontTools.ttLib.woff2.compress(source, target, transform_tables=set())`). Leaving the glyph tables untransformed makes the skill's first-use unpacking fast; unpacking restores every table of the release file except DSIG, which WOFF2 does not carry.

The release maps all 11,172 precomposed Hangul syllables but draws only 2,780 of them; the other 8,392 point at empty glyphs. Because the font claims those syllables, no renderer, browser or PowerPoint falls back to another font for them, and they come out blank. These files leave the 8,392 code points out of `cmap`, with every glyph and metric unchanged, so a syllable outside the 2,780 is drawn by the next font in the list. `tests/test_bundled_font_files.py` fails when a bundled face maps a visible character to an empty glyph.

The source page lists the license as the SIL Open Font License, and each font's name table says "licensed under the SIL Open Font License, Version 1.1". The release repository carries no license file, so `OFL.txt` is the OFL 1.1 text under the copyright line from the font's name table.
