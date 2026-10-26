---
name: read-paper
description: 펍메드(PubMed/PMC/DOI) 링크를 받아 초록부터 본문까지 쉽게 풀어 요약하고, 그림을 뽑아 그래프 의미를 해석하고, 사용자의 프로젝트와의 연관성까지 정리한 인터랙티브 웹 리포트를 만든다. 사용자가 pubmed.ncbi.nlm.nih.gov, pmc.ncbi.nlm.nih.gov, doi.org 링크나 PMID를 보내면 사용한다.
---

# 논문 리딩 리포트 만들기

사용자는 학생이다. 목표는 "이 리포트 하나만 읽으면 논문을 이해하고, 내 보고서나 프로젝트에 바로 쓸 수 있다"이다.
모든 설명은 한국어로 쓰고, 전문 용어는 처음 나올 때 영어 원어를 괄호로 붙인다.

## 1. 논문 가져오기

```bash
python3 scripts/fetch_paper.py "<사용자가 보낸 링크>"
```

- 성공하면 `library/<PMID>/paper.json`, `paper.md`, `figures/*` 가 생긴다.
- **종료 코드 3 (네트워크 차단)** 이면 펍메드 커넥터로 대신 가져온다.
  1. `mcp__PubMed__get_article_metadata` (PMID) 로 제목, 저자, 저널, 연도, 초록, DOI, PMCID
  2. PMCID가 있으면 `mcp__PubMed__get_full_text_article` 로 본문 텍스트
  3. 커넥터 본문에는 그림, 표, 캡션이 빠져 있다. 사용자에게 한 번만 알린다:
     "그림을 가져오려면 환경 설정 > Network access 에 `eutils.ncbi.nlm.nih.gov, pmc.ncbi.nlm.nih.gov, www.ncbi.nlm.nih.gov, cdn.ncbi.nlm.nih.gov, ftp.ncbi.nlm.nih.gov, www.ebi.ac.uk, europepmc.org` 를 추가하거나, 논문 PDF나 그림 캡처를 올려 주세요."
     그리고 그림 없이 진행한다. 그림 카드는 만들지 말고 `source_note` 에 그림이 빠진 이유를 적는다.
- **PMCID가 없으면** (오픈액세스가 아니면) 초록만 있다. 사용자에게 PDF를 올려 달라고 하고,
  받으면 `python3 scripts/fetch_paper.py <링크> --pdf <파일>` (처음 한 번 `pip install pymupdf`).
  PDF가 없으면 초록 기반 리포트를 만들고 머리말 태그에 `초록 기반`을 넣는다.
- 사용자가 그림 캡처를 직접 올리면 `library/<PMID>/figures/` 에 저장해서 쓴다.

## 2. 꼼꼼히 읽기

1. `paper.md` 를 끝까지 읽는다 (길면 나눠서). 방법의 대상, 설계, 측정 도구, 통계 방법과 결과의 수치를 메모한다.
2. **모든 그림 이미지를 Read 도구로 직접 본다.** 캡션만 보고 해석하지 않는다.
   축 이름과 단위, 집단(색이나 기호), 오차막대 종류, 유의성 표시(*, p), 패널(A, B, C)을 확인한다.
   해상도 때문에 숫자가 안 읽히면 본문이나 표의 수치로 확인하고, 그래도 모르면 모른다고 쓴다.
3. 표는 `paper.md` 의 마크다운 표를 읽는다. 표가 이미지뿐이면 이미지를 본다.
4. `profile/my-projects.md` 를 읽는다.

## 3. report.json 쓰기

`library/<PMID>/report.json` 에 쓴다. 형식과 블록 종류는 `docs/report-schema.md`, 완성 예시는 `examples/34713412/report.json`.

내용 규칙:

- **숫자는 논문에 있는 것만 쓴다.** 그래프의 막대 값도 본문이나 표, 그림에서 읽은 값이다. 그림에서 눈으로 읽은 근삿값은 `display` 에 `≈` 를 붙인다.
- 논문의 주장과 내 해석을 구분한다. 해석은 "~로 볼 수 있다", 논문 주장은 "저자들은 ~라고 본다".
- `easy` 는 고등학생도 이해하는 수준으로, 비유를 하나씩 쓴다. `detail` 은 통계 수치(r, p, OR, 95% CI, 효과크기)와 그 뜻을 풀어 쓴다.
- 섹션은 보통 이 순서: 초록 풀이, 왜 이 연구를 했나(배경), 어떻게 연구했나(방법), 무엇을 찾았나(결과), 저자들의 해석(고찰), 결론. 논문 구조가 다르면 맞춘다.
- 시각화는 이해를 돕는 곳에만 넣는다. 최소한:
  - 방법 섹션에 `flow` (대상 → 측정 → 분석 → 결과 흐름)
  - 결과 섹션에 `bars` 하나 이상 (논문 수치로 그린 비교 그래프) 또는 `table`
  - 연구 대상이나 규모는 `stats`
- 그림 카드마다 `what`(무엇을 보여주나), `how_to_read`(눈을 어디서부터 어디로 옮기며 읽는지 2~5단계), `findings`(핵심 발견, 수치 포함), `meaning`(그래서 무슨 의미인지), `caveat`(오해하기 쉬운 점)를 모두 채운다.
  그래프 종류(`kind`: 막대그래프, 산점도, 생존곡선, 포레스트 플롯, 흐름도 등)를 적고, 처음 보는 그래프 종류라면 `how_to_read` 첫 단계에서 그 그래프 읽는 법부터 설명한다.
- `critique`: 연구 설계상 강점과 한계 (표본 크기, 인과관계 여부, 측정 방법, 일반화 가능성).
- `glossary`: 6~12개. `quiz`: 3~5개 (답은 본문 근거와 함께).
- `relevance` (마지막 섹션):
  - `profile/my-projects.md` 의 프로젝트마다 연관도(0~5)와 이유, 구체적 활용법을 쓴다. 연관도 2 이하는 한 줄로 짧게 쓰거나 뺀다.
  - `cite_as` 에는 보고서에 그대로 붙여 넣을 수 있는 한국어 문장을 1~2개 쓰고 (저자 et al., 연도) 인용을 붙인다.
  - 프로필이 비어 있으면 사용자에게 지금 하는 보고서나 프로젝트 주제를 물어보고, 답을 `profile/my-projects.md` 에 추가한 뒤 쓴다. 답이 없으면 `summary` 에 프로필이 비어 있다고 적고 일반적인 활용 아이디어만 쓴다. 사용자의 프로젝트를 지어내지 않는다.
  - `next`: 이어서 읽을 만한 논문을 찾고 싶으면 `mcp__PubMed__find_related_articles` 로 2~3편을 골라 링크와 함께 쓴다.

## 4. 리포트 만들기와 공유

```bash
python3 scripts/build_report.py library/<PMID>
```

1. 경고(`!`)가 나오면 고친다.
2. Artifact 도구로 `library/<PMID>/report.html` 을 공개한다 (처음엔 `icon: "book"`, `description` 에 한 문장 요약).
   같은 논문을 다시 만들면 같은 경로로 다시 공개해서 링크를 유지한다.
3. `library/<PMID>/` 를 커밋하고 현재 브랜치에 푸시한다. 커밋 메시지: `Read: <논문 짧은 제목> (PMID <번호>)`.
4. 사용자에게 답할 때: 리포트 링크, 한 줄 요약, 가장 연관도 높은 프로젝트와 활용법 한두 줄.
   펍메드 커넥터를 썼다면 "PubMed에서 가져온 정보"라고 밝히고 DOI 링크를 넣는다.
