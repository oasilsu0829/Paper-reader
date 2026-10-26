#!/usr/bin/env python3
"""report.json(Claude가 쓴 해설)을 한 장짜리 웹 리포트(report.html)로 만든다.

    python3 scripts/build_report.py library/34713412

- 그림 이미지는 HTML 안에 넣어(base64) 파일 하나로 열리고 공유된다.
- library/README.md 의 읽은 논문 목록도 함께 갱신한다.
- 같은 폴더에 paper.json 이 있으면 서지 정보, 캡션, 이미지, 표 숫자를 자동으로 채운다.
- report.json 형식은 docs/report-schema.md 참고.
"""
import base64
import html
import json
import math
import mimetypes
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "report.html"
MAX_IMAGE_BYTES = 3_000_000


def esc(s):
    return html.escape(str(s or ""), quote=True)


# ---------------------------------------------------------------- 마크다운 (필요한 만큼만)

def inline(s):
    s = esc(s).replace("\\*", "\x00")  # \* 는 별표 그대로
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"==(.+?)==", r"<mark>\1</mark>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    return s.replace("\x00", "*")


def md(text):
    """문단, 글머리표(- ), 번호 목록(1. ), 굵게, 형광펜(==), 링크를 지원한다."""
    if not text:
        return ""
    if isinstance(text, list):
        text = "\n".join(f"- {t}" for t in text)
    out, para, lst, kind = [], [], [], None

    def flush():
        nonlocal para, lst, kind
        if para:
            out.append("<p>" + "<br>".join(inline(x) for x in para) + "</p>")
            para = []
        if lst:
            out.append(f"<{kind}>" + "".join(f"<li>{inline(x)}</li>" for x in lst) + f"</{kind}>")
            lst, kind = [], None

    for line in str(text).splitlines():
        s = line.strip()
        m_ul = re.match(r"^[-•*]\s+(.*)", s)
        m_ol = re.match(r"^\d+[.)]\s+(.*)", s)
        if not s:
            flush()
        elif m_ul or m_ol:
            k = "ul" if m_ul else "ol"
            if para or (kind and kind != k):
                flush()
            kind = k
            lst.append((m_ul or m_ol).group(1))
        else:
            if lst:
                flush()
            para.append(s)
    flush()
    return "\n".join(out)


# ---------------------------------------------------------------- 시각화 블록

def nice_step(span, target=5):
    raw = span / max(target, 1)
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def text_width(s, size=13):
    """SVG 글자 폭 어림값 (한글은 글자 크기만큼, 라틴 문자는 그 절반 남짓)."""
    return sum(size if ord(c) > 0x1100 else size * 0.58 for c in s)


def fmt_num(v):
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.2f}".rstrip("0").rstrip(".")


def block_bars(b):
    items = b.get("items") or []
    if not items:
        return ""
    vals = [float(i["value"]) for i in items]
    lo = min([0.0] + vals + ([float(b["min"])] if "min" in b else []))
    hi = max([0.0] + vals + ([float(b["max"])] if "max" in b else []))
    if hi == lo:
        hi = lo + 1
    step = nice_step(hi - lo)
    lo = math.floor(lo / step + 1e-9) * step
    hi = math.ceil(hi / step - 1e-9) * step
    unit = b.get("unit", "")
    longest = max(len(str(i.get("display") or (fmt_num(float(i["value"])) + unit))) for i in items)
    W, ROW, TOP = 640, 30, 6
    LW = min(270, max(110, max(text_width(str(i.get("label", ""))) for i in items) + 18))
    VW = max(64, 16 + 7 * longest)
    x0, x1 = LW, W - VW
    H = TOP + ROW * len(items) + 26

    def X(v):
        return x0 + (v - lo) / (hi - lo) * (x1 - x0)

    any_hl = any(i.get("highlight") for i in items)
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(b.get("title", "막대그래프"))}">']
    t = lo
    while t <= hi + 1e-9:
        x = X(t)
        parts.append(f'<line class="grid" x1="{x:.1f}" x2="{x:.1f}" y1="{TOP}" y2="{H - 22}"/>')
        parts.append(f'<text class="tick" x="{x:.1f}" y="{H - 6}" text-anchor="middle">{fmt_num(t)}</text>')
        t += step
    for n, it in enumerate(items):
        v = float(it["value"])
        y = TOP + n * ROW
        xa, xb = sorted((X(0), X(v)))
        tone = it.get("tone") or ("" if (it.get("highlight") or not any_hl) else "muted")
        label = str(it.get("label", ""))
        short = label
        while text_width(short) > LW - 14 and len(short) > 2:
            short = short[:-2] + "…"
        parts.append(f'<g><title>{esc(label)}: {esc(fmt_num(v))}{esc(unit)}{(" · " + esc(it["note"])) if it.get("note") else ""}</title>')
        parts.append(f'<text class="lbl" x="{LW - 10}" y="{y + ROW / 2 + 4.5:.1f}" text-anchor="end">{esc(short)}</text>')
        parts.append(f'<rect class="bar {tone}" x="{xa:.1f}" y="{y + 6}" width="{max(xb - xa, 1.5):.1f}" height="{ROW - 12}" rx="2"/>')
        shown = it.get("display") or (fmt_num(v) + unit)
        parts.append(f'<text class="val" x="{x1 + 8}" y="{y + ROW / 2 + 4.5:.1f}">{esc(shown)}</text></g>')
    if lo < 0 < hi:
        parts.append(f'<line class="zero" x1="{X(0):.1f}" x2="{X(0):.1f}" y1="{TOP}" y2="{H - 22}"/>')
    parts.append("</svg>")
    cap = f'<p class="chart-cap">{inline(b["caption"])}</p>' if b.get("caption") else ""
    title = f'<p class="chart-t">{inline(b["title"])}</p>' if b.get("title") else ""
    return f'<figure class="chart">{title}<div class="chart-scroll">{"".join(parts)}</div>{cap}</figure>'


