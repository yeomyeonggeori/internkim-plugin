# MaruBuri Font Assets

MaruBuri (마루 부리) 2.000, by NAVER and the NAVER Cultural Foundation, designed by AG Typography Institute.

- Source: https://hangeul.naver.com/font/nanum
- Download: https://hangeul.pstatic.net/0/hangeul/2022/zip_v2/maruburi.zip, folder `OTF`

- `MaruBuri-Regular.woff2`: 400
- `MaruBuri-Bold.woff2`: 700

The release also has ExtraLight, Light and SemiBold. Its TrueType files are about 8 MB a face against 1 MB for the OpenType (CFF) ones, so the OpenType faces are shipped. Word and PowerPoint embed only TrueType outlines, so a file that names MaruBuri does not carry it.

Each file is the release's OTF stored as WOFF2 with fontTools 4.62 (`fontTools.ttLib.woff2.compress(source, target, transform_tables=set())`). Leaving the glyph tables untransformed makes the skill's first-use unpacking fast; unpacking restores every table of the release file except DSIG, which WOFF2 does not carry.

NAVER's font site lists MaruBuri among its Nanum fonts under "오픈 라이선스 (상업적 사용 허용)", and NAVER's license page for those fonts, https://help.naver.com/service/30016/contents/18088, gives the SIL Open Font License, Version 1.1. The download carries no license file, so `OFL.txt` is the OFL 1.1 text under the copyright line from the font's name table.
