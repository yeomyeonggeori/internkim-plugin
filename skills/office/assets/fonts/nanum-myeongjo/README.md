# Nanum Myeongjo Font Assets

Nanum Myeongjo (나눔명조) 3.011, by NAVER, designed by FONTRIX.

- Source: https://hangeul.naver.com/font/nanum
- Download: https://hangeul.naver.com/hangeul_static/webfont/zips/nanum-myeongjo.zip

- `NanumMyeongjo.woff2`: 400
- `NanumMyeongjoBold.woff2`: 700. The file's own weight class says 600; Word and every other reader treat it as the family's Bold.

The release also has ExtraBold.

Each file is the release's TTF stored as WOFF2 with fontTools 4.62 (`fontTools.ttLib.woff2.compress(source, target, transform_tables=set())`). Leaving the glyph tables untransformed makes the skill's first-use unpacking fast; unpacking restores every table of the release file except DSIG, which WOFF2 does not carry.

NAVER's license page for the Nanum fonts, https://help.naver.com/service/30016/contents/18088, says "This Font Software is licensed under the SIL Open Font License, Version 1.1." The download carries no license file, so `OFL.txt` is the OFL 1.1 text under the copyright line that page gives.
