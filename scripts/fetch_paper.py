#!/usr/bin/env python3
"""펍메드 링크(또는 PMID/PMCID/DOI)로 논문 메타데이터, 본문, 그림, 표를 내려받는다.

    python3 scripts/fetch_paper.py https://pubmed.ncbi.nlm.nih.gov/34713412/
    python3 scripts/fetch_paper.py PMC9046468
    python3 scripts/fetch_paper.py 34713412 --pdf ~/Downloads/paper.pdf

결과는 library/<PMID>/ 에 저장된다.
    paper.json   구조화된 원자료 (메타데이터, 초록, 섹션, 그림, 표)
    paper.md     사람이/Claude가 읽기 좋은 요약본
    figures/     그림 이미지 파일

표준 라이브러리만 사용한다. --pdf 옵션만 PyMuPDF(pip install pymupdf)가 필요하다.
"""
import argparse
import io
import json
import os
import re
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "library"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
UA = "paper-reader/1.0 (student reading tool)"
HOSTS = [
    "eutils.ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov", "www.ncbi.nlm.nih.gov",
    "cdn.ncbi.nlm.nih.gov", "ftp.ncbi.nlm.nih.gov", "www.ebi.ac.uk", "europepmc.org",
]
XLINK = "{http://www.w3.org/1999/xlink}href"


class NetworkBlocked(Exception):
    pass


# ---------------------------------------------------------------- 입력 해석

def parse_input(raw):
    """링크나 ID에서 {'pmid'|'pmcid'|'doi': 값} 을 뽑는다."""
    s = raw.strip()
    m = re.search(r"(PMC\d+)", s, re.I)
    if m:
        return {"pmcid": m.group(1).upper()}
    m = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", s)
    if m:
        return {"pmid": m.group(1)}
    m = re.search(r"(10\.\d{4,9}/[^\s?#]+)", s)
    if m:
        return {"doi": urllib.parse.unquote(m.group(1)).rstrip(".")}
    m = re.search(r"(?:^|[^\d])(\d{5,9})(?:$|[^\d])", s)
    if m:
        return {"pmid": m.group(1)}
    raise SystemExit(f"펍메드 링크나 PMID/PMCID/DOI를 알아볼 수 없습니다: {raw}")


# ---------------------------------------------------------------- 네트워크

def http_get(url, binary=False, retries=2):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                data = r.read()
                return data if binary else data.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (403, 407) and "Tunnel" in str(e.reason):
                raise NetworkBlocked(url)
            if e.code == 404:
                return None
            last = e
        except urllib.error.URLError as e:
            msg = str(e.reason)
            if "403" in msg or "Tunnel" in msg or "Name or service" in msg or "getaddrinfo" in msg:
                raise NetworkBlocked(url)
            last = e
        except (TimeoutError, ConnectionError) as e:
            last = e
        time.sleep(2 ** attempt)
    print(f"  ! 요청 실패: {url} ({last})", file=sys.stderr)
    return None


def eutils(path, **params):
    params.setdefault("tool", "paper-reader")
    if os.environ.get("NCBI_API_KEY"):
        params["api_key"] = os.environ["NCBI_API_KEY"]
    return http_get(f"{EUTILS}/{path}?{urllib.parse.urlencode(params)}")


# ---------------------------------------------------------------- ID 변환

def resolve_ids(ids):
    """PMID, PMCID, DOI 중 아는 것으로 나머지를 채운다."""
    if "pmid" in ids and "pmcid" in ids:
        return ids
    if "doi" in ids and "pmid" not in ids:
        x = eutils("esearch.fcgi", db="pubmed", term=f"{ids['doi']}[doi]", retmode="json")
        if x:
            hits = json.loads(x)["esearchresult"].get("idlist", [])
            if hits:
                ids["pmid"] = hits[0]
    if "pmcid" in ids and "pmid" not in ids:
        x = eutils("esummary.fcgi", db="pmc", id=ids["pmcid"].replace("PMC", ""), retmode="json")
        if x:
            res = json.loads(x).get("result", {})
            for uid in res.get("uids", []):
                for a in res[uid].get("articleids", []):
                    if a.get("idtype") == "pmid" and a.get("value", "0") != "0":
                        ids["pmid"] = a["value"]
                    if a.get("idtype") == "doi":
                        ids.setdefault("doi", a["value"])
    return ids


# ---------------------------------------------------------------- 텍스트 유틸

BLOCK_TAGS = {"p", "title", "label", "list-item", "sec", "td", "th", "tr", "caption", "AbstractText"}


