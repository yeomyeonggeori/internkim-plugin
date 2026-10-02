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

Paperlogy is distributed under the SIL Open Font License 1.1. The license text from the release is `OFL.txt`.
