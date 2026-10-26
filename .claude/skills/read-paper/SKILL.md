---
name: read-paper
description: 펍메드(PubMed/PMC/DOI) 링크를 받아 초록부터 본문까지 쉽게 풀어 요약하고, 그림을 뽑아 그래프 의미를 해석하고, 사용자의 프로젝트와의 연관성까지 정리한 인터랙티브 웹 리포트를 만든다. 사용자가 pubmed.ncbi.nlm.nih.gov, pmc.ncbi.nlm.nih.gov, doi.org 링크나 PMID를 보내면 사용한다.
---

# 논문 리딩 리포트 만들기

사용자는 학생이다. 목표는 "이 리포트 하나만 읽으면 논문을 이해하고, 내 보고서나 프로젝트에 바로 쓸 수 있다"이다.
모든 설명은 한국어로 쓰고, 전문 용어는 처음 나올 때 영어 원어를 괄호로 붙인다.
**사용자는 빠른 결과를 원한다.** 아래 순서를 그대로 따르고, 적힌 것 외의 단계는 하지 않는다.

## 빠른 경로 (전체 순서)

1. **가져오기**: `python3 scripts/fetch_paper.py "<링크>"` 한 번.
   - 종료 코드 3(네트워크 차단)이면 다시 시도하지 말고 바로 커넥터로 간다. 이 세션에서 이미 차단을 확인했다면 스크립트도 건너뛴다.
   - 커넥터: `mcp__PubMed__get_article_metadata` 를 먼저 부르고, PMCID가 나오면 `mcp__PubMed__get_full_text_article`.
2. **읽기**: `paper.md`(또는 커넥터 본문)를 한 번 읽고, 그림 이미지가 있으면 각각 한 번씩 본다. `profile/my-projects.md` 를 읽는다.
3. **쓰기**: `library/<PMID>/report.json` 을 **Write 한 번**으로 쓴다. 분량 기준은 아래 표.
4. **만들기·공개·저장**: 한 메시지에서 순서대로
   `python3 scripts/build_report.py library/<PMID>` → Artifact 공개 → 커밋·푸시.
5. **답하기**: 링크, 한 줄 요약, 가장 관련 있는 프로젝트 활용법 한두 줄. 끝.

하지 않는 것: 화면 캡처나 미리보기 확인, 템플릿이나 스크립트 수정(사용자가 요청할 때만), 연관 논문 검색(사용자가 요청할 때만), 같은 내용을 채팅에 길게 다시 쓰기.

## 자동으로 채워지는 것 (쓰지 않는다)

`paper.json` 이 있으면 `build_report.py` 가 알아서 넣는다:
제목, 저자, 저널, 연도, PMID·PMCID·DOI, PubMed 링크, 읽은 날짜, 그림·표의 원문 캡션, 이미지 경로, 표 숫자(표 카드에 blocks가 없을 때).
그림·표 카드는 `paper.json` 의 `id` 나 `label` 과 같게 맞춰서 연결한다.

커넥터로 가져온 경우(`paper.json` 없음)에는 `meta` 에 `title_ko, title, authors, journal, year, pmid, pmcid, doi, url` 만 쓰고, **원문 캡션은 옮겨 쓰지 않는다.**

## 분량 기준

| 부분 | 쓰는 것 | 분량 |
|---|---|---|
| `meta` | `title_ko`, `tags` (연구 유형, 규모, 핵심 방법) | 태그 3~5개 |
| `tldr` | 한 문장, 핵심은 `==형광펜==` | 1문장 |
| `overview` | `points`, `stats` | 포인트 3~5개(각 1~2문장), 숫자 카드 3~5개 |
| `sections` | 초록 풀이, 배경, 방법, 결과, 고찰 (논문 구조에 맞춰 조정) | 섹션당 `easy` 3~6문장, `detail` 글머리표 3~6개 |
| `figures`, `tables` | 그림·표 카드 | 아래 참고 |
| `relevance` | 프로젝트 카드 | 프로젝트당 why 1~2문장, use 2~3개, cite_as 1~2개 |

