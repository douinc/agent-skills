#!/usr/bin/env python3
"""release-notes — 정식 태그 사이의 변경을 고정 양식 릴리스 노트로 쓰고, 검사하고, GitHub Release에 올린다.

  notes.py init <태그> [--base <태그>] [--at <ref>] [--force]   재료(brief.md)와 노트 뼈대(.release-notes/<태그>.md)
                                                   --at: 태그를 만들기 전, 릴리스될 브랜치·커밋 기준으로 쓴다
  notes.py check <태그>                            노트 검사 (오류가 있으면 종료 코드 1)
  notes.py publish <태그> [--dry-run]              검사 → Release 본문 교체(없으면 만들기)
  notes.py link <태그> <주소>                      쇼케이스 링크를 노트 둘째 줄에 넣기
  notes.py audit [--limit N]                       이미 나간 정식 릴리스 노트 점검

설정은 release-showcase와 같은 `.release-showcase/config.json`을 읽는다(없으면 앱 하나·접두사 v).
범위·변경 수집 규칙은 release-showcase의 showcase.py와 같다(기준 태그만 다르다 — 노트는 바로 앞 정식 태그).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from urllib.parse import quote
from dataclasses import dataclass
from datetime import date
from pathlib import Path

CONFIG_NAME = Path(".release-showcase") / "config.json"
NOTES_DIR = Path(".release-notes")
KEPT_MARK = "<!-- release-notes:kept -->"
LIFETIME_DAYS = 3
PRE_RE = re.compile(r"staging|beta|alpha|rc\.?\d|nightly|canary|preview", re.I)
PR_RE = re.compile(r"\(#(\d+)\)")
TAIL_PR_RE = re.compile(r"\(#(\d+)\)\s*$")  # squash 제목 끝의 번호만 PR이다 — 앞의 (#N)은 이슈·색상 코드일 수 있다
REF_RE = re.compile(r"(?<![\w/])#(\d+)\b")
MERGE_RE = re.compile(r"^Merge pull request #(\d+)")
TYPE_RE = re.compile(r"^(\w+)(?:\(([^)]*)\))?!?:\s*(.+)$")
SKIP_RE = re.compile(r"^(Merge |release|sync|Release )", re.I)
PREFIX_RE = re.compile(r"^\s*[-*]\s*(feat|fix|chore|ci|docs|refactor|test|perf|build|style|hotfix)(\([^)]*\))?!?:", re.I)
SECTIONS = ["새 기능", "달라진 점", "고친 것", "올릴 때 할 일", "범위"]
REQUIRED = ["올릴 때 할 일", "범위"]
CHANGE_SECTIONS = ["새 기능", "달라진 점", "고친 것"]
PLACEHOLDER_RE = re.compile(r"TODO|TBD|여기에|<[^>\n]*적는다[^>\n]*>")
GROUP_LABEL = {"feat": "새 기능·바뀐 동작", "fix": "고친 것", "other": "내부 정리"}


@dataclass
class App:
    key: str
    label: str
    tag_prefix: str
    source_dir: str = ""
    ship_scopes: tuple[str, ...] = ()


@dataclass
class Config:
    root: Path
    repo: str
    apps: dict[str, App]
    deny: re.Pattern[str] | None
    include_direct: bool
    server_dirs: list[str]
    keep_sections: list[str]


def run(*cmd: str, check: bool = True, timeout: int = 60) -> str:
    return subprocess.run(cmd, check=check, capture_output=True, text=True, timeout=timeout).stdout


def git(root: Path, *args: str, check: bool = True) -> str:
    return run("git", "-C", str(root), *args, check=check)


def load_config() -> Config:
    try:
        root = Path(run("git", "rev-parse", "--show-toplevel").strip())
    except subprocess.CalledProcessError:
        raise SystemExit("git 저장소 안에서 실행해요") from None
    path = root / CONFIG_NAME
    raw = json.loads(path.read_text()) if path.exists() else {}
    apps = {k: App(k, a.get("label", k), a.get("tagPrefix", "v"), a.get("sourceDir", ""),
                   tuple(a.get("shipScopes", []))) for k, a in (raw.get("apps") or {}).items()}
    if not apps:
        apps["app"] = App("app", root.name, "v")
    deny = raw.get("denyPattern", "")
    if src := raw.get("denyPatternFrom"):
        f = root / src["file"]
        m = re.search(src.get("regex", r"=\s*/(.+)/\w*"), f.read_text()) if f.exists() else None
        if m:
            deny = f"{m.group(1)}|{deny}" if deny else m.group(1)
    rn = raw.get("releaseNotes") or {}
    url = git(root, "remote", "get-url", "origin", check=False).strip()
    slug = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    return Config(root, raw.get("repo") or (slug.group(1) if slug else ""), apps,
                  re.compile(deny.strip("|"), re.I) if deny.strip("|") else None,
                  raw.get("includeDirectCommits", False), rn.get("serverDirs", []),
                  rn.get("keepSections", ["산출물"]))


def app_for_tag(cfg: Config, tag: str) -> App:
    hits = sorted((a for a in cfg.apps.values() if tag.startswith(a.tag_prefix)), key=lambda a: -len(a.tag_prefix))
    if not hits:
        raise SystemExit(f"태그 접두사를 모르겠어요: {tag} (설정: {', '.join(a.tag_prefix + '*' for a in cfg.apps.values())})")
    return hits[0]


def production_tags(cfg: Config, app: App) -> list[tuple[str, str]]:
    out = git(cfg.root, "tag", "-l", f"{app.tag_prefix}*", "--sort=creatordate",
              "--format=%(refname:short)\t%(creatordate:short)")
    rows = [ln.split("\t") for ln in out.splitlines()]
    others = [a.tag_prefix for a in cfg.apps.values() if len(a.tag_prefix) > len(app.tag_prefix)]
    return [(t, d) for t, d in rows if not PRE_RE.search(t.removeprefix(app.tag_prefix))
            and not any(t.startswith(p) for p in others)]


def ref_exists(cfg: Config, ref: str) -> bool:
    return subprocess.run(["git", "-C", str(cfg.root), "rev-parse", "-q", "--verify", f"{ref}^{{commit}}"],
                          capture_output=True).returncode == 0


def end_ref(cfg: Config, tag: str, at: str | None) -> str:
    """구간의 끝 — 태그가 있으면 태그, 아직 없으면 릴리스될 브랜치·커밋(`at`)."""
    if ref_exists(cfg, f"refs/tags/{tag}"):
        return tag
    if at and ref_exists(cfg, at):
        return at
    raise SystemExit(f"태그 {tag}가 없어요 — `git fetch --tags`, 또는 태그 전이면 `--at <브랜치>`로 릴리스될 커밋을 알려 줘요")


def suggest_base(cfg: Config, app: App, tag: str) -> tuple[str, list[str]]:
    tags = production_tags(cfg, app)
    names = [t for t, _ in tags]
    if tag not in names:
        if PRE_RE.search(tag.removeprefix(app.tag_prefix)):
            raise SystemExit(f"{tag}는 정식 태그가 아니에요 — 사전 배포 태그는 --base로 기준을 직접 줘요")
        if not tags:
            raise SystemExit("직전 정식 태그가 없어요 — --base로 지정해요")
        return tags[-1][0], [f"{tags[-1][0]}({tags[-1][1]})를 기준으로 씀 — 지금까지의 마지막 정식 태그(이번 태그는 아직 없음)"]
    i = names.index(tag)
    if i == 0:
        raise SystemExit("직전 정식 태그가 없어요 — --base로 지정해요")
    prev, day = tags[i - 1]
    life = (date.fromisoformat(tags[i][1]) - date.fromisoformat(day)).days
    why = [f"{prev}({day})를 기준으로 씀 — 바로 앞 정식 태그"]
    if life < LIFETIME_DAYS:
        why.append(f"{prev}는 {life}일 만에 이 버전으로 바뀌었어요 — 쇼케이스는 그 앞 버전을 기준으로 잡을 수 있어요")
    return prev, why


def pr_numbers(cfg: Config, ref: str) -> set[str]:
    subjects = git(cfg.root, "log", "--format=%s", ref)
    return set(re.findall(r"\(#(\d+)\)\s*$", subjects, re.M)) | set(re.findall(r"^Merge pull request #(\d+)", subjects, re.M))


def collect_changes(cfg: Config, tag: str, base: str, paths: list[str], scopes: tuple[str, ...]) -> list[dict]:
    """base 히스토리에 없던 PR만 모은다(브랜치가 갈라져 있어도 PR 번호로 가른다)."""
    released = pr_numbers(cfg, base)
    spec = ["--", *paths] if paths else []
    raw = git(cfg.root, "log", "--format=%h%x1f%cs%x1f%s%x1f%b%x1e", f"{base}..{tag}", *spec)
    entries = []
    for record in raw.split("\x1e"):
        if not record.strip():
            continue
        sha, day, subject, body = record.strip("\n").split("\x1f", 3)
        if m := MERGE_RE.match(subject):
            title = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
            entries.append((sha, day, title, [m.group(1)], False))
        elif subject.startswith(("release", "Release")):
            entries += [(sha, day, ln[2:].strip(), TAIL_PR_RE.findall(ln), True) for ln in body.splitlines()
                        if ln.startswith("* ") and TAIL_PR_RE.search(ln)]
        elif not subject.startswith("Merge "):
            entries.append((sha, day, subject, TAIL_PR_RE.findall(subject), False))
    changes, seen = [], set(released)
    for sha, day, subject, prs, bundled in entries:
        if SKIP_RE.match(subject) or (not prs and not cfg.include_direct) or any(p in seen for p in prs):
            continue
        m = TYPE_RE.match(subject)
        kind, scope, text = (m.group(1), m.group(2) or "", m.group(3)) if m else ("other", "", subject)
        ours = not scopes or any(k in scope for k in scopes)
        if bundled and not ours:
            continue
        seen.update(prs)
        group = kind if kind in ("feat", "fix") else "other"
        if scope and not ours:
            group = "other"
        if kind == "chore" and re.search(r"버전을|bump (app )?version|version bump", text, re.I):
            continue
        changes.append({"sha": sha, "day": day, "scope": scope, "text": TAIL_PR_RE.sub("", text).strip(),
                        "prs": prs, "group": group})
    return changes


def pr_body(cfg: Config, number: str, limit: int = 1200) -> str:
    try:
        out = run("gh", "pr", "view", number, "--repo", cfg.repo, "--json", "body", timeout=30)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return "(PR 본문을 읽지 못함 — `gh auth status`)"
    body = re.sub(r"<!--.*?-->", "", json.loads(out).get("body") or "", flags=re.S)
    body = re.sub(r"\n{2,}", "\n", body).strip()
    return body[:limit] + ("…" if len(body) > limit else "")


def release_body(cfg: Config, tag: str) -> str | None:
    try:
        return json.loads(run("gh", "release", "view", tag, "--repo", cfg.repo, "--json", "body", timeout=30))["body"]
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None


# ── 노트 파일 ─────────────────────────────────────────────────────────────


def notes_path(cfg: Config, tag: str) -> Path:
    return cfg.root / NOTES_DIR / f"{tag}.md"


def work_dir(cfg: Config, tag: str) -> Path:
    d = cfg.root / NOTES_DIR / ".work" / tag
    d.mkdir(parents=True, exist_ok=True)
    ignore = cfg.root / NOTES_DIR / ".gitignore"
    if not ignore.exists():
        ignore.write_text(".work/\n")
    return d


def parse_notes(text: str) -> dict:
    """머리말 주석(base·omit), 첫 줄 요약, 구역별 본문."""
    meta = dict(re.findall(r"<!--\s*(base|tag|at):\s*(\S+)\s*-->", text))
    omit = set()
    for line in re.findall(r"<!--\s*omit:(.*?)-->", text, re.S):
        omit |= set(REF_RE.findall(line))
    body = re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()
    head, *parts = re.split(r"^## +(.+?)\s*$", body, flags=re.M)
    titles = [parts[i].strip() for i in range(0, len(parts), 2)]
    sections = {parts[i].strip(): parts[i + 1].strip() for i in range(0, len(parts), 2)}
    lines = [ln for ln in head.strip().splitlines() if ln.strip()]
    return {"meta": meta, "omit": omit, "body": body, "summary": lines[0] if lines else "",
            "head": head.strip(), "sections": sections,
            "dups": sorted({t for t in titles if titles.count(t) > 1})}


def scope_of(cfg: Config, tag: str, base: str, at: str | None = None) -> tuple[App, list[dict], list[dict]]:
    app = app_for_tag(cfg, tag)
    end = end_ref(cfg, tag, at)
    changes = collect_changes(cfg, end, base, [app.source_dir] if app.source_dir else [], app.ship_scopes)
    mine = {p for c in changes for p in c["prs"]}
    server = [c for c in collect_changes(cfg, end, base, cfg.server_dirs, ()) if not set(c["prs"]) & mine] \
        if cfg.server_dirs else []
    return app, changes, server


def cmd_init(cfg: Config, tag: str, base: str | None, force: bool, at: str | None = None) -> int:
    app = app_for_tag(cfg, tag)
    why = [f"--base로 지정: {base}"] if base else []
    if not base:
        base, why = suggest_base(cfg, app, tag)
    _, changes, server = scope_of(cfg, tag, base, at)
    pending = end_ref(cfg, tag, at) != tag
    if pending:
        why.append(f"태그가 아직 없어 `{at}` 기준으로 모음 — 태그 뒤 `check`가 실제 태그로 다시 봐요")
    by = {g: [c for c in changes if c["group"] == g] for g in GROUP_LABEL}
    wd = work_dir(cfg, tag)
    out = [f"# {app.label} {tag.removeprefix(app.tag_prefix)} 재료", "",
           f"- 범위: `{base}` → `{tag}`", *[f"- {w}" for w in why],
           f"- 변경: 새 기능 {len(by['feat'])} · 고친 것 {len(by['fix'])} · 내부 정리 {len(by['other'])}"
           + (f" · 같은 구간 서버 변경 {len(server)}" if cfg.server_dirs else ""), ""]
    for g in ("feat", "fix"):
        out += [f"## {GROUP_LABEL[g]} ({len(by[g])})", ""]
        for c in by[g]:
            refs = " ".join(f"#{p}" for p in c["prs"])
            out += [f"### {c['text']} ({refs}, {c['day']})", ""]
            out += [pr_body(cfg, p) for p in c["prs"][:1]] + [""]
    out += [f"## {GROUP_LABEL['other']} ({len(by['other'])}) — 노트에는 건수만", ""]
    out += [f"- {c['text']} ({' '.join('#' + p for p in c['prs'])})" for c in by["other"]] + [""]
    if server:
        out += [f"## 같은 구간 서버 변경 ({len(server)}) — 이 앱 사용자가 느끼는 것만 노트에", ""]
        out += [f"- [{c['group']}] {c['text']} ({' '.join('#' + p for p in c['prs'])})" for c in server] + [""]
    prev = None if pending else release_body(cfg, tag)
    if prev is not None:
        (wd / "current-body.md").write_text(prev)
        out += ["## 지금 올라가 있는 Release 본문", "", "`current-body.md`에 저장했어요. publish가 남길 구역: "
                + ", ".join(cfg.keep_sections), ""]
    (wd / "brief.md").write_text("\n".join(out))
    path = notes_path(cfg, tag)
    if path.exists() and not force:
        print(f"노트가 이미 있어요(그대로 둠): {path}")
    else:
        compare = f"https://github.com/{cfg.repo}/compare/{quote(base)}...{quote(tag)}" if cfg.repo else ""
        n = len(changes)
        skeleton = [f"<!-- tag: {tag} -->", f"<!-- base: {base} -->", *([f"<!-- at: {at} -->"] if pending else []),
                    "<!-- omit: 노트에 싣지 않는 새 기능·수정 PR과 이유를 적는다. 예) #123 화면에 드러나지 않는 준비 작업 -->", "",
                    "TODO 이번 버전에서 가장 큰 변화 한 문장", "",
                    "## 새 기능", "", "- TODO (#PR)", "", "## 달라진 점", "", "- TODO (#PR)", "",
                    "## 고친 것", "", "- TODO (#PR)", "", "## 올릴 때 할 일", "", "- TODO 없으면 \"할 일 없음\"", "",
                    "## 범위", "",
                    f"`{base}` → `{tag}` · PR {n}건(새 기능 {len(by['feat'])} · 고친 것 {len(by['fix'])} · 내부 정리 {len(by['other'])})"
                    + (f" · [전체 비교]({compare})" if compare else ""), ""]
        path.write_text("\n".join(skeleton))
        print(f"노트 뼈대: {path}")
    print(f"재료: {wd / 'brief.md'}")
    for w in why:
        print(f"  · {w}")
    return 0


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warns: list[str] = []
        self.info: list[str] = []

    def show(self) -> None:
        for mark, rows in (("✗", self.errors), ("△", self.warns), ("·", self.info)):
            for r in rows:
                print(f"{mark} {r}")
        print(f"오류 {len(self.errors)} · 경고 {len(self.warns)}")


def body_checks(rep: Report, cfg: Config, text: str) -> None:
    """본문만 보고 알 수 있는 것 — check와 audit이 함께 쓴다."""
    lines = text.splitlines()
    merges = [ln for ln in lines if re.search(r"Merge (pull request|branch|remote)", ln)]
    if merges:
        rep.errors.append(f"병합 커밋 줄 {len(merges)}개 — 커밋 제목을 그대로 붙였어요: {merges[0].strip()[:60]}")
    prefixed = [ln for ln in lines if PREFIX_RE.match(ln)]
    if prefixed:
        rep.errors.append(f"커밋 접두사가 붙은 줄 {len(prefixed)}개 — 사용자가 겪는 변화로 다시 써요: {prefixed[0].strip()[:60]}")
    if cfg.deny and (m := cfg.deny.search(text)):
        rep.errors.append(f"쓰지 않기로 한 말: {m.group(0)}")


def cmd_check(cfg: Config, tag: str, quiet: bool = False) -> Report:
    rep = Report()
    path = notes_path(cfg, tag)
    if not path.exists():
        raise SystemExit(f"노트가 없어요: {path} — 먼저 `init {tag}`")
    n = parse_notes(path.read_text())
    base = n["meta"].get("base")
    if not base:
        raise SystemExit("노트 머리말에 `<!-- base: 태그 -->`가 없어요")
    app, changes, server = scope_of(cfg, tag, base, n["meta"].get("at"))
    if end_ref(cfg, tag, n["meta"].get("at")) != tag:
        rep.info.append(f"태그가 아직 없어 `{n['meta']['at']}` 기준으로 봤어요 — 태그 뒤 다시 검사해요")
    body_checks(rep, cfg, n["body"])
    if PLACEHOLDER_RE.search(n["body"]):
        rep.errors.append("채우지 않은 자리(TODO)가 남았어요")
    if not n["summary"] or n["summary"].startswith(("#", "-", "[")):
        rep.errors.append("첫 줄에 한 문장 요약이 없어요")
    elif len(n["summary"]) > 120:
        rep.warns.append(f"첫 줄 요약이 {len(n['summary'])}자 — 120자 안쪽으로")
    sec = n["sections"]
    for name in n["dups"]:
        rep.errors.append(f"`## {name}` 구역이 두 번 나와요 — 하나로 합쳐요")
    for name in REQUIRED:
        if name not in sec:
            rep.errors.append(f"`## {name}` 구역이 없어요")
    for name, content in sec.items():
        if name in SECTIONS and not content:
            rep.errors.append(f"`## {name}` 구역이 비었어요 — 없으면 구역을 지우거나 \"없음\"이라고 써요")
        elif name not in SECTIONS:
            rep.warns.append(f"양식에 없는 구역: `## {name}`")
    order = [s for s in sec if s in SECTIONS]
    if order != [s for s in SECTIONS if s in sec]:
        rep.warns.append("구역 순서가 양식과 달라요: " + " → ".join(SECTIONS))
    if not any(sec.get(s) for s in CHANGE_SECTIONS):
        rep.errors.append("새 기능·달라진 점·고친 것이 모두 없어요")
    if "범위" in sec and base not in sec["범위"]:
        rep.errors.append(f"범위 구역에 기준 태그 `{base}`가 없어요")
    cited = set(REF_RE.findall("\n".join(sec.get(s, "") for s in CHANGE_SECTIONS + ["올릴 때 할 일"])))
    user_facing = {p: c for c in changes if c["group"] in ("feat", "fix") for p in c["prs"]}
    known = {p for c in changes + server for p in c["prs"]}
    missing = [p for p in user_facing if p not in cited and p not in n["omit"]]
    for p in missing:
        rep.errors.append(f"범위 안 변경이 노트에 없어요: #{p} {user_facing[p]['text'][:50]} — 싣거나 `<!-- omit: #{p} 이유 -->`")
    for p in sorted(cited - known, key=int):
        rep.errors.append(f"범위 밖 PR을 적었어요: #{p} — `{base}` → `{tag}` 구간{'·서버 경로' if cfg.server_dirs else ''}에 없어요")
    bare = [ln for s in CHANGE_SECTIONS for ln in sec.get(s, "").splitlines()
            if re.match(r"^[-*] ", ln) and not REF_RE.search(ln) and "없음" not in ln]
    if bare:
        rep.warns.append(f"PR 번호가 없는 항목 {len(bare)}개: {bare[0][:50]}")
    names = [t for t, _ in production_tags(cfg, app)]
    if names and names[-1] != tag and tag not in names:
        names.append(tag)
    if tag in names and names.index(tag) > 0:
        prev = names[names.index(tag) - 1]
        prev_file = notes_path(cfg, prev)
        prev_text = parse_notes(prev_file.read_text())["body"] if prev_file.exists() else (release_body(cfg, prev) or "")
        if prev_text and norm_changes(prev_text) == norm_changes(n["body"]):
            rep.errors.append(f"직전 정식 노트({prev})와 변경 내용이 같아요")
    rep.info.append(f"범위 `{base}` → `{tag}`: 새 기능·수정 PR {len(user_facing)}건 중 실은 것 "
                    f"{len([p for p in user_facing if p in cited])} · 뺀 것 {len([p for p in user_facing if p in n['omit']])}")
    if not quiet:
        rep.show()
    return rep


def norm_changes(text: str) -> str:
    """버전·빌드 정보 줄을 뺀 변경 본문 — 복사된 노트를 찾는다."""
    keep = [ln.strip() for ln in text.splitlines()
            if ln.strip() and not re.match(r"^\w+=\S+$", ln.strip()) and "`" not in ln and not ln.startswith(("#", ">", "<"))]
    return "\n".join(keep)


def split_kept(cfg: Config, body: str) -> str:
    """CI가 쓴 본문에서 남길 것 — 지정 구역(기본 산출물)과 맨 위 key=value 빌드 정보."""
    if KEPT_MARK in body:
        return body.split(KEPT_MARK, 1)[1].strip()
    head, *parts = re.split(r"^(## +.+?)\s*$", body, flags=re.M)
    kept = []
    for i in range(0, len(parts), 2):
        title = parts[i].lstrip("# ").strip()
        if any(title.startswith(k) for k in cfg.keep_sections):
            kept.append(f"{parts[i]}\n{parts[i + 1].strip()}")
    info = [ln.strip() for ln in head.splitlines() if re.match(r"^\w+=\S+$", ln.strip())]
    if info:
        kept.append("## 빌드 정보\n```\n" + "\n".join(info) + "\n```")
    return "\n\n".join(kept)


def compose(cfg: Config, tag: str, current: str | None) -> str:
    # 머리말 주석(tag·base·omit)은 GitHub 화면에 보이지 않으므로 그대로 올린다 — audit이 본문만으로 판정한다
    text = notes_path(cfg, tag).read_text().strip()
    kept = split_kept(cfg, current) if current else ""
    return text + (f"\n\n{KEPT_MARK}\n{kept}" if kept else "") + "\n"


def cmd_publish(cfg: Config, tag: str, dry: bool) -> int:
    rep = cmd_check(cfg, tag)
    if rep.errors:
        print("오류가 있어 올리지 않았어요")
        return 1
    if not ref_exists(cfg, f"refs/tags/{tag}"):
        raise SystemExit(f"태그 {tag}가 아직 없어요 — 태그가 올라간 뒤에 올려요")
    current = release_body(cfg, tag)
    wd = work_dir(cfg, tag)
    if current is not None and not (wd / "original-body.md").exists():
        (wd / "original-body.md").write_text(current)
    body = compose(cfg, tag, current)
    out = wd / "publish-body.md"
    out.write_text(body)
    if dry:
        print(f"올릴 본문(올리지 않음): {out}")
        return 0
    if current is None:
        if not git(cfg.root, "ls-remote", "--tags", "origin", tag).strip():
            raise SystemExit(f"원격에 태그 {tag}가 없어요 — 태그는 프로젝트의 릴리스 절차로 먼저 만들어요")
        app = app_for_tag(cfg, tag)
        run("gh", "release", "create", tag, "--repo", cfg.repo, "--verify-tag",
            "--title", f"{app.label} {tag.removeprefix(app.tag_prefix)}", "--notes-file", str(out))
        print(f"Release를 새로 만들었어요: https://github.com/{cfg.repo}/releases/tag/{tag}")
    else:
        run("gh", "release", "edit", tag, "--repo", cfg.repo, "--notes-file", str(out))
        print(f"Release 본문을 바꿨어요: https://github.com/{cfg.repo}/releases/tag/{tag}")
        print(f"이전 본문: {wd / 'original-body.md'}")
    return 0


def cmd_link(cfg: Config, tag: str, url: str) -> int:
    path = notes_path(cfg, tag)
    lines = path.read_text().splitlines()
    link = f"[화면으로 보는 쇼케이스]({url})"
    lines = [ln for ln in lines if not ln.startswith("[화면으로 보는 쇼케이스](")]
    i = next(k for k, ln in enumerate(lines) if ln.strip() and not ln.startswith("<!--"))
    lines[i + 1:i + 1] = ["", link]
    path.write_text("\n".join(lines) + "\n")
    print(f"쇼케이스 링크를 넣었어요 — `publish {tag}`로 다시 올려요")
    return 0


def cmd_audit(cfg: Config, limit: int) -> int:
    rels = json.loads(run("gh", "api", f"repos/{cfg.repo}/releases?per_page=100", timeout=60))
    rows, bad = [], 0
    last_body: dict[str, str] = {}
    for r in sorted(rels, key=lambda r: r["created_at"]):
        tag = r["tag_name"]
        app = next((a for a in sorted(cfg.apps.values(), key=lambda a: -len(a.tag_prefix)) if tag.startswith(a.tag_prefix)), None)
        if r["prerelease"] or r["draft"] or not app or PRE_RE.search(tag.removeprefix(app.tag_prefix)):
            continue
        body = r["body"] or ""
        rep = Report()
        body_checks(rep, cfg, body)
        if app.key in last_body and norm_changes(body) and norm_changes(body) == last_body[app.key]:
            rep.errors.append("직전 정식 노트와 변경 내용이 같음")
        last_body[app.key] = norm_changes(body)
        if "## 올릴 때 할 일" not in body:
            rep.errors.append("양식 아님(올릴 때 할 일 없음)")
        try:
            base, _ = suggest_base(cfg, app, tag)
            _, changes, _ = scope_of(cfg, tag, base)
            facing = {p for c in changes if c["group"] in ("feat", "fix") for p in c["prs"]}
            parsed = parse_notes(body.split(KEPT_MARK, 1)[0])
            base = parsed["meta"].get("base", base)
            _, changes, _ = scope_of(cfg, tag, base)
            facing = {p for c in changes if c["group"] in ("feat", "fix") for p in c["prs"]}
            cited = set(re.findall(r"#(\d+)", parsed["body"]))
            gone = facing - cited - parsed["omit"]
            cover = f"{len(facing & cited)}/{len(facing)}" + (f"(뺀 것 {len(facing & parsed['omit'])})" if facing & parsed["omit"] else "")
            if gone:
                rep.errors.append(f"범위 안 변경 {len(gone)}건 누락")
        except SystemExit:
            cover = "-"
        rows.append((r["created_at"][:10], tag, cover, "; ".join(e.split(" — ")[0] for e in rep.errors) or "통과"))
        bad += bool(rep.errors)
    for day, tag, cover, verdict in rows[-limit:]:
        print(f"{day}  {tag:<32} 실은 변경 {cover:<16} {verdict}")
    print(f"정식 릴리스 {len(rows)}건 중 고칠 것 {bad}건")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="릴리스 노트 — 재료 모으기·검사·올리기")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="재료(brief.md)와 노트 뼈대")
    p.add_argument("tag")
    p.add_argument("--base")
    p.add_argument("--force", action="store_true")
    p.add_argument("--at", help="태그가 아직 없을 때 릴리스될 브랜치·커밋")
    p = sub.add_parser("check", help="노트 검사")
    p.add_argument("tag")
    p = sub.add_parser("publish", help="검사 → Release 본문 교체")
    p.add_argument("tag")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("link", help="쇼케이스 링크 넣기")
    p.add_argument("tag")
    p.add_argument("url")
    p = sub.add_parser("audit", help="나간 정식 릴리스 노트 점검")
    p.add_argument("--limit", type=int, default=30)
    a = ap.parse_args()
    cfg = load_config()
    if a.cmd == "init":
        return cmd_init(cfg, a.tag, a.base, a.force, a.at)
    if a.cmd == "check":
        return 1 if cmd_check(cfg, a.tag).errors else 0
    if a.cmd == "publish":
        return cmd_publish(cfg, a.tag, a.dry_run)
    if a.cmd == "link":
        return cmd_link(cfg, a.tag, a.url)
    return cmd_audit(cfg, a.limit)


if __name__ == "__main__":
    sys.exit(main())
