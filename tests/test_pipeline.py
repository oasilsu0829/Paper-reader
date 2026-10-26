"""python3 -m unittest discover tests"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_report  # noqa: E402
import fetch_paper  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


class ParseInput(unittest.TestCase):
    def test_links_and_ids(self):
        cases = {
            "https://pubmed.ncbi.nlm.nih.gov/34713412/": {"pmid": "34713412"},
            "pubmed.gov/34713412": {"pmid": "34713412"},
            "https://pmc.ncbi.nlm.nih.gov/articles/PMC9046468/": {"pmcid": "PMC9046468"},
            "https://www.ncbi.nlm.nih.gov/pmc/articles/pmc9046468": {"pmcid": "PMC9046468"},
            "https://doi.org/10.1007/s12529-021-10032-y": {"doi": "10.1007/s12529-021-10032-y"},
            "34713412": {"pmid": "34713412"},
        }
        for raw, want in cases.items():
            self.assertEqual(fetch_paper.parse_input(raw), want, raw)


class ParseXml(unittest.TestCase):
    def test_pubmed(self):
        m = fetch_paper.parse_pubmed_xml((FIX / "pubmed_sample.xml").read_text())
        self.assertEqual(m["title"], "A sample trial of walking.")
        self.assertEqual(m["authors"], ["Minji Kim", "Walk Group"])
        self.assertEqual(m["year"], "2024")
        self.assertEqual(m["abstract"][0], {"label": "BACKGROUND", "text": "Walking is good."})
        self.assertEqual(m["ids"]["pmc"], "PMC0000001")
        self.assertEqual(m["ids"]["doi"], "10.1000/walk.1")

    def test_jats(self):
        j = fetch_paper.parse_jats((FIX / "jats_sample.xml").read_text())
        titles = [s["title"] for s in j["sections"]]
        self.assertEqual(titles, ["본문", "Introduction", "Methods", "Methods > Participants", "Results"])
        part = j["sections"][3]["paragraphs"]
        self.assertIn("We enrolled 40 adults.", part)
        self.assertIn("• Age 60+", part)
        self.assertEqual(j["figures"][0]["graphic"], "nihms-123-f0001")
        self.assertEqual(j["figures"][0]["caption"], "Flow CONSORT diagram.")
        t = j["tables"][0]
        self.assertEqual(t["rows"], [["Group", "n"], ["Walk", "20"], ["Control", "20"]])
        self.assertEqual(t["footnote"], "Values are counts.")
        self.assertEqual(j["reference_count"], 2)
        self.assertEqual([a["label"] for a in j["abstract_jats"]], ["Background", "Results"])

    def test_html_entities(self):
        j = fetch_paper.parse_jats('<article><body><sec><title>A</title><p>x&nbsp;y &lt; z</p></sec></body></article>')
        self.assertEqual(j["sections"][0]["paragraphs"], ["x y < z"])


class Report(unittest.TestCase):
    def test_markdown(self):
        h = build_report.md("첫 줄 **굵게** ==형광==\n\n- 하나\n- 둘\n1. 순서")
        self.assertIn("<strong>굵게</strong>", h)
        self.assertIn("<mark>형광</mark>", h)
        self.assertIn("<ul><li>하나</li><li>둘</li></ul>", h)
        self.assertIn("<ol><li>순서</li></ol>", h)
        self.assertNotIn("<script>", build_report.md("<script>x</script>"))
        self.assertIn("* p<.05, ** p<.01", build_report.inline("\\* p<.05, \\*\\* p<.01").replace("&lt;", "<"))

    def test_bars_scale(self):
        svg = build_report.block_bars({"items": [{"label": "a", "value": -0.3}, {"label": "b", "value": 0.22}]})
        self.assertIn('class="zero"', svg)
        self.assertIn(">-0.3<", svg)
        counts = build_report.block_bars({"items": [{"label": "a", "value": 53}, {"label": "b", "value": 13}]})
        self.assertNotIn(">-", counts)  # 양수만 있으면 축이 0에서 시작

    def test_build_example(self):
        ex = ROOT / "examples" / "34713412"
        if not (ex / "report.json").exists():
            self.skipTest("예시 리포트 없음")
        rep = json.loads((ex / "report.json").read_text())
        html = build_report.build(rep, ex)
        self.assertIn("<title>", html)
        self.assertNotIn("{{", html)
        for sid in ("overview", "figures", "relevance"):
            self.assertIn(f'id="{sid}"', html)

    def test_merge_paper_fills_meta_caption_and_table(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            paper = {"ids": {"pmid": "1", "doi": "10.1/x"}, "url": "https://pubmed.ncbi.nlm.nih.gov/1/",
                     "meta": {"title": "T", "authors": ["A B"], "journal": "J", "year": "2024"},
                     "fetched": "2026-01-01",
                     "figures": [{"id": "F1", "label": "Figure 1", "caption": "cap", "image": "figures/F1.jpg"}],
                     "tables": [{"id": "T1", "label": "Table 1", "caption": "tc", "rows": [["g", "n"], ["a", "1"]], "footnote": ""}]}
            (d / "paper.json").write_text(json.dumps(paper))
            rep = build_report.merge_paper({"meta": {"title_ko": "티"}, "figures": [{"label": "Figure 1"}],
                                            "tables": [{"id": "T1"}]}, d)
            self.assertEqual(rep["meta"]["doi"], "10.1/x")
            self.assertEqual(rep["meta"]["title_ko"], "티")
            self.assertEqual(rep["meta"]["read_date"], "2026-01-01")
            self.assertEqual(rep["figures"][0]["caption"], "cap")
            self.assertEqual(rep["figures"][0]["image"], "figures/F1.jpg")
            self.assertEqual(rep["tables"][0]["blocks"][0]["rows"], [["a", "1"]])

    def test_missing_image_and_embed(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "figures").mkdir()
            (d / "figures" / "f1.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
            rep = {"meta": {"title": "T"}, "figures": [
                {"id": "f1", "label": "Figure 1", "image": "figures/f1.png"},
                {"id": "f2", "label": "Figure 2"}]}
            html = build_report.build(rep, d)
            self.assertIn("data:image/png;base64,", html)
            self.assertIn("fig-missing", html)


if __name__ == "__main__":
    unittest.main()
