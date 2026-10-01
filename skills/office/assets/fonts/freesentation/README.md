# Freesentation Font Assets

Freesentation (프리젠테이션) 2.001, designed by Lee Juim (이주임), the designer of Paperlogy.

- Source: https://freesentation.blog/freesentation
- Download: https://github.com/Freesentation/freesentation/raw/refs/heads/main/Freesentation-2.001.zip

- `Freesentation-4Regular.woff2`: 400
- `Freesentation-7Bold.woff2`: 700

A deck that names Freesentation draws its regular text in 400 and every heavier weight in 700. The release also has Thin, ExtraLight, Light, Medium, SemiBold, ExtraBold and Black.

Each file is the release's TTF stored as WOFF2 with fontTools 4.62 (`fontTools.ttLib.woff2.compress(source, target, transform_tables=set())`). Leaving the glyph tables untransformed makes the skill's first-use unpacking fast; unpacking restores every table of the release file except DSIG, which WOFF2 does not carry.

Freesentation is distributed under the SIL Open Font License 1.1. The license text from the release repository is `OFL.txt`.