def text_of(el):
    """요소의 글자만 모은다. 문단처럼 덩어리진 하위 요소 사이에는 공백을 넣는다."""
    if el is None:
        return ""
    parts = []

    def rec(e):
        if e.text:
            parts.append(e.text)
        for c in e:
            rec(c)
            if isinstance(c.tag, str) and c.tag in BLOCK_TAGS:
                parts.append(" ")
            if c.tail:
                parts.append(c.tail)

    rec(el)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def safe_xml(xml):
    """DOCTYPE을 지우고 XML에 정의되지 않은 HTML 엔티티(&nbsp; 등)를 문자로 바꾼다."""
    import html as _html
    xml = re.sub(r"<!DOCTYPE[^>]*>", "", xml, count=1)
    return re.sub(r"&([A-Za-z][A-Za-z0-9]*);",
                  lambda m: m.group(0) if m.group(1) in ("amp", "lt", "gt", "quot", "apos") else _html.unescape(m.group(0)),
                  xml)


def strip_ns(root):
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag and not el.tag.startswith("{http://www.w3.org/1999/xlink"):
            el.tag = el.tag.split("}", 1)[1]
    return root


# ---------------------------------------------------------------- PubMed 메타데이터

def parse_pubmed_xml(xml):
    root = ET.fromstring(safe_xml(xml))
    art = root.find(".//PubmedArticle")
    if art is None:
        return None
    a = art.find(".//Article")
    meta = {
        "title": text_of(a.find("ArticleTitle")),
        "journal": text_of(a.find("Journal/Title")),
        "journal_abbrev": text_of(a.find("Journal/ISOAbbreviation")),
        "year": "",
        "authors": [],
        "affiliations": [],
        "abstract": [],
        "keywords": [text_of(k) for k in art.findall(".//KeywordList/Keyword")],
        "mesh": [text_of(m.find("DescriptorName")) for m in art.findall(".//MeshHeading")],
        "publication_types": [text_of(p) for p in a.findall("PublicationTypeList/PublicationType")],
        "ids": {},
    }
    y = a.find("Journal/JournalIssue/PubDate/Year")
    md = a.find("Journal/JournalIssue/PubDate/MedlineDate")
    meta["year"] = text_of(y) if y is not None else (text_of(md)[:4] if md is not None else "")
    for au in a.findall("AuthorList/Author"):
        name = " ".join(x for x in [text_of(au.find("ForeName")), text_of(au.find("LastName"))] if x)
        if not name:
            name = text_of(au.find("CollectiveName"))
        if name:
            meta["authors"].append(name)
        for af in au.findall("AffiliationInfo/Affiliation"):
            t = text_of(af)
            if t and t not in meta["affiliations"]:
                meta["affiliations"].append(t)
    for ab in a.findall("Abstract/AbstractText"):
        meta["abstract"].append({"label": ab.get("Label") or ab.get("NlmCategory") or "", "text": text_of(ab)})
    for aid in art.findall(".//PubmedData/ArticleIdList/ArticleId"):
        meta["ids"][aid.get("IdType")] = (aid.text or "").strip()
    return meta


# ---------------------------------------------------------------- JATS 본문 파싱

def table_rows(tw):
    rows = []
    for tr in tw.iter("tr"):
        cells = []
        for c in tr:
            if c.tag in ("td", "th"):
                cells.append(text_of(c))
        if cells:
            rows.append(cells)
    return rows


def parse_sections(body):
    out = []

    def walk(sec, depth, prefix):
        title = text_of(sec.find("title"))
        paras = []
        for child in sec:
            if child.tag == "p":
                paras.append(text_of(child))
            elif child.tag in ("list",):
                paras.extend("• " + text_of(li) for li in child.iter("list-item"))
            elif child.tag == "disp-quote":
                paras.append("> " + text_of(child))
        name = (prefix + " > " + title) if prefix and title else (title or prefix)
        out.append({"title": name or "(제목 없음)", "depth": depth, "paragraphs": [p for p in paras if p]})
        for sub in sec.findall("sec"):
            walk(sub, depth + 1, name)

    # 섹션 없이 문단만 있는 본문
    loose = [text_of(p) for p in body.findall("p")]
    if loose:
        out.append({"title": "본문", "depth": 0, "paragraphs": loose})
    for sec in body.findall("sec"):
        walk(sec, 0, "")
    return out


