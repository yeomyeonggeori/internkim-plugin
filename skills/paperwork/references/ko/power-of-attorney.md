# 위임장

output: pdf
filename: 위임장_<수임인성명>_<YYYYMMDD>.pdf

## Purpose

위임인이 수임인에게 특정 권한의 행사를 맡긴다는 사실을 증명하는 대외 문서. 위임 사항은 포괄적으로 쓰지 않고 구체적인 항목으로 열거해야 한다.

## Required fields

- meta: 위임인(성명, 생년월일 또는 사업자번호, 주소), 수임인(성명, 생년월일, 주소, 연락처), 위임기간
- sections: 위임 사항(bullets, 구체적인 행위 단위로 열거)
- notes: "위와 같이 위 사람에게 권한을 위임합니다."
- signature: 위임인 본인, stamp true

## Document JSON skeleton

```json
{
  "title": "위 임 장",
  "documentNumber": "POA-<YYYYMMDD>-<순번>",
  "profile": { ...company profile... },
  "meta": [
    { "label": "위임인 성명", "value": "<위임인 성명>" },
    { "label": "위임인 생년월일/사업자번호", "value": "<YYYY-MM-DD 또는 사업자등록번호>" },
    { "label": "위임인 주소", "value": "<위임인 주소>" },
    { "label": "수임인 성명", "value": "<수임인 성명>" },
    { "label": "수임인 생년월일", "value": "<YYYY-MM-DD>" },
    { "label": "수임인 주소", "value": "<수임인 주소>" },
    { "label": "수임인 연락처", "value": "<수임인 연락처>" },
    { "label": "위임기간", "value": "<YYYY-MM-DD> ~ <YYYY-MM-DD>" }
  ],
  "sections": [
    { "title": "위임 사항", "bullets": ["<위임할 구체적 행위 1>", "<위임할 구체적 행위 2>", "<위임할 구체적 행위 3>"] }
  ],
  "notes": ["위와 같이 위 사람에게 권한을 위임합니다."],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "위임인 <성명> (인)", "stamp": true }
}
```

## Fixed wording

- notes: "위와 같이 위 사람에게 권한을 위임합니다."
- title은 "위 임 장"처럼 글자 사이 공백을 넣는다.

## Rules

- 위임 사항을 "일체의 권한을 위임함" 같은 포괄 위임으로 쓰지 말고, 위임인이 실제로 맡기려는 행위를 항목별로 구체적으로 열거한다.
- 위임인·수임인의 성명, 생년월일, 주소, 연락처, 위임기간, 위임 사항은 요청자가 제공한 사실만 사용하고 지어내지 않으며, 없으면 요청자에게 확인한다.
- 위임기간이 없으면 만료일을 지어내지 말고 요청자에게 확인한다.
