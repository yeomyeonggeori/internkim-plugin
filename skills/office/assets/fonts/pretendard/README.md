# Pretendard Font Assets

Pretendard 1.3.9 (font version 1.309), by Kil Hyung-jin.

- Source: https://github.com/orioncactus/pretendard
- Download: https://github.com/orioncactus/pretendard/releases/download/v1.3.9/Pretendard-1.3.9.zip, folder `public/static/alternative`

- `Pretendard-Regular.woff2`: 400
- `Pretendard-SemiBold.woff2`: 600, for the table headers and minor headings of a document PDF
- `Pretendard-Bold.woff2`: 700

The release also has Thin, ExtraLight, Light, Medium, ExtraBold and Black.

Each file is the release's static TTF stored as WOFF2 with fontTools 4.62 (`fontTools.ttLib.woff2.compress(source, target, transform_tables=set())`). Leaving the glyph tables untransformed makes the skill's first-use unpacking fast; unpacking restores every table of the release file except DSIG, which WOFF2 does not carry.

Pretendard is distributed under the SIL Open Font License 1.1. The license text from the release is `OFL.txt`.
