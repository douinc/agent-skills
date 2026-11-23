#!/usr/bin/env python3
"""정리 JSON(+메타·전사) → 팀 공유용 HTML 한 장. 표준 라이브러리만 쓴다.

    python render.py summary.json --meta meta.json [--transcript transcript.txt] [--diagram 제목=그림.html] > out.html

meta.json 키(모두 선택):
  recorder(녹음한 사람), author_email, recorded_at(ISO, 녹음 시작), duration_min, source(녹음 수단, 예: "휴대폰"),
  kind_label(대화 종류 칩), scope(external·internal → '외부 녹음'·'내부 녹음' 태그), session_id,
  source_tag(출처 태그이자 바닥글 주어, 기본 "녹음"), source_label(출처 칩 글 전체, 예: "구글밋"),
  tags(source_tag 다음에 붙일 태그 목록), requester(정리를 요청한 사람), generator(만든 도구 이름),
  title_prefix(제목 앞에 붙일 글, 예: "[회의록] 2026-11-17"),
  meeting_mode(online·offline → '회의록'과 '온라인 회의'·'오프라인 회의' 태그),
  meta_prefix(문서 보관소가 읽는 분류 meta의 이름 머리. 주면 `<머리>:type`·`<머리>:tags`·`<머리>:title`도 낸다).
전사 파일 줄이 `[HH:MM:SS] 이름: 내용` 꼴이면 시각을 읽어 경과 시각으로 보여 준다.

화면: 머리(종류·시각·길이, 제목, 한 줄 요약) 아래 [정리 | 원문 전사] 탭. 그림(--diagram, 독립 HTML)은
정리 탭 '핵심' 다음에 iframe으로 들어가고 '크게 보기'로 화면 가득 볼 수 있다. 전사 탭은 화자별 색·경과 시각·
찾기·화자 거르기. 탭은 CSS만으로 바뀌고(스크립트가 막혀도 됨), 주소 끝 #transcript면 전사 탭으로 연다.

HTML 머리에는 `author`·`keywords`(출처, 외부/내부 녹음, 미팅 종류, 상대 기관, 핵심어) meta가 들어간다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from html import escape
from typing import Any

CSS = """
:root{--bg:#fff;--fg:#1b1d21;--muted:#5f6670;--line:#e4e7eb;--soft:#f5f7f9;--accent:#3b6ef5;--chip:#eef2ff;--mark:#fff2a8;
--s0:#3b6ef5;--s1:#e8590c;--s2:#2b8a3e;--s3:#ae3ec9;--s4:#c2255c;--s5:#0c8599;--s6:#5f3dc4;--s7:#a07c00}
@media (prefers-color-scheme:dark){:root{--bg:#141517;--fg:#e8eaed;--muted:#9aa1ab;--line:#2b2e33;--soft:#1c1e21;--accent:#7aa2ff;--chip:#232a3d;--mark:#5c4d00;
--s0:#7aa2ff;--s1:#ff922b;--s2:#69db7c;--s3:#da77f2;--s4:#f783ac;--s5:#3bc9db;--s6:#9775fa;--s7:#ffd43b}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.65 Pretendard,"Apple SD Gothic Neo","Noto Sans KR",system-ui,sans-serif}
main{max-width:840px;margin:0 auto;padding:32px 20px 56px}
header .chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
.chip{background:var(--chip);color:var(--accent);border-radius:999px;padding:2px 10px;font-size:12.5px;font-weight:600}
.chip.gray{background:var(--soft);color:var(--muted)}
h1{font-size:24px;line-height:1.35;margin:0 0 6px}
.who{color:var(--muted);font-size:14px;margin:0}
.lead{margin:20px 0 4px;padding:14px 16px;border-left:4px solid var(--accent);background:var(--soft);border-radius:0 10px 10px 0;font-size:16px}
.view{position:absolute;opacity:0;pointer-events:none}
.tabs{position:sticky;top:0;z-index:2;display:flex;gap:4px;margin:22px 0 4px;padding-top:6px;background:var(--bg);border-bottom:1px solid var(--line)}
.tabs label{cursor:pointer;padding:9px 14px 10px;border-bottom:3px solid transparent;color:var(--muted);font-weight:600;font-size:15px}
.tabs label small{font-weight:500;font-size:12.5px;margin-left:4px}
#v-sum:checked~.tabs label[for=v-sum],#v-tr:checked~.tabs label[for=v-tr]{color:var(--fg);border-color:var(--accent)}
#v-sum:focus-visible~.tabs label[for=v-sum],#v-tr:focus-visible~.tabs label[for=v-tr]{outline:2px solid var(--accent);outline-offset:2px}
.panel{display:none;scroll-margin-top:56px}
#v-sum:checked~.p-sum,#v-tr:checked~.p-tr{display:block}
h2{font-size:17px;margin:28px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
h3{font-size:15px;margin:18px 0 6px}
ul{margin:0;padding-left:20px}
li{margin:3px 0}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600;background:var(--soft)}
.goto{display:inline-block;margin-top:26px;color:var(--accent);cursor:pointer;font-weight:600;font-size:14px}
.trbar{position:sticky;top:52px;z-index:1;background:var(--bg);padding:14px 0 10px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;border-bottom:1px solid var(--line)}
.trbar input{flex:1 1 220px;min-width:0;font:inherit;font-size:14px;padding:7px 12px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg)}
.spk{display:inline-flex;align-items:center;gap:6px;font:inherit;font-size:13px;padding:4px 10px;border:1px solid var(--line);border-radius:999px;background:var(--bg);color:var(--fg);cursor:pointer}
.spk i{width:9px;height:9px;border-radius:50%;background:var(--c)}
.spk[aria-pressed=false]{opacity:.4}
.count{color:var(--muted);font-size:12.5px;width:100%}
.turns{margin-top:6px}
.turn{display:grid;grid-template-columns:62px 1fr;gap:4px 12px;padding:9px 0;border-bottom:1px solid var(--line)}
.turn time{color:var(--muted);font-size:12.5px;font-variant-numeric:tabular-nums;padding-top:2px}
.turn b{display:block;color:var(--c);font-size:13px;font-weight:700}
.turn p{margin:0;white-space:pre-wrap;word-break:keep-all;overflow-wrap:anywhere}
.turn[hidden],.cut[hidden]{display:none}
mark{background:var(--mark);color:inherit;border-radius:2px}
.cut{display:flex;align-items:center;gap:10px;margin:16px 0 8px;color:var(--muted);font-size:12.5px}
.cut::before,.cut::after{content:"";flex:1;border-top:1px dashed var(--line)}
.note{color:var(--muted);font-size:13px;margin:10px 0 0}
figure{margin:12px 0 18px}
figure .fhead{display:flex;align-items:baseline;gap:10px;justify-content:space-between}
figure figcaption{font-weight:700;font-size:15px}
figure .why{color:var(--muted);font-size:13px;margin:2px 0 8px}
figure iframe{display:block;width:100%;height:560px;border:1px solid var(--line);border-radius:10px;background:var(--bg)}
.fs{font:inherit;font-size:13px;padding:3px 10px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg);cursor:pointer;white-space:nowrap}
figure.full{position:fixed;inset:0;z-index:10;margin:0;padding:12px;background:var(--bg);display:flex;flex-direction:column}
figure.full iframe{flex:1;height:auto}
footer{margin-top:36px;color:var(--muted);font-size:12.5px}
@media (max-width:560px){main{padding:22px 14px 40px}.turn{grid-template-columns:1fr}.turn time{padding:0}.trbar{position:static;flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none}.trbar input{flex:0 0 150px}.spk{flex:0 0 auto}.count{display:none}}
.turn.cont{border-top:0;padding-top:0}
@media print{.view,.tabs,.trbar,.goto,.fs{display:none}.panel{display:block!important}.p-tr{break-before:page}}
"""

# 그림 '크게 보기'(화면 가득). Esc로 닫는다
FIG_JS = """
(()=>{const close=()=>document.querySelectorAll('figure.full').forEach(f=>{f.classList.remove('full');f.querySelector('.fs').textContent='크게 보기';});
document.querySelectorAll('.fs').forEach(b=>b.addEventListener('click',()=>{const f=b.closest('figure'),on=!f.classList.contains('full');
close();if(on){f.classList.add('full');b.textContent='닫기';}}));
document.addEventListener('keydown',e=>{if(e.key==='Escape')close();});})();
"""

# 전사 탭의 찾기·화자 거르기. 스크립트가 막혀도 탭 전환(CSS)과 전사 읽기는 된다
JS = """
(()=>{const q=document.getElementById('q'),turns=[...document.querySelectorAll('.turn')],cnt=document.getElementById('cnt'),
off=new Set(),esc=s=>s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'})[c]);
turns.forEach(t=>{const p=t.querySelector('p');p.dataset.raw=p.textContent;});
function apply(){const k=(q.value||'').trim().toLowerCase();let n=0;
turns.forEach(t=>{const p=t.querySelector('p'),raw=p.dataset.raw,low=raw.toLowerCase(),hit=!k||low.includes(k),show=hit&&!off.has(t.dataset.s);
t.hidden=!show;if(show)n++;
if(!k){p.textContent=raw;return;}let h='',i=0,j;while((j=low.indexOf(k,i))>=0){h+=esc(raw.slice(i,j))+'<mark>'+esc(raw.slice(j,j+k.length))+'</mark>';i=j+k.length;}
p.innerHTML=h+esc(raw.slice(i));});
document.querySelectorAll('.cut').forEach(c=>c.hidden=!!(k||off.size));
cnt.textContent=(k||off.size)?`${n}개 발언 표시`:'';}
q.addEventListener('input',apply);
document.querySelectorAll('.spk').forEach(b=>b.addEventListener('click',()=>{const s=b.dataset.s;
off.has(s)?off.delete(s):off.add(s);b.setAttribute('aria-pressed',!off.has(s));apply();}));
if(location.hash==='#transcript')document.getElementById('v-tr').checked=true;})();
"""


def _s(v: Any) -> str:
    return escape(str(v or "").strip())


def _list(items: list[Any]) -> str:
    rows = [f"<li>{_s(x)}</li>" for x in items or [] if str(x or "").strip()]
    return f"<ul>{''.join(rows)}</ul>" if rows else ""


def _section(title: str, body: str) -> str:
    return f"<h2>{escape(title)}</h2>{body}" if body else ""


def _when(meta: dict) -> str:
    raw = meta.get("recorded_at")
    if not raw:
        return ""
    try:
        t = datetime.fromisoformat(str(raw))
    except ValueError:
        return _s(raw)
    return f"{t.year}년 {t.month}월 {t.day}일 {t:%H:%M}"


def _clock(sec: int) -> str:
    return (
        f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"
        if sec >= 3600
        else f"{sec // 60}:{sec % 60:02d}"
    )


def _start(meta: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(str(meta.get("recorded_at")))
    except ValueError:
        return None


def _transcript(lines: list[dict] | None, meta: dict) -> tuple[str, str]:
    """(탭 이름 옆 설명, 전사 탭 본문). 항목: speaker·start_s·end_s·text, 또는 divider(이어진 녹음 경계)."""
    if not lines:
        return "", ""
    start = _start(meta)
    order: list[str] = []
    talk: dict[str, float] = {}
    for x in lines:
        sp = x.get("speaker")
        if x.get("divider") or not sp:
            continue
        if sp not in order:
            order.append(sp)
        talk[sp] = talk.get(sp, 0) + max(
            0, float(x.get("end_s") or x.get("start_s") or 0) - float(x.get("start_s") or 0)
        )
    if not any(talk.values()):  # 끝 시각이 없는 전사(글 파일)는 글자 수로 말한 비율을 어림한다
        for x in lines:
            if x.get("speaker") and not x.get("divider"):
                talk[x["speaker"]] += len(str(x.get("text") or ""))
    color = {sp: f"var(--s{i % 8})" for i, sp in enumerate(order)}
    total = sum(talk.values()) or 1
    numbered = any(_NUMBERED.match(sp) for sp in order)
    rows = []
    for x in lines:
        sec = int(x.get("start_s") or 0)
        if x.get("divider"):
            at = f"{(start + timedelta(seconds=sec)):%H:%M} " if start else ""
            rows.append(f'<div class="cut">{at}녹음 이어짐</div>')
            continue
        sp = x.get("speaker") or ""
        clock = f' title="{(start + timedelta(seconds=sec)):%H:%M:%S}"' if start else ""
        cont = bool(x.get("cont"))
        who = f"<b>{_s(sp)}</b>" if sp and not cont else ""
        rows.append(
            f'<div class="turn{" cont" if cont else ""}" data-s="{_s(sp)}" style="--c:{color.get(sp, "var(--muted)")}">'
            f"<time{clock}>{_clock(sec)}</time><div>{who}<p>{_s(x.get('text'))}</p></div></div>"
        )
    chips = "".join(
        f'<button type="button" class="spk" data-s="{_s(sp)}" aria-pressed="true" style="--c:{color[sp]}">'
        f"<i></i>{_s(sp)} {round(talk.get(sp, 0) * 100 / total)}%</button>"
        for sp in order
    )
    minutes = meta.get("duration_min")
    label = " · ".join(
        p for p in (f"{minutes}분" if minutes else "", f"화자 {len(order)}" if order else "") if p
    )
    body = (
        '<div class="trbar"><input id="q" type="search" placeholder="전사에서 찾기" aria-label="전사에서 찾기">'
        f'{chips}<span class="count" id="cnt"></span></div>'
        f'<div class="turns">{"".join(rows)}</div>'
        '<p class="note">STT 전사라 오인식이 있다. '
        + (
            "화자 번호는 자동 분리라 같은 사람이 둘로 나뉘거나 바뀔 수 있다. "
            if numbered or not order
            else ""
        )
        + "시각에 마우스를 올리면 실제 시각이 보인다.</p>"
    )
    return label, body


_NUMBERED = re.compile(r"^(화자|speaker)\s*\d+$", re.I)


def _figures(diagrams: list[dict] | None) -> str:
    """archify 독립 HTML을 iframe srcdoc으로 넣는다(그림 스크립트·글꼴이 문서와 섞이지 않게)."""
    out = []
    for d in diagrams or []:
        if not d.get("html"):
            continue
        why = f'<p class="why">{_s(d.get("purpose"))}</p>' if d.get("purpose") else ""
        out.append(
            f'<figure><div class="fhead"><figcaption>{_s(d.get("title")) or "그림"}</figcaption>'
            '<button type="button" class="fs">크게 보기</button></div>'
            f'{why}<iframe loading="lazy" title="{_s(d.get("title"))}" srcdoc="{escape(d["html"], quote=True)}"></iframe></figure>'
        )
    return "".join(out)


SOURCE_TAG = "녹음"
OFFLINE_MEETING_TYPES = {"영업·고객 미팅", "협력사 회의", "투자 미팅", "내부 회의"}
MEETING_TAGS = {"회의록", "온라인 회의", "오프라인 회의"}


def doc_labels(data: dict, meta: dict) -> tuple[str, list[str]]:
    """문서 분류(종류, 태그). 문서 보관소가 meta로 읽어 갈 수 있다."""
    mtype = str(data.get("meeting_type") or "").strip()
    doc_type = "교육·발표 자료" if mtype == "세미나·강연" else "회의·결정 기록"
    scope = {"external": "외부 녹음", "internal": "내부 녹음"}.get(str(meta.get("scope") or ""), "")
    mode = str(meta.get("meeting_mode") or "")
    out: list[str] = []
    if mode == "online":
        out.extend(["회의록", "온라인 회의"])
    elif mode == "offline" and mtype in OFFLINE_MEETING_TYPES:
        out.extend(["회의록", "오프라인 회의"])
    tags = [str(meta.get("source_tag") or SOURCE_TAG)]
    tags += [str(x) for x in (meta.get("tags") or [])[:3]]
    tags += [scope, mtype if mtype and mtype != "기타" else ""]
    tags += [str(x) for x in (data.get("organizations") or [])[:3]]
    tags += [str(x) for x in (data.get("keywords") or [])[:3]]
    for t in tags:
        t = " ".join(t.replace(",", " ").split())[:40]
        if t and t not in MEETING_TAGS and t not in out:
            out.append(t)
    return doc_type, out[:8]


def render(
    data: dict,
    meta: dict | None = None,
    transcript: list[dict] | None = None,
    diagrams: list[dict] | None = None,
) -> str:
    """diagrams: [{title, purpose, html(archify 독립 HTML)}]. '정리' 탭의 핵심 다음에 넣는다."""
    meta = meta or {}
    doc_type, tags = doc_labels(data, meta)
    title = str(data.get("title") or "녹음 정리").strip()
    title_prefix = str(meta.get("title_prefix") or "").strip()
    if not title_prefix and "회의록" in tags and (start := _start(meta)):
        title_prefix = f"[회의록] {start:%Y-%m-%d}"
    if title_prefix and not title.startswith(title_prefix + " "):
        title = f"{title_prefix} {title}"
    chips = [
        f'<span class="chip">{_s(meta.get("kind_label"))}</span>' if meta.get("kind_label") else "",
        f'<span class="chip gray">{_when(meta)}</span>' if meta.get("recorded_at") else "",
        f'<span class="chip gray">{_s(meta.get("duration_min"))}분</span>'
        if meta.get("duration_min")
        else "",
        f'<span class="chip gray">{_s(meta.get("source_label"))}</span>'
        if meta.get("source_label")
        else f'<span class="chip gray">{_s(meta.get("source"))}</span>'
        if meta.get("source")
        else "",
    ]
    who = []
    if data.get("counterpart"):
        who.append(f"상대: {_s(data['counterpart'])}")
    if meta.get("recorder"):
        who.append(f"녹음: {_s(meta['recorder'])}")
    if meta.get("requester"):
        who.append(f"요청: {_s(meta['requester'])}")

    actions = [a for a in data.get("action_items") or [] if isinstance(a, dict) and a.get("what")]
    action_html = ""
    if actions:
        rows = "".join(
            f"<tr><td>{_s(a.get('who'))}</td><td>{_s(a.get('what'))}</td><td>{_s(a.get('due'))}</td></tr>"
            for a in actions
        )
        action_html = f"<table><tr><th>담당</th><th>할 일</th><th>기한</th></tr>{rows}</table>"
    nums = [n for n in data.get("numbers") or [] if isinstance(n, dict) and n.get("value")]
    num_html = ""
    if nums:
        rows = "".join(f"<tr><td>{_s(n.get('label'))}</td><td>{_s(n.get('value'))}</td></tr>" for n in nums)
        num_html = f"<table><tr><th>항목</th><th>값</th></tr>{rows}</table>"
    topics = "".join(
        f"<h3>{_s(t.get('heading'))}</h3>{_list(t.get('points') or [])}"
        for t in data.get("topics") or []
        if isinstance(t, dict) and t.get("heading")
    )
    check = _list((data.get("open_questions") or []) + (data.get("caveats") or []))

    head_meta = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f'<meta name="generator" content="{_s(meta.get("generator") or "recording-share-html")}">',
        f'<meta name="keywords" content="{escape(", ".join(tags))}">',
    ]
    prefix = str(meta.get("meta_prefix") or "").strip()
    if prefix:  # 문서 보관소가 읽어 갈 분류. 제목은 머리말을 붙였을 때만 고정한다
        head_meta.append(f'<meta name="{_s(prefix)}:type" content="{escape(doc_type)}">')
        head_meta.append(f'<meta name="{_s(prefix)}:tags" content="{escape(", ".join(tags))}">')
        if title_prefix:
            head_meta.append(f'<meta name="{_s(prefix)}:title" content="{escape(title)}">')
    if meta.get("author_email"):
        head_meta.append(f'<meta name="author" content="{_s(meta["author_email"])}">')
    if meta.get("session_id"):
        head_meta.append(f'<meta name="recording:session" content="{_s(meta["session_id"])}">')
    if meta.get("recorded_at"):
        head_meta.append(f'<meta name="recording:recorded-at" content="{_s(meta["recorded_at"])}">')

    tr_label, tr_body = _transcript(transcript, meta)
    figures = _figures(diagrams)
    summary = "".join(
        [
            _section("핵심", _list(data.get("highlights") or [])),
            _section("그림", figures),
            _section("정한 것", _list(data.get("decisions") or [])),
            _section("할 일", action_html),
            _section("숫자·일정", num_html),
            _section("상대 반응·요구", _list(data.get("voice") or [])),
            _section("자세히", topics),
            _section("확인할 것", check),
            '<label class="goto" for="v-tr">원문 전사 보기 →</label>' if tr_body else "",
        ]
    )
    if tr_body:
        tabs = (
            '<input class="view" type="radio" name="view" id="v-sum" checked aria-label="정리">'
            '<input class="view" type="radio" name="view" id="v-tr" aria-label="원문 전사">'
            '<nav class="tabs"><label for="v-sum">정리</label>'
            f'<label for="v-tr">원문 전사<small>{_s(tr_label)}</small></label></nav>'
            f'<section class="panel p-sum">{summary}</section>'
            f'<section class="panel p-tr" id="transcript">{tr_body}</section>'
        )
    else:
        tabs = summary
    body = "".join(
        [
            f'<header><div class="chips">{"".join(chips)}</div><h1>{escape(title)}</h1>',
            f'<p class="who">{" · ".join(who)}</p></header>' if who else "</header>",
            f'<p class="lead">{_s(data.get("one_line"))}</p>' if data.get("one_line") else "",
            tabs,
            f"<footer>{_s(meta.get('source_tag') or SOURCE_TAG)}을 AI가 정리했다. "
            "원문과 다를 수 있으니 중요한 내용은 원문 전사로 확인한다.</footer>",
        ]
    )
    script = (f"<script>{JS}</script>" if tr_body else "") + (f"<script>{FIG_JS}</script>" if figures else "")
    return (
        f'<!doctype html><html lang="ko"><head>{"".join(head_meta)}<title>{escape(title)}</title>'
        f"<style>{CSS}</style></head><body><main>{body}</main>{script}</body></html>\n"
    )


def _read_transcript(path: str) -> list[dict]:
    """텍스트 파일 한 줄 = 한 발화. '화자: 내용' 꼴이면 화자를 나눈다.

    '[HH:MM:SS] 이름: 내용' 꼴(회의 도구가 낸 전사)이면 첫 줄부터 흐른 시간을 start_s로 넣는다(자정을 넘기면 하루를 더한다)."""
    out: list[dict] = []
    first = last = None
    days = 0
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        item: dict = {}
        m = _STAMP.match(line)
        if m:
            sec = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
            if last is not None and sec < last - 12 * 3600:
                days += 1
            last = sec
            sec += days * 86400
            first = sec if first is None else first
            item["start_s"] = sec - first
            line = line[m.end() :]
        speaker, sep, text = line.partition(": ")
        ok = bool(sep) and len(speaker) <= (32 if m else 12)
        item.update({"speaker": speaker if ok else None, "text": text if ok else line})
        out.append(item)
    return out


_STAMP = re.compile(r"^\[(\d{1,2}):(\d{2}):(\d{2})\]\s*")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("summary")
    ap.add_argument("--meta")
    ap.add_argument("--transcript")
    ap.add_argument(
        "--diagram",
        action="append",
        default=[],
        metavar="제목=파일.html",
        help="archify로 만든 그림 HTML(여러 번 줄 수 있다)",
    )
    a = ap.parse_args()
    data = json.load(open(a.summary, encoding="utf-8"))
    meta = json.load(open(a.meta, encoding="utf-8")) if a.meta else {}
    tr = _read_transcript(a.transcript) if a.transcript else None
    figs = []
    for item in a.diagram:
        title, _, path = item.rpartition("=")
        figs.append({"title": title or "그림", "html": open(path, encoding="utf-8").read()})
    sys.stdout.write(render(data, meta, tr, figs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
