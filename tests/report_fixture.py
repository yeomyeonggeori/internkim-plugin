from doc_fixture import run_office


REPORT_MARKDOWN = """# 2026년 3분기 영업 실적 보고서

작성: 이샘플 (영업기획팀) · 보고일: 2026-10-01

## 1. 요약

3분기 매출은 **42억 3,000만 원**으로 전년 동기 대비 12.4% 증가했다. 자세한 수치는 [사내 대시보드](https://dashboard.example.com)에서 확인한다.

## 2. 주요 지표

| 구분 | 2분기 | 3분기 |
| --- | --- | --- |
| 매출 | 3,820 | 4,230 |
| 영업이익 | 290 | 343 |

![분기별 매출](chart.png)

## 3. 성과 요인

- 공공 부문 수주 확대
- 기존 고객 재계약률 94%
   - 대형 고객 3곳 다년 계약 전환

## 4. 4분기 계획

1. 수도권 영업 인력 2명 충원
1. 연말 프로모션 집행
"""
CHART_IMAGE = """
from PIL import Image, ImageDraw
image = Image.new("RGB", (600, 240), (240, 244, 250))
draw = ImageDraw.Draw(image)
for index, height in enumerate((80, 140, 110, 190)):
    draw.rectangle([60 + index * 130, 220 - height, 140 + index * 130, 220], fill=(40, 90, 160))
image.save("chart.png")
"""


def pdf_text(path, working_directory):
    return "\n".join(page["text"] for page in run_office(["read", path], working_directory)["details"]["pages"])