def block_flow(b):
    steps = b.get("steps") or []
    edges = b.get("edges") or []
    out = [f'<div class="flow{" vertical" if len(steps) > 4 else ""}">']
    for n, s in enumerate(steps):
        if n:
            lab = edges[n - 1] if n - 1 < len(edges) else ""
            out.append(f'<div class="flow-arrow" aria-hidden="true">{esc(lab)}</div>')
        out.append(f'<div class="flow-step"><b>{inline(s.get("title", ""))}</b><span>{inline(s.get("desc", ""))}</span></div>')
    out.append("</div>")
    if b.get("caption"):
        out.append(f'<p class="flow-cap">{inline(b["caption"])}</p>')
    title = f'<p class="chart-t">{inline(b["title"])}</p>' if b.get("title") else ""
    return title + "".join(out)


def block_stats(b):
    items = b.get("items") or []
    cells = "".join(
        f'<div class="stat"><span class="stat-v">{esc(i.get("value"))}</span>'
        f'<span class="stat-l">{inline(i.get("label"))}</span>'
        + (f'<span class="stat-n">{inline(i.get("note"))}</span>' if i.get("note") else "") + "</div>"
        for i in items)
    return f'<div class="stats">{cells}</div>' if cells else ""


def block_table(b):
    rows = b.get("rows") or []
    head = b.get("headers") or []
    h = "".join(f"<th>{inline(c)}</th>" for c in head)
    body = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows)
    title = f'<p class="chart-t">{inline(b["title"])}</p>' if b.get("title") else ""
    cap = f'<p class="chart-cap">{inline(b["caption"])}</p>' if b.get("caption") else ""
    return f'{title}<div class="tbl-wrap"><table>{"<thead><tr>" + h + "</tr></thead>" if h else ""}<tbody>{body}</tbody></table></div>{cap}'


def block_callout(b):
    tone = "warn" if b.get("tone") == "warn" else ""
    t = f'<span class="callout-t">{inline(b["title"])}</span>' if b.get("title") else ""
    return f'<div class="callout {tone}">{t}{md(b.get("text"))}</div>'


def block_compare(b):
    cols = []
    for side in ("left", "right"):
        c = b.get(side) or {}
        cols.append(f'<div><h4>{inline(c.get("title"))}</h4>{md(c.get("items"))}</div>')
    title = f'<p class="chart-t">{inline(b["title"])}</p>' if b.get("title") else ""
    return f'{title}<div class="compare">{"".join(cols)}</div>'


def block_mermaid(b):
    cap = f'<p class="chart-cap">{inline(b["caption"])}</p>' if b.get("caption") else ""
    return f'<pre class="mermaid">{esc(b.get("code", ""))}</pre>{cap}'


