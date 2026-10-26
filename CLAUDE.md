# Paper Reader

학생용 논문 리딩 도구. 사용자가 펍메드/PMC/DOI 링크나 PMID를 보내면 따로 지시가 없어도
`.claude/skills/read-paper/SKILL.md` 의 순서대로 리포트를 만든다.

- 사용자의 프로젝트 정보는 `profile/my-projects.md` 에 있다. 사용자가 새 보고서나 프로젝트 이야기를 하면 이 파일에 추가한다.
- 읽은 논문은 `library/<PMID>/` 에 쌓인다. 목록은 `library/README.md` (자동 생성).
- 코드: `scripts/fetch_paper.py` (가져오기), `scripts/build_report.py` (HTML 생성), `templates/report.html` (디자인).
- 테스트: `python3 -m unittest discover tests`
- 답변과 리포트는 한국어로 쓴다.
