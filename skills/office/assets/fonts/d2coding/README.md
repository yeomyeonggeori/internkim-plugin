# D2Coding Font Assets

D2Coding 1.3.3 (build 20260725), by NAVER, designed by FONTRIX.

- Source: https://github.com/naver/d2-coding-font
- Download: https://github.com/naver/d2-coding-font/releases/download/VER1.3.3/D2Coding-Ver1.3.3-20260725.zip, folder `D2Coding`

- `D2Coding-Regular.woff2`: 400, from `D2Coding-Ver1.3.3-20260725.ttf`
- `D2Coding-Bold.woff2`: 700, from `D2CodingBold-Ver1.3.3-20260725.ttf`

D2Coding also carries all 4,888 KS X 1001 Hanja, so it is the fallback for Hanja the other families lack.

Each file is the release's TTF stored as WOFF2 with fontTools 4.62 (`fontTools.ttLib.woff2.compress(source, target, transform_tables=set())`). Leaving the glyph tables untransformed makes the skill's first-use unpacking fast; unpacking restores every table of the release file except DSIG, which WOFF2 does not carry.

D2Coding is distributed under the SIL Open Font License 1.1. The license text from the release is `OFL.txt`.