def parse_jats(xml):
    root = strip_ns(ET.fromstring(safe_xml(xml)))
    art = root if root.tag == "article" else root.find(".//article")
    if art is None:
        return None
    result = {"sections": [], "figures": [], "tables": [], "abstract_jats": [], "reference_count": 0}
    front = art.find("front")
    if front is not None:
        for ab in front.findall(".//abstract"):
            if ab.get("abstract-type") in ("graphical", "teaser"):
                continue
            secs = ab.findall("sec")
            if secs:
                for s in secs:
                    result["abstract_jats"].append({"label": text_of(s.find("title")),
                                                    "text": " ".join(text_of(p) for p in s.findall("p"))})
            else:
                result["abstract_jats"].append({"label": "", "text": " ".join(text_of(p) for p in ab.findall("p"))})
            break
    body = art.find("body")
    if body is not None:
        result["sections"] = parse_sections(body)
    for i, fig in enumerate(art.iter("fig"), 1):
        g = fig.find(".//graphic")
        result["figures"].append({
            "id": fig.get("id") or f"fig{i}",
            "label": text_of(fig.find("label")) or f"Figure {i}",
            "caption": text_of(fig.find("caption")),
            "graphic": g.get(XLINK) if g is not None else None,
        })
    for i, tw in enumerate(art.iter("table-wrap"), 1):
        g = tw.find(".//graphic")
        result["tables"].append({
            "id": tw.get("id") or f"tbl{i}",
            "label": text_of(tw.find("label")) or f"Table {i}",
            "caption": text_of(tw.find("caption")),
            "footnote": text_of(tw.find("table-wrap-foot")),
            "rows": table_rows(tw),
            "graphic": g.get(XLINK) if g is not None else None,
        })
    back = art.find("back")
    if back is not None:
        result["reference_count"] = len(back.findall(".//ref"))
    return result


# ---------------------------------------------------------------- 그림 다운로드