**그림 카드**
- 결과를 보여 주는 그래프(핵심 그림): `kind, title_ko, what, how_to_read(2~4단계), findings(2~4개), meaning, caveat` 모두.
  처음 보는 그래프 종류면 `how_to_read` 첫 단계에서 읽는 법부터.
- 구조도, 흐름도, 사진 같은 보조 그림과 표: `kind, title_ko, what, meaning` 만.
- `detail` 은 통계적으로 짚을 게 있을 때만.

## 내용 규칙

- **숫자는 논문에 있는 것만 쓴다.** 막대 값도 본문, 표, 그림에서 읽은 값이다. 그림에서 눈으로 읽은 근삿값과 본문이 "약"으로 보고한 값은 `display` 에 `≈` 를 붙인다.
- 논문의 주장과 내 해석을 구분한다. 해석은 "~로 볼 수 있다", 논문 주장은 "저자들은 ~라고 본다". 연구의 한계는 고찰 섹션이나 그림 카드의 `caveat` 에 짧게 넣는다.
- `easy` 는 고등학생도 이해하는 수준으로, 비유를 하나씩. `detail` 은 통계 수치(r, p, OR, 95% CI, 효과크기)와 그 뜻.
- 시각화 최소 기준: 방법 섹션에 `flow`, 결과 섹션에 `bars` 또는 `table` 하나 이상, 규모는 `overview.stats`.
- 그림을 직접 볼 수 있으면 축, 단위, 집단, 오차막대, 유의성 표시, 패널을 확인하고 해석한다. 캡션만 보고 해석하지 않는다.
- 블록 종류와 필드는 `docs/report-schema.md`, 완성 예시는 `examples/34713412/report.json`.

## relevance (마지막 섹션)

- `profile/my-projects.md` 의 프로젝트마다 연관도(0~5), 이유, 활용법, 인용 문장(`cite_as`: 그대로 붙여 넣을 한국어 문장 + (저자 et al., 연도)). 연관도 2 이하는 한 줄로 쓰거나 뺀다.
- 프로필이 비어 있으면 리포트는 일반 활용법으로 먼저 만들고, 답할 때 프로젝트 주제를 물어본다. 답을 받으면 `profile/my-projects.md` 에 추가하고 이 섹션만 다시 써서 같은 경로로 다시 공개한다. 사용자의 프로젝트를 지어내지 않는다.

## 예외 상황

- **그림을 못 가져올 때** (네트워크 차단): 처음 한 번만 알린다. "그림을 가져오려면 환경 설정 > Network access 에 `eutils.ncbi.nlm.nih.gov, pmc.ncbi.nlm.nih.gov, www.ncbi.nlm.nih.gov, cdn.ncbi.nlm.nih.gov, ftp.ncbi.nlm.nih.gov, www.ebi.ac.uk, europepmc.org` 를 추가하거나, 논문 PDF나 그림 캡처를 올려 주세요."
  커넥터 본문에 캡션이 남아 있으면(숫자 뒤 캡션 문단) 캡션과 본문 수치로 그림 카드를 만들고 `missing_note` 에 원본 이미지 없이 해석했다고 적는다. `source_note` 에 이유를 한 문장으로.
- **PMCID가 없을 때** (오픈액세스 아님): 초록 기반 리포트를 만들고 태그에 `초록 기반`을 넣은 뒤, PDF를 올리면 본문까지 분석한다고 알린다.
  PDF를 받으면 `pip install pymupdf` (처음 한 번) 후 `python3 scripts/fetch_paper.py <링크> --pdf <파일>`.
- **그림 캡처를 직접 올리면** `library/<PMID>/figures/` 에 저장하고 카드의 `image` 로 쓴다.

## 공개와 저장

- Artifact: 처음엔 `icon: "book"`, `description` 은 한 문장. 같은 논문을 다시 만들면 같은 경로로 공개해 링크를 유지한다.
- 커밋 메시지: `Read: <논문 짧은 제목> (PMID <번호>)`. 현재 브랜치에 푸시.
- 커넥터를 썼다면 답에 "PubMed에서 가져온 정보"라고 밝히고 DOI 링크를 넣는다.
