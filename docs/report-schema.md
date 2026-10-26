# report.json 형식

`scripts/build_report.py` 가 읽는 파일이다. 모든 글 필드는 간단한 마크다운을 쓸 수 있다:
`**굵게**`, `*기울임*`, `==형광펜==`, `` `코드` ``, `[링크](https://...)`, 빈 줄로 문단 구분, `- ` 글머리표, `1. ` 번호 목록.
필드는 대부분 선택이다. 없는 섹션은 리포트와 목차에서 빠진다.

같은 폴더에 `paper.json`(fetch_paper.py 결과)이 있으면 `build_report.py` 가 다음을 자동으로 채운다. report.json 에 쓰지 않아도 된다.
`meta` 의 title, authors, journal, year, pmid, pmcid, doi, url, read_date / 그림·표 카드의 caption, image, 표 숫자(blocks가 없을 때).
카드는 `id` 나 `label` 이 paper.json 과 같아야 연결된다.

```jsonc
{
  "page_title": "HIV 여성의 긍정 요인",        // 브라우저 탭과 갤러리 이름 (2~4단어)
  "meta": {
    "title": "원문 영어 제목",
    "title_ko": "한국어로 풀어 쓴 제목",
    "authors": ["Leslie R Brody", "..."],
    "journal": "Int J Behav Med",
    "year": "2021",
    "pmid": "34713412", "pmcid": "PMC9046468", "doi": "10.1007/...",
    "url": "https://pubmed.ncbi.nlm.nih.gov/34713412/",
    "read_date": "2026-10-26",
    "tags": ["혼합연구", "n=98", "상관분석"]       // 연구 유형, 규모, 핵심 방법 등
  },
  "tldr": "한 줄 요약. ==가장 중요한 부분==은 형광펜.",
  "overview": {
    "points": ["핵심 1", "핵심 2", "핵심 3"],       // 3~5개
    "stats": [{"value": "98명", "label": "참여자", "note": "평균 45세"}],
    "easy": "...", "detail": "...", "blocks": []
  },
  "sections": [
    {
      "id": "abstract",                 // 영문 소문자, 링크 앵커로 쓰임
      "kicker": "초록",                  // 제목 위 작은 라벨
      "title": "초록을 쉽게 풀면",
      "easy": "항상 보이는 쉬운 설명",
      "detail": "'자세히' 모드에서 추가로 보이는 설명 (통계, 수치)",
      "blocks": [ /* 아래 블록들 */ ]
    }
  ],
  "figures_intro": "그림 섹션 맨 앞 안내 (선택)",
  "figures": [
    {
      "id": "fig1",
      "label": "Figure 1",
      "kind": "막대그래프",
      "image": "figures/F1.jpg",          // report.json 기준 상대경로. 없으면 '이미지 없음' 안내가 나옴
      "missing_note": "이미지가 없을 때 보여 줄 문장 (false면 안내 숨김)",
      "title_ko": "그림 제목을 한국어로",
      "caption": "원문 캡션 (접어서 보여 줌)",
      "what": "무엇을 보여주나",
      "how_to_read": ["1단계", "2단계"],
      "findings": ["발견 1 (수치 포함)", "발견 2"],
      "meaning": "그래서 무슨 의미인지",
      "caveat": "해석할 때 주의할 점",
      "detail": "'자세히' 모드 추가 설명",
      "blocks": []                         // 예: 본문 수치로 다시 그린 bars
    }
  ],
  "tables": [ /* figures 와 같은 형식. 보통 image 대신 blocks 에 table */ ],
  "relevance": {
    "title": "내 프로젝트에 어떻게 쓸까",
    "summary": "전체 요약",
    "projects": [
      {
        "name": "프로젝트 이름",
        "fit": 4,                          // 0~5
        "why": "왜 관련 있나",
        "use": ["활용법 1", "활용법 2"],
        "cite_as": ["보고서에 붙여 넣을 문장 (Brody et al., 2021)."]
      }
    ],
    "next": ["다음에 할 일이나 이어 읽을 논문"]
  },
  "source_note": "출처 아래 덧붙일 말 (예: 그림을 가져오지 못한 이유)"
}
```

## 블록

`sections[].blocks`, `overview.blocks`, `figures[].blocks` 에 넣는다.

| type | 필드 | 쓰는 곳 |
|---|---|---|
| `flow` | `title?`, `steps: [{title, desc}]`, `edges?: ["화살표 라벨"]`, `caption?` | 연구 설계, 인과 모델, 절차 |
| `bars` | `title?`, `unit?`, `min?`, `max?`, `items: [{label, value, display?, note?, highlight?, tone?}]`, `caption?` | 논문 수치 비교. 음수(상관계수)도 됨. `highlight: true` 인 막대만 강조색, `tone`: `good`/`warn`/`muted` |
| `stats` | `items: [{value, label, note?}]` | 표본 수, 기간 같은 큰 숫자 |
| `table` | `title?`, `headers`, `rows`, `caption?` | 표를 단순하게 다시 정리 |
| `compare` | `title?`, `left: {title, items}`, `right: {title, items}` | 두 집단, 가설과 결과 비교 |
| `callout` | `title?`, `text`, `tone?: "warn"` | 꼭 짚을 점, 흔한 오해 |
| `list` | `items` | 글머리표 |
| `text` | `text` | 문단 |
| `mermaid` | `code`, `caption?` | 복잡한 관계도. 공개된 Artifact에서만 그려지고 로컬 파일에선 코드로 보임 |
