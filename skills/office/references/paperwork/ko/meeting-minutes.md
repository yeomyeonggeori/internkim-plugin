# 회의록 (Meeting Minutes)

output: pdf
filename: 회의록_<회의명>_<YYYYMMDD>.pdf

## Purpose

회의에서 논의된 안건과 결정사항, 실행 항목을 기록하는 문서. 결재 승인이 아닌 기록·공유 목적이므로 approvalLine은 사용하지 않는다.

## Required fields

- meta: 회의명, 일시, 장소, 참석자, 작성자
- sections: 안건 / 논의 내용 / 결정사항(bullets) / 실행 항목
- items: 실행 항목이 있으면 항목·담당·기한 표로 작성(없으면 생략)
- signature: 작성자 본인, stamp false
- approvalLine은 사용하지 않는다

## Document JSON skeleton

```json
{
  "title": "회 의 록",
  "documentNumber": "MM-<YYYYMMDD>-<순번>",
  "profile": { ...company profile... },
  "meta": [
    { "label": "회의명", "value": "<회의명>" },
    { "label": "일시", "value": "<YYYY-MM-DD HH:MM>" },
    { "label": "장소", "value": "<장소 또는 화상회의 링크>" },
    { "label": "참석자", "value": "<이름1, 이름2, ...>" },
    { "label": "작성자", "value": "<성명>" }
  ],
  "sections": [
    { "title": "1. 안건", "bullets": ["<안건 1>", "<안건 2>"] },
    { "title": "2. 논의 내용", "paragraphs": ["<안건별 논의 요약>"] },
    { "title": "3. 결정사항", "bullets": ["<결정사항 1>", "<결정사항 2>"] },
    { "title": "4. 실행 항목", "paragraphs": [] }
  ],
  "items": {
    "headers": ["항목", "담당", "기한"],
    "aligns": ["L", "L", "L"],
    "rows": [["<실행 항목>", "<담당자>", "<YYYY-MM-DD>"]]
  },
  "signature": { "date": "<YYYY년 M월 D일>", "line": "작성자 <성명>", "stamp": false }
}
```

## Fixed wording

- 고정 문구 없음. 회의 내용을 사실대로 요약해 각 섹션에 채운다.

## Rules

- approvalLine은 절대 추가하지 않는다.
- 실행 항목이 있으면 4번 섹션 아래 items 표(항목·담당·기한)로 작성하고, 실행 항목이 없으면 items 블록을 생략한다.
- 참석자·결정사항·담당자·기한은 요청자가 제공한 사실만 사용하고, 없는 정보는 지어내지 말고 요청자에게 확인한다.
- title은 "회 의 록"처럼 글자 사이 공백을 넣는다.