def find_pmc_image_urls(pmcid):
    """PMC 기사 페이지에서 그림 원본 URL들을 모은다 (cdn.ncbi.nlm.nih.gov/pmc/blobs/...)."""
    html = http_get(f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/")
    if not html:
        return []
    urls = re.findall(r'(https://cdn\.ncbi\.nlm\.nih\.gov/pmc/blobs/[^"\'\s>]+?\.(?:jpe?g|png|gif))', html)
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def oa_package_images(pmcid):
    """오픈액세스 패키지(tar.gz)에서 이미지 파일을 {파일명(확장자 제외): bytes} 로 꺼낸다."""
    x = http_get(f"https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={pmcid}")
    if not x:
        return {}
    m = re.search(r'format="tgz"[^>]*href="([^"]+)"', x)
    if not m:
        return {}
    url = m.group(1).replace("ftp://", "https://")
    data = http_get(url, binary=True)
    if not data:
        return {}
    imgs = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for mem in tar.getmembers():
            name = mem.name.rsplit("/", 1)[-1]
            if mem.isfile() and re.search(r"\.(jpe?g|png|gif)$", name, re.I):
                f = tar.extractfile(mem)
                if f:
                    imgs[name.rsplit(".", 1)[0]] = (name.rsplit(".", 1)[1].lower(), f.read())
    return imgs


def download_figures(pmcid, items, outdir):
    """그림(과 이미지로만 제공되는 표)을 내려받아 items[i]['image'] 에 상대경로를 적는다."""
    targets = [it for it in items if it.get("graphic")]
    if not targets:
        return
    outdir.mkdir(parents=True, exist_ok=True)
    page_urls = None
    package = None
    for n, it in enumerate(targets, 1):
        g = it["graphic"]
        base = g.rsplit("/", 1)[-1]
        stem = re.sub(r"\.(jpe?g|png|gif|tiff?)$", "", base, flags=re.I)
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", it["id"]) or f"fig{n}"
        data, ext, src = None, "jpg", None
        # 1) Europe PMC 이미지 경로
        for e in ("jpg", "gif", "png"):
            u = f"https://europepmc.org/articles/{pmcid}/bin/{stem}.{e}"
            d = http_get(u, binary=True, retries=0)
            if d and len(d) > 2000 and not d.lstrip().startswith(b"<"):
                data, ext, src = d, e, u
                break
        # 2) PMC 기사 페이지의 CDN 이미지
        if data is None:
            if page_urls is None:
                page_urls = find_pmc_image_urls(pmcid)
            for u in page_urls:
                if stem in u:
                    d = http_get(u, binary=True)
                    if d:
                        data, ext, src = d, u.rsplit(".", 1)[-1].lower(), u
                        break
        # 3) 오픈액세스 패키지
        if data is None:
            if package is None:
                package = oa_package_images(pmcid)
            if stem in package:
                ext, data = package[stem]
                src = "PMC OA package"
        if data is None:
            print(f"  ! 이미지를 찾지 못함: {it['label']} ({g})", file=sys.stderr)
            continue
        fname = f"{safe}.{'jpg' if ext == 'jpeg' else ext}"
        (outdir / fname).write_bytes(data)
        it["image"] = f"figures/{fname}"
        it["image_source"] = src
        print(f"  ✓ {it['label']} → figures/{fname}")


# ---------------------------------------------------------------- PDF (선택)

def from_pdf(pdf_path, outdir):
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise SystemExit("PDF 처리에는 PyMuPDF가 필요합니다: pip install pymupdf")
    doc = fitz.open(pdf_path)
    figdir = outdir / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    pages, figures = [], []
    cap_re = re.compile(r"^\s*(Fig(?:ure)?\.?\s*\d+[A-Za-z]?|Table\s*\d+)[.:|\s]", re.I)
    for pno, page in enumerate(doc, 1):
        text = page.get_text("text")
        pages.append({"title": f"PDF {pno}쪽", "depth": 0, "paragraphs": [p.strip() for p in text.split("\n\n") if p.strip()]})
        caps = []
        for b in page.get_text("blocks"):
            t = re.sub(r"\s+", " ", b[4]).strip()
            m = cap_re.match(t)
            if m:
                caps.append((m.group(1), t))
        n = 0
        for img in page.get_images(full=True):
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.width < 250 or pix.height < 180:
                    continue
                if pix.n - pix.alpha >= 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                n += 1
                name = f"p{pno}_img{n}.png"
                pix.save(str(figdir / name))
                figures.append({"id": f"p{pno}_img{n}", "label": f"{pno}쪽 이미지 {n}",
                                "caption": " / ".join(c[1] for c in caps), "image": f"figures/{name}",
                                "graphic": None, "source": "pdf-embedded"})
            except Exception as e:  # 손상되었거나 특이한 이미지 형식
                print(f"  ! {pno}쪽 이미지 추출 실패: {e}", file=sys.stderr)
        if caps:
            # 벡터로 그려진 그래프는 이미지로 추출되지 않으므로 쪽 전체를 렌더링한다
            name = f"page{pno}.png"
            page.get_pixmap(dpi=150).save(str(figdir / name))
            for label, cap in caps:
                figures.append({"id": re.sub(r"\W+", "", label).lower() + f"_p{pno}", "label": label,
                                "caption": cap, "image": f"figures/{name}", "graphic": None, "source": "pdf-page"})
    return pages, figures


# ---------------------------------------------------------------- 출력

def write_markdown(paper, path):
    m = paper["meta"]
    L = [f"# {m.get('title','')}", ""]
    L.append(f"- 저자: {', '.join(m.get('authors', [])[:8])}{' 외' if len(m.get('authors', [])) > 8 else ''}")
    L.append(f"- 저널: {m.get('journal','')} ({m.get('year','')})")
    L.append(f"- PMID: {paper['ids'].get('pmid','-')} · PMCID: {paper['ids'].get('pmcid','-')} · DOI: {paper['ids'].get('doi','-')}")
    if m.get("publication_types"):
        L.append(f"- 유형: {', '.join(m['publication_types'])}")
    if m.get("keywords"):
        L.append(f"- 키워드: {', '.join(m['keywords'])}")
    L.append(f"- 본문 확보: {'예' if paper['fulltext_available'] else '아니오 (초록만)'}")
    L += ["", "## Abstract", ""]
    for ab in paper["abstract"]:
        L.append(f"**{ab['label']}** {ab['text']}" if ab["label"] else ab["text"])
        L.append("")
    for s in paper["sections"]:
        L += [f"{'#' * min(2 + s['depth'], 6)} {s['title']}", ""]
        for p in s["paragraphs"]:
            L += [p, ""]
    if paper["figures"]:
        L += ["## Figures", ""]
        for f in paper["figures"]:
            L.append(f"- **{f['label']}** [{f.get('image') or '이미지 없음'}] {f['caption']}")
        L.append("")
    if paper["tables"]:
        L += ["## Tables", ""]
        for t in paper["tables"]:
            L += [f"### {t['label']} {t['caption']}", ""]
            rows = t.get("rows") or []
            if rows:
                w = max(len(r) for r in rows)
                rows = [r + [""] * (w - len(r)) for r in rows]
                L.append("| " + " | ".join(rows[0]) + " |")
                L.append("|" + "---|" * w)
                for r in rows[1:]:
                    L.append("| " + " | ".join(c.replace("|", "/") for c in r) + " |")
            elif t.get("image"):
                L.append(f"(표가 이미지로만 제공됨: {t['image']})")
            if t.get("footnote"):
                L += ["", f"_{t['footnote']}_"]
            L.append("")
    path.write_text("\n".join(L), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="펍메드/PMC 링크, PMID, PMCID 또는 DOI")
    ap.add_argument("--pdf", help="본문이 PMC에 없을 때 쓸 논문 PDF 파일")
    ap.add_argument("--out", help="저장 폴더 (기본: library/<PMID>)")
    args = ap.parse_args()

    ids = parse_input(args.source)
    print(f"입력 해석: {ids}")
    try:
        ids = resolve_ids(ids)
        meta = None
        if "pmid" in ids:
            x = eutils("efetch.fcgi", db="pubmed", id=ids["pmid"], retmode="xml")
            meta = parse_pubmed_xml(x) if x else None
            if meta:
                ids.setdefault("doi", meta["ids"].get("doi"))
                if meta["ids"].get("pmc"):
                    ids.setdefault("pmcid", meta["ids"]["pmc"])
        jats = None
        if ids.get("pmcid"):
            x = http_get(f"{EUROPEPMC}/{ids['pmcid']}/fullTextXML")
            jats = parse_jats(x) if x and x.lstrip().startswith("<") else None
            if not jats or not jats["sections"]:
                x = eutils("efetch.fcgi", db="pmc", id=ids["pmcid"].replace("PMC", ""), retmode="xml")
                j2 = parse_jats(x) if x else None
                if j2 and (j2["sections"] or not jats):
                    jats = j2
    except NetworkBlocked as e:
        print("\n네트워크가 막혀 있어 논문 서버에 접속할 수 없습니다.", file=sys.stderr)
        print(f"  막힌 주소: {e}", file=sys.stderr)
        print("  Claude 환경 설정 > Network access 에 다음 도메인을 허용하세요:", file=sys.stderr)
        print("  " + ", ".join(HOSTS), file=sys.stderr)
        print("  (그동안 Claude는 펍메드 커넥터로 본문 텍스트만 가져와 리포트를 만들 수 있습니다.)", file=sys.stderr)
        sys.exit(3)

    key = ids.get("pmid") or ids.get("pmcid") or re.sub(r"\W+", "_", ids.get("doi", "paper"))
    outdir = Path(args.out) if args.out else LIBRARY / key
    outdir.mkdir(parents=True, exist_ok=True)

    paper = {
        "ids": {k: v for k, v in ids.items() if v},
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{ids['pmid']}/" if ids.get("pmid") else args.source,
        "meta": meta or {"title": "", "authors": [], "journal": "", "year": ""},
        "abstract": (meta or {}).get("abstract") or (jats or {}).get("abstract_jats") or [],
        "sections": (jats or {}).get("sections", []),
        "figures": (jats or {}).get("figures", []),
        "tables": (jats or {}).get("tables", []),
        "reference_count": (jats or {}).get("reference_count", 0),
        "fulltext_available": bool(jats and jats["sections"]),
        "fetched": time.strftime("%Y-%m-%d"),
    }
    if ids.get("pmcid") and (paper["figures"] or paper["tables"]):
        print("그림 내려받는 중…")
        try:
            download_figures(ids["pmcid"], paper["figures"] + paper["tables"], outdir / "figures")
        except NetworkBlocked as e:
            print(f"  ! 그림 서버가 막혀 있음: {e}", file=sys.stderr)
    if args.pdf:
        print("PDF 처리 중…")
        pages, figs = from_pdf(args.pdf, outdir)
        if not paper["fulltext_available"]:
            paper["sections"] = pages
            paper["fulltext_available"] = True
            paper["fulltext_source"] = "pdf"
        if not any(f.get("image") for f in paper["figures"]):
            paper["figures"] = figs

    (outdir / "paper.json").write_text(json.dumps(paper, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(paper, outdir / "paper.md")
    nimg = sum(1 for f in paper["figures"] + paper["tables"] if f.get("image"))
    print(f"\n저장: {outdir.relative_to(ROOT) if outdir.is_relative_to(ROOT) else outdir}")
    print(f"  제목: {paper['meta'].get('title','')[:90]}")
    print(f"  본문: {'있음' if paper['fulltext_available'] else '없음 (초록만, PDF를 --pdf 로 주면 본문/그림 분석 가능)'}")
    print(f"  섹션 {len(paper['sections'])}개 · 그림 {len(paper['figures'])}개 · 표 {len(paper['tables'])}개 · 이미지 파일 {nimg}개")


if __name__ == "__main__":
    main()
