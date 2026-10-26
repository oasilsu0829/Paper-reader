# Paper Reader

펍메드 링크 하나를 보내면 논문을 읽기 쉬운 웹 리포트로 만들어 주는 도구입니다.

- **초록부터 본문까지** 섹션별로 쉽게 풀어 씁니다. "쉽게 / 자세히" 버튼으로 설명 깊이를 바꿀 수 있습니다.
- **시각화**: 연구 흐름도, 논문 수치로 다시 그린 그래프, 핵심 숫자 카드.
- **그림 해석**: 논문 그림을 뽑아서 무엇을 보여주는지, 어디부터 읽는지, 핵심 발견, 의미, 주의할 점을 정리합니다. 그림은 눌러서 크게 볼 수 있습니다.
- **내 프로젝트와 연결**: `profile/my-projects.md` 에 적어 둔 보고서나 프로젝트마다 연관도, 활용법, 보고서에 바로 붙여 넣을 인용 문장을 만듭니다.

## 쓰는 법

1. Claude(이 저장소가 연결된 Claude Code 세션)에 펍메드 링크를 보냅니다.
   ```
   https://pubmed.ncbi.nlm.nih.gov/34713412/
   ```
2. Claude가 논문을 가져와 읽고 리포트를 만들어 링크로 줍니다. 리포트는 `library/<PMID>/report.html` 에도 저장됩니다.
3. 처음 한 번은 `profile/my-projects.md` 에 지금 하는 보고서나 프로젝트를 적어 두세요. 비어 있으면 Claude가 물어봅니다.

예시 리포트: [`examples/34713412/report.html`](examples/34713412/report.html)

### 그림까지 가져오려면 (클라우드 세션)

Claude 클라우드 환경은 기본 네트워크 설정에서 펍메드 서버를 막을 수 있습니다. 그럴 때는 본문 텍스트만 펍메드 커넥터로 가져오고 그림은 빠집니다.
환경 설정 > **Network access** 의 허용 도메인에 아래를 추가하면 그림도 가져옵니다.

```
eutils.ncbi.nlm.nih.gov, pmc.ncbi.nlm.nih.gov, www.ncbi.nlm.nih.gov, cdn.ncbi.nlm.nih.gov,
ftp.ncbi.nlm.nih.gov, www.ebi.ac.uk, europepmc.org
```

설정 방법: https://code.claude.com/docs/en/cloud-environments#network-access

### 오픈액세스가 아닌 논문

PMC에 본문이 없는 논문은 초록만 가져올 수 있습니다. 학교 도서관 등에서 받은 PDF를 올리면 본문과 그림까지 분석합니다.

```bash
pip install pymupdf
python3 scripts/fetch_paper.py https://pubmed.ncbi.nlm.nih.gov/<PMID>/ --pdf paper.pdf
```

## 직접 실행

```bash
python3 scripts/fetch_paper.py <링크|PMID|PMCID|DOI>   # library/<PMID>/paper.json, paper.md, figures/
# report.json 작성 (형식: docs/report-schema.md)
python3 scripts/build_report.py library/<PMID>           # library/<PMID>/report.html
python3 -m unittest discover tests                        # 테스트
```

Python 3.9 이상, 표준 라이브러리만 씁니다 (PDF 처리만 PyMuPDF 필요).
NCBI 요청이 많으면 `NCBI_API_KEY` 환경변수를 설정하세요.

## 구조

```
.claude/skills/read-paper/SKILL.md   Claude가 따르는 작업 순서와 작성 규칙
profile/my-projects.md               내 보고서, 프로젝트 목록
scripts/fetch_paper.py               PubMed / Europe PMC / PMC에서 메타데이터, 본문, 그림, 표 수집
scripts/build_report.py              report.json → 그림이 들어간 HTML 한 파일
templates/report.html                리포트 디자인 (라이트/다크, 모바일 대응)
docs/report-schema.md                report.json 형식
library/                             읽은 논문들
examples/                            예시 리포트
```