BLOCKS = {
    "bars": block_bars, "flow": block_flow, "stats": block_stats, "table": block_table,
    "callout": block_callout, "compare": block_compare, "mermaid": block_mermaid,
    "list": lambda b: md(b.get("items")), "text": lambda b: md(b.get("text")),
}


def blocks(bs):
    out = []
    for b in bs or []:
        fn = BLOCKS.get(b.get("type"))
        if not fn:
            print(f"  ! 알 수 없는 블록 종류: {b.get('type')}", file=sys.stderr)
            continue
        out.append(fn(b))
    return "\n".join(out)


def easy_detail(obj):
    """easy(항상 보임) + detail('자세히' 모드에서 추가로 보임)."""
    h = ""
    if obj.get("easy"):
        h += f'<div class="prose v-easy">{md(obj["easy"])}</div>'
    if obj.get("detail"):
        h += f'<div class="prose v-detail"><span class="rail-label">자세히</span>{md(obj["detail"])}</div>'
    return h


# ---------------------------------------------------------------- 그림

def image_data_uri(base, rel):
    p = (base / rel).resolve()
    if not p.is_file():
        print(f"  ! 그림 파일 없음: {rel}", file=sys.stderr)
        return None
    data = p.read_bytes()
    if len(data) > MAX_IMAGE_BYTES:
        print(f"  ! 그림이 너무 큼({len(data)//1024}KB), 그대로 넣습니다: {rel}", file=sys.stderr)
    mime = mimetypes.guess_type(p.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def figure_card(f, base):
    fid = re.sub(r"[^A-Za-z0-9_-]", "", f.get("id") or "") or "fig"
    h = [f'<article class="fig" id="f-{fid}">',
         f'<div class="fig-head"><span class="fig-label">{esc(f.get("label"))}'
         + (f' · {esc(f["kind"])}' if f.get("kind") else "") + "</span>"
         f'<h3>{inline(f.get("title_ko") or f.get("label"))}</h3></div>']
    src = image_data_uri(base, f["image"]) if f.get("image") else None
    if src:
        alt = esc(f.get("title_ko") or f.get("caption") or f.get("label"))
        h.append(f'<button type="button" class="fig-zoom" aria-label="{esc(f.get("label"))} 크게 보기"><img src="{src}" alt="{alt}" loading="lazy"></button>')
        h.append('<p class="fig-zoom-hint">누르면 크게 볼 수 있어요</p>')
    elif f.get("missing_note") is not False:
        h.append(f'<div class="fig-missing">{inline(f.get("missing_note") or "원본 이미지를 가져오지 못해 캡션과 본문 수치로 해석했습니다.")}</div>')
    h.append(blocks(f.get("blocks")))
    g = ['<div class="fig-grid">']
    if f.get("what"):
        g.append(f'<h4>무엇을 보여주나</h4><div class="prose">{md(f["what"])}</div>')
    if f.get("how_to_read"):
        steps = "".join(f"<li>{inline(s)}</li>" for s in f["how_to_read"])
        g.append(f'<h4>읽는 순서</h4><div class="prose"><ol>{steps}</ol></div>')
    if f.get("findings"):
        g.append(f'<h4>핵심 발견</h4><div class="prose">{md(f["findings"])}</div>')
    if f.get("meaning"):
        g.append(f'<h4>그래서 무슨 의미?</h4><div class="prose">{md(f["meaning"])}</div>')
    if f.get("caveat"):
        g.append(f'<div class="callout warn"><span class="callout-t">해석할 때 주의</span>{md(f["caveat"])}</div>')
    g.append("</div>")
    h.append("".join(g))
    if f.get("detail"):
        h.append(f'<div class="prose v-detail"><span class="rail-label">자세히</span>{md(f["detail"])}</div>')
    if f.get("caption"):
        h.append(f'<details><summary>원문 캡션 보기</summary><p class="orig">{esc(f["caption"])}</p></details>')
    h.append("</article>")
    return "\n".join(h)


# ---------------------------------------------------------------- paper.json 자동 채우기

def merge_paper(rep, base):
    """fetch_paper.py 가 만든 paper.json 에서 서지 정보, 캡션, 이미지 경로, 표 숫자를 채운다.
    report.json 에 이미 있는 값은 건드리지 않으므로 Claude는 해석만 쓰면 된다."""
    m = rep.setdefault("meta", {})
    pj = base / "paper.json"
    if pj.is_file():
        paper = json.loads(pj.read_text(encoding="utf-8"))
        pm, ids = paper.get("meta", {}), paper.get("ids", {})
        for k, v in (("title", pm.get("title")), ("authors", pm.get("authors")),
                     ("journal", pm.get("journal")), ("year", pm.get("year")),
                     ("pmid", ids.get("pmid")), ("pmcid", ids.get("pmcid")),
                     ("doi", ids.get("doi")), ("url", paper.get("url")),
                     ("read_date", paper.get("fetched"))):
            if v and not m.get(k):
                m[k] = v
        src = {}
        for it in (paper.get("figures") or []) + (paper.get("tables") or []):
            src[it.get("id")] = it
            src[it.get("label")] = it
        for card in (rep.get("figures") or []) + (rep.get("tables") or []):
            it = src.get(card.get("id")) or src.get(card.get("label"))
            if not it:
                continue
            card.setdefault("label", it.get("label"))
            if not card.get("caption") and it.get("caption"):
                card["caption"] = it["caption"]
            if not card.get("image") and it.get("image"):
                card["image"] = it["image"]
            rows = it.get("rows") or []
            if rows and not card.get("blocks") and not card.get("image"):
                card["blocks"] = [{"type": "table", "headers": rows[0], "rows": rows[1:],
                                   "caption": it.get("footnote", "")}]
    m.setdefault("read_date", time.strftime("%Y-%m-%d"))
    return rep


# ---------------------------------------------------------------- 조립

def build(rep, base):
    m = rep.get("meta", {})
    toc, body = [], []

    def sec(sid, kicker, title, inner):
        toc.append(f'<li><a href="#{sid}">{esc(title)}</a></li>')
        body.append(f'<section id="{sid}"><span class="kicker">{esc(kicker)}</span><h2>{esc(title)}</h2>{inner}</section>')

    # 머리말
    authors = m.get("authors") or []
    au = ", ".join(authors[:3]) + (f" 외 {len(authors) - 3}명" if len(authors) > 3 else "")
    links = []
    if m.get("url"):
        links.append(f'<a href="{esc(m["url"])}" target="_blank" rel="noopener">PubMed</a>')
    if m.get("doi"):
        links.append(f'<a href="https://doi.org/{esc(m["doi"])}" target="_blank" rel="noopener">DOI {esc(m["doi"])}</a>')
    chips = "".join(f'<span class="chip">{esc(c)}</span>' for c in (m.get("tags") or []))
    head = [
        '<header>',
        f'<div class="eyebrow"><span>논문 리딩 노트</span>{"<span>" + esc(m["read_date"]) + "</span>" if m.get("read_date") else ""}'
        f'{"<span>PMID " + esc(m["pmid"]) + "</span>" if m.get("pmid") else ""}</div>',
        f'<h1>{inline(m.get("title_ko") or m.get("title"))}</h1>',
        f'<p class="orig-title" lang="en">{esc(m.get("title"))}</p>' if m.get("title_ko") else "",
        f'<p class="meta"><span><b>{esc(au)}</b></span><span>{esc(m.get("journal"))} · {esc(m.get("year"))}</span>{"".join(f"<span>{l}</span>" for l in links)}</p>',
        f'<div class="chips">{chips}</div>' if chips else "",
        f'<p class="tldr"><span class="rail-label">한 줄 요약</span><mark>{inline(rep.get("tldr"))}</mark></p>' if rep.get("tldr") else "",
        '</header>',
    ]
    body.append("".join(head))

    # 한눈에 보기
    ov = rep.get("overview") or {}
    inner = ""
    if ov.get("points"):
        inner += '<ol class="points">' + "".join(f"<li><span>{inline(p)}</span></li>" for p in ov["points"]) + "</ol>"
    inner += block_stats({"items": ov.get("stats")}) + easy_detail(ov) + blocks(ov.get("blocks"))
    if inner:
        sec("overview", "1분 요약", ov.get("title") or "한눈에 보기", inner)

    for n, s in enumerate(rep.get("sections") or [], 1):
        sid = re.sub(r"[^a-z0-9-]", "", (s.get("id") or f"s{n}").lower()) or f"s{n}"
        sec(sid, s.get("kicker") or "본문", s.get("title", f"섹션 {n}"), easy_detail(s) + blocks(s.get("blocks")))

    figs = (rep.get("figures") or []) + (rep.get("tables") or [])
    if figs:
        intro = md(rep.get("figures_intro")) if rep.get("figures_intro") else ""
        sec("figures", "그림·표 해석", "그림과 표 읽기", f'<div class="prose">{intro}</div>' + "".join(figure_card(f, base) for f in figs))

    rel = rep.get("relevance")
    if rel:
        inner = easy_detail({"easy": rel.get("summary")})
        for p in rel.get("projects") or []:
            meter = ""
            if p.get("fit") is not None:
                fit = max(0, min(5, int(p["fit"])))
                dots = "".join(f'<i class="{"on" if k < fit else ""}"></i>' for k in range(5))
                meter = f'<span class="fit" aria-label="연관도 5점 중 {fit}점">연관도 {dots} {fit}/5</span>'
            card = [f'<div class="proj"><div class="proj-head"><h3>{inline(p.get("name"))}</h3>{meter}</div>']
            if p.get("why"):
                card.append(f'<div class="prose">{md(p["why"])}</div>')
            if p.get("use"):
                card.append(f'<div class="prose"><strong>이렇게 써먹기</strong>{md(p["use"])}</div>')
            for c in p.get("cite_as") or []:
                card.append(f'<div class="cite"><span class="cite-text">{inline(c)}</span><button type="button">복사</button></div>')
            card.append("</div>")
            inner += "".join(card)
        if rel.get("next"):
            inner += f'<h3>다음에 할 일</h3><div class="prose">{md(rel["next"])}</div>'
        sec("relevance", "내 프로젝트와 연결", rel.get("title") or "내 프로젝트에 어떻게 쓸까", inner)

    # 출처
    src = ["<footer>"]
    src.append(f'<p>출처: PubMed에서 가져온 논문 정보를 바탕으로 정리했습니다. 원문: '
               + (f'<a href="https://doi.org/{esc(m["doi"])}" target="_blank" rel="noopener">https://doi.org/{esc(m["doi"])}</a>' if m.get("doi") else esc(m.get("url"))) + "</p>")
    if rep.get("source_note"):
        src.append(f"<p>{inline(rep['source_note'])}</p>")
    src.append("<p>이 리포트는 학습용 요약입니다. 인용할 때는 반드시 원문을 확인하세요.</p></footer>")
    body.append("".join(src))

    title = rep.get("page_title") or (m.get("short_title") or m.get("title_ko") or m.get("title") or "논문 리딩 노트")
    tpl = TEMPLATE.read_text(encoding="utf-8")
    return tpl.replace("{{TITLE}}", esc(title)).replace("{{TOC}}", "".join(toc)).replace("{{BODY}}", "\n".join(body))


def update_index():
    lib = ROOT / "library"
    rows = []
    for rj in sorted(lib.glob("*/report.json")):
        try:
            r = json.loads(rj.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        m = r.get("meta", {})
        rows.append((m.get("read_date", ""), rj.parent.name, m.get("title_ko") or m.get("title", ""),
                     m.get("journal", ""), m.get("year", ""), r.get("tldr", "")))
    rows.sort(reverse=True)
    L = ["# 읽은 논문", "", "`scripts/build_report.py` 가 자동으로 갱신합니다.", "",
         "| 읽은 날 | 논문 | 저널 | 한 줄 요약 |", "|---|---|---|---|"]
    for d, key, t, j, y, tl in rows:
        L.append(f"| {d} | [{t}]({key}/report.html) | {j} {y} | {tl.replace('|', '/').replace('==', '')} |")
    (lib / "README.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    target = Path(sys.argv[1])
    rj = target if target.suffix == ".json" else target / "report.json"
    if not rj.is_file():
        raise SystemExit(f"report.json이 없습니다: {rj}")
    rep = json.loads(rj.read_text(encoding="utf-8"))
    out = rj.parent / "report.html"
    out.write_text(build(merge_paper(rep, rj.parent), rj.parent), encoding="utf-8")
    if rj.parent.parent.resolve() == (ROOT / "library").resolve():
        update_index()
    size = out.stat().st_size
    print(f"리포트 생성: {out} ({size / 1024:.0f}KB)")
    if size > 15_000_000:
        print("  ! 16MB 한도에 가깝습니다. 큰 그림을 줄이세요.", file=sys.stderr)


if __name__ == "__main__":
    main()
