#!/usr/bin/env python3
"""릴리스 쇼케이스 — 릴리스 태그 사이의 변경을 이미지·영상·HTML 컴포넌트로 보여 주는 파일 하나짜리 HTML.

텍스트뿐인 릴리스 노트로는 화면이 어떻게 바뀌었는지, 새 기능을 어떻게 쓰는지 보이지 않는다. 이 도구는
사람이 쓴 이야기(story.json)에 저장소가 이미 가진 시각 자료를 붙인다.

- 화면 이미지: 이번 태그(이후)와 직전 정식 태그(이전) 시점의 커밋된 스크린샷(골든)을 `git show`로 꺼낸다.
  저장소에 없으면 story 폴더의 `.media/`에 둔 그림을 쓴다.
- 영상: 설정의 `record`가 있으면 태그 시점 코드를 임시 worktree로 꺼내 띄우고 Playwright로 클릭 흐름을
  녹화한다(`record.mjs`). 직접 찍은 영상을 `.media/<id>.webm`으로 넣어도 된다.
- 전체 변경 목록: 기준 태그 히스토리에 없던 PR 번호만 모은다. 브랜치가 갈라져 두 태그가 조상 관계가 아니어도
  (cherry-pick·hotfix) PR 번호로 가르므로 이중 계산이 없다.
- 검사: 빌드 전에 글·자료를 기계로 검사하고(`check`), 빌드 뒤에는 데스크톱·모바일 폭으로 열어 검수한다
  (`verify`, `check.mjs`).

이미지·영상은 base64로 HTML 안에 넣는다 — 메신저 첨부 어디에 올려도 깨지지 않는다. 표준 라이브러리만 쓴다.

사용 (저장소 안 어디서든):
    showcase.py init <태그> [--base <태그>]     # story.json 초안 + 재료 묶음(.media/brief.md)
    showcase.py goldens <태그>                  # 이전·이후 사이에 생기거나 바뀐 스크린샷
    showcase.py check <태그>                    # 글·자료 검사
    showcase.py build <태그> [--record] [--verify]
    showcase.py verify <태그>                   # 만들어 둔 HTML을 다시 검수
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template.html"
CONFIG_NAME = Path(".release-showcase") / "config.json"
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "release-showcase"

CHANGE_GROUPS = [
    ("feat", "새 기능·바뀐 동작"),
    ("fix", "고친 것"),
    ("other", "내부 정비"),
]
HIGHLIGHT_TONES = {"new", "better", "fix", "safe"}
MEDIA_KINDS = {"image", "row", "compare", "steps", "tabs", "video", "flow", "stack"}
# 사용자에게 갈 수 있는 글에 쓰지 않는 내부 구현어 — 설정 `jargon`으로 더한다
JARGON = ["SSE", "payload", "페이로드", "enum", "엔드포인트", "플래그", "리팩터", "마이그레이션", "IPC",
          "웹훅", "래치", "게이트", "하네스", "렌더러", "스키마"]
LIFETIME_DAYS = 3  # 다음 정식 버전이 이 안에 나왔으면 사용자가 실제로 머문 버전이 아니라고 본다
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
        ".gif": "image/gif", ".svg": "image/svg+xml", ".webm": "video/webm", ".mp4": "video/mp4"}


# ── 설정 ──────────────────────────────────────────────────────────────────


@dataclass
class App:
    key: str
    label: str
    tag_prefix: str
    source_dir: str = ""  # 변경 목록을 모을 경로 (비우면 저장소 전체)
    goldens_dir: str = ""  # 커밋된 스크린샷 폴더 (없으면 .media/의 그림만)
    icon: str = ""  # 앱 아이콘 경로 (태그 시점에서 꺼냄)
    ui_dir: str = ""  # 화면 문구를 찾을 경로 — 글에 쓴 메뉴·버튼 이름이 앱에 있는지 본다
    ship_scopes: tuple[str, ...] = ()  # 커밋 scope가 이 중 하나를 담아야 사용자에게 닿는 변경으로 본다
    record: dict = field(default_factory=dict)


@dataclass
class Config:
    root: Path
    repo: str  # GitHub owner/name — PR 링크·릴리스 파일
    stories_dir: Path
    brand: str
    apps: dict[str, App]
    deny: re.Pattern[str] | None
    jargon: list[str]
    include_direct_commits: bool
    notes: list[str]
    tone: str  # 해요체 | 합니다체 | off — 문장 끝 검사
    frame_width: int  # 그림 틀 최대 폭(px) — 좁은 창 앱은 작게, 웹 화면은 크게
    video_width: int  # 영상 틀 최대 폭(px)


def git(root: Path, *args: str, binary: bool = False, check: bool = True) -> str | bytes:
    out = subprocess.run(["git", "-C", str(root), *args], check=check, capture_output=True)
    return out.stdout if binary else out.stdout.decode()


def repo_root() -> Path:
    try:
        return Path(str(git(Path.cwd(), "rev-parse", "--show-toplevel")).strip())
    except subprocess.CalledProcessError:
        raise SystemExit("git 저장소 안에서 실행해요") from None


def github_slug(root: Path) -> str:
    url = str(git(root, "remote", "get-url", "origin", check=False)).strip()
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    return m.group(1) if m else ""


def load_config() -> Config:
    root = repo_root()
    path = root / CONFIG_NAME
    raw = json.loads(path.read_text()) if path.exists() else {}
    apps = {}
    for key, a in (raw.get("apps") or {}).items():
        apps[key] = App(
            key=key, label=a.get("label", key), tag_prefix=a.get("tagPrefix", "v"),
            source_dir=a.get("sourceDir", ""), goldens_dir=a.get("goldensDir", ""), icon=a.get("icon", ""),
            ui_dir=a.get("uiDir", ""), ship_scopes=tuple(a.get("shipScopes", [])), record=a.get("record") or {},
        )
    if not apps:
        apps["app"] = App(key="app", label=root.name, tag_prefix="v")
    deny = raw.get("denyPattern", "")
    if src := raw.get("denyPatternFrom"):
        text = (root / src["file"]).read_text()
        m = re.search(src.get("regex", r"=\s*/(.+)/\w*"), text)
        if m:
            deny = f"{m.group(1)}|{deny}" if deny else m.group(1)
    return Config(
        root=root, repo=raw.get("repo") or github_slug(root),
        stories_dir=root / raw.get("storiesDir", ".release-showcase/stories"),
        brand=raw.get("brandColor", "#1657b9"), apps=apps,
        deny=re.compile(deny.strip("|"), re.IGNORECASE) if deny.strip("|") else None,
        jargon=JARGON + raw.get("jargon", []), include_direct_commits=raw.get("includeDirectCommits", False),
        notes=raw.get("notes", []), tone=raw.get("tone", "해요체"),
        frame_width=int(raw.get("frameWidth", 420)), video_width=int(raw.get("videoWidth", 520)),
    )


def app_for_tag(cfg: Config, tag: str) -> App:
    hits = sorted((a for a in cfg.apps.values() if tag.startswith(a.tag_prefix)), key=lambda a: -len(a.tag_prefix))
    if not hits:
        prefixes = ", ".join(f"{a.tag_prefix}*" for a in cfg.apps.values())
        raise SystemExit(f"태그 접두사를 모르겠어요: {tag} (설정된 접두사: {prefixes})")
    return hits[0]


def story_dir_for(cfg: Config, target: str) -> Path:
    p = Path(target)
    if p.is_dir() or "/" in target:
        return p.resolve()
    return cfg.stories_dir / target


def load_story(story_dir: Path) -> dict:
    path = story_dir / "story.json"
    if not path.exists():
        raise SystemExit(f"{path}가 없어요 — 먼저 `showcase.py init <태그>`")
    return json.loads(path.read_text())


# ── 텍스트 ────────────────────────────────────────────────────────────────


class Inline:
    """story 문자열의 작은 마크업: **굵게**, `화면 문구`, [글](링크), #123 → PR 링크."""

    def __init__(self, repo: str):
        self.repo = repo

    def __call__(self, text: str) -> str:
        s = html.escape(text, quote=False)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        # 영문만 든 `…`은 명령·경로로 보고 고정폭, 다른 글자가 섞이면 화면 문구로 본다
        s = re.sub(r"`(.+?)`", lambda m: f'<code class="cmd">{m.group(1)}</code>' if m.group(1).isascii()
                   else f"<code>{m.group(1)}</code>", s)
        s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
        if self.repo:
            s = re.sub(r"(?<![\w/&])#(\d{1,6})\b", rf'<a class="pr" href="https://github.com/{self.repo}/pull/\1">#\1</a>', s)
        return s


def plain(text: str) -> str:
    return re.sub(r"\*\*|`|\[([^\]]+)\]\([^)]+\)", lambda m: m.group(1) or "", text)


def blend(hex_color: str, ratio: float) -> str:
    """브랜드 색을 흰색과 섞는다 — 밝은 변형·바탕색."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#" + "".join(f"{round(c + (255 - c) * ratio):02x}" for c in (r, g, b))


# ── 미디어 ────────────────────────────────────────────────────────────────


def data_uri(raw: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


class Media:
    def __init__(self, cfg: Config, app: App, refs: dict[str, str], story_dir: Path):
        self.cfg, self.app, self.refs, self.dir = cfg, app, refs, story_dir
        self.media_dir = story_dir / ".media"
        self._cache: dict[tuple[str, str], str] = {}

    def ref(self, spec: dict, default: str = "tag") -> str:
        r = spec.get("ref", default)
        return self.refs.get(r, r)

    def image(self, spec: dict, default_ref: str = "tag") -> str:
        """`golden`(골든 폴더 기준) · `file`(저장소 경로) · `local`(story 폴더 기준) 중 하나."""
        if "local" in spec:
            p = self.dir / spec["local"]
            return data_uri(p.read_bytes(), MIME.get(p.suffix.lower(), "image/png"))
        path = f"{self.app.goldens_dir}/{spec['golden']}" if "golden" in spec else spec["file"]
        key = (self.ref(spec, default_ref), path)
        if key not in self._cache:
            raw = git(self.cfg.root, "show", f"{key[0]}:{path}", binary=True)
            self._cache[key] = data_uri(raw, MIME.get(Path(path).suffix.lower(), "image/png"))
        return self._cache[key]

    def clip(self, clip_id: str) -> tuple[str, str, list[dict]]:
        """(base64, MIME, 챕터). 문서에는 H.264 MP4로 싣는다 — Safari·iOS는 WebM을 못 틀거나 data: 영상을 못 연다."""
        raw = self.media_dir / f"{clip_id}.raw.webm"
        meta_path = self.media_dir / f"{clip_id}.chapters.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {"lead": 0, "chapters": []}
        lead = float(meta.get("lead", 0))
        chapters = meta["chapters"]
        mp4 = self.media_dir / f"{clip_id}.mp4"
        if raw.exists() and (not mp4.exists() or mp4.stat().st_mtime < raw.stat().st_mtime) and h264_available():
            encode_clip(raw, mp4, lead)
        if mp4.exists():
            return base64.b64encode(mp4.read_bytes()).decode(), "video/mp4", chapters
        # H.264 인코더가 없으면 WebM으로 싣는다 — Chrome·Edge·Firefox에서만 재생된다
        webm = self.media_dir / f"{clip_id}.webm"
        source = webm if webm.exists() else raw
        if not source.exists():
            raise SystemExit(f"영상 '{clip_id}'가 없어요 — `build --record` 또는 {mp4}를 넣어요")
        print(f"△ {clip_id}: H.264 인코더(ffmpeg libx264)가 없어 WebM으로 실어요 — Safari·iPhone에서는 재생되지 않아요")
        if source == raw and not meta.get("encoded"):
            # 앞쪽 로딩 구간을 자르지 못했으니 챕터 시각을 그만큼 민다
            chapters = [{**c, "t": c["t"] + lead} for c in chapters]
        return base64.b64encode(source.read_bytes()).decode(), "video/webm", chapters


def h264_available() -> bool:
    if not shutil.which("ffmpeg"):
        return False
    out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    return "libx264" in out


def encode_clip(raw: Path, out: Path, lead: float) -> None:
    """녹화 원본을 앞쪽 로딩을 자르고 모든 브라우저가 트는 H.264 MP4(yuv420p, faststart)로 만든다."""
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{lead:.2f}", "-i", str(raw), "-c:v", "libx264",
         "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p", "-profile:v", "high",
         "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2:out_range=tv,format=yuv420p", "-color_range", "tv",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-movflags", "+faststart", "-an", str(out)],
        check=True,
    )


# ── 브라우저 도구 (record.mjs · check.mjs) ────────────────────────────────


def playwright_dir(cfg: Config, extra: list[Path] = ()) -> Path:
    """playwright 패키지가 있는 폴더. 프로젝트에 있으면 그것을, 없으면 캐시에 한 번 설치한다."""
    candidates = [*extra, cfg.root, *(cfg.root / a.record.get("cwd", "") for a in cfg.apps.values())]
    for c in candidates:
        if (c / "node_modules" / "playwright" / "package.json").exists():
            return c
    if not (CACHE / "node_modules" / "playwright" / "package.json").exists():
        print(f"playwright가 프로젝트에 없어 {CACHE}에 설치해요 (한 번만)")
        CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(["npm", "install", "--prefix", str(CACHE), "--no-save", "--silent", "playwright"], check=True)
    subprocess.run(["npx", "--prefix", str(CACHE), "playwright", "install", "chromium"], check=True,
                   capture_output=True)
    return CACHE


def node() -> str:
    for exe in ("node", "bun"):
        if shutil.which(exe):
            return exe
    raise SystemExit("node(18 이상) 또는 bun이 필요해요")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_http(url: str, timeout: float = 90) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3):
                return
        except Exception:  # noqa: BLE001 — 서버가 뜰 때까지 어떤 실패든 다시 시도한다
            time.sleep(0.5)
    raise SystemExit(f"{url}이 {timeout:.0f}초 안에 뜨지 않았어요")


def record_clips(cfg: Config, app: App, story_dir: Path, tag: str) -> None:
    """태그 시점 코드를 임시 worktree로 꺼내 띄우고 clips.json의 흐름을 녹화한다."""
    spec = story_dir / "clips.json"
    if not spec.exists() or not json.loads(spec.read_text()):
        return
    rec = app.record
    if not rec.get("serve") or not rec.get("url"):
        raise SystemExit(f"설정 apps.{app.key}.record에 serve·url이 없어 녹화할 수 없어요 (references/config.md)")
    out_dir = (story_dir / ".media").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    worktree = Path(tempfile.mkdtemp(prefix="release-showcase-"))
    worktree.rmdir()
    git(cfg.root, "worktree", "add", "--detach", str(worktree), tag)
    server = None
    try:
        cwd = worktree / rec.get("cwd", "")
        if rec.get("install"):
            subprocess.run(rec["install"], shell=True, cwd=cwd, check=True)
        port = free_port()
        server = subprocess.Popen(rec["serve"].replace("{port}", str(port)), shell=True, cwd=cwd,
                                  start_new_session=True)
        base = rec["url"].replace("{port}", str(port))
        wait_http(base)
        settings = {k: rec[k] for k in ("viewport", "scale", "ready", "browserArgs") if k in rec}
        subprocess.run(
            [node(), str(HERE / "record.mjs"), "--spec", str(spec.resolve()), "--out", str(out_dir),
             "--base-url", base, "--settings", json.dumps(settings)],
            env={**os.environ, "SHOWCASE_PLAYWRIGHT_DIR": str(playwright_dir(cfg, [cwd]))},
            check=True,
        )
    finally:
        if server is not None:
            os.killpg(server.pid, signal.SIGTERM)
            server.wait(timeout=15)
        git(cfg.root, "worktree", "remove", "--force", str(worktree))


def verify(cfg: Config, out: Path, story_dir: Path) -> int:
    """결과 HTML을 데스크톱·모바일 폭으로 열어 넘침·빈 이미지·영상·상호작용을 보고 화면을 남긴다."""
    return subprocess.run(
        [node(), str(HERE / "check.mjs"), "--html", str(out), "--out", str(story_dir / ".media" / "review")],
        env={**os.environ, "SHOWCASE_PLAYWRIGHT_DIR": str(playwright_dir(cfg))},
    ).returncode


# ── 변경 목록 ─────────────────────────────────────────────────────────────

PR_RE = re.compile(r"\(#(\d+)\)")
MERGE_RE = re.compile(r"^Merge pull request #(\d+)")
TYPE_RE = re.compile(r"^(\w+)(?:\(([^)]*)\))?!?:\s*(.+)$")
SKIP_RE = re.compile(r"^(Merge |release|sync|Release )", re.IGNORECASE)


def pr_numbers(cfg: Config, ref: str, last_only: bool = False) -> set[str]:
    """`ref` 히스토리 제목의 `(#N)`. `last_only`면 squash 제목마다 끝 번호(PR 자신)만 센다."""
    subjects = str(git(cfg.root, "log", "--format=%s", ref))
    merged = set(re.findall(r"^Merge pull request #(\d+)", subjects, re.M))
    if last_only:
        return {n for s in subjects.splitlines() for n in PR_RE.findall(s)[-1:]} | merged
    return set(PR_RE.findall(subjects)) | merged


def collect_changes(cfg: Config, app: App, tag: str, base: str) -> list[dict]:
    """base 히스토리에 없던 PR만 — 태그끼리 조상 관계가 아니어도 맞는다.

    - `base..tag`는 브랜치가 갈라져 있으면 base에 cherry-pick으로 이미 들어간 PR까지 담으므로 PR 번호로
      한 번 더 거른다.
    - squash 머지는 제목의 `(#N)`, merge 커밋 머지는 `Merge pull request #N`과 본문 첫 줄(PR 제목)을 쓴다.
    - 동기화·릴리스 PR을 squash로 넣었으면(`release…` 커밋) 본문의 `* 제목 (#N)` 줄이 실제 변경이다. 그
      커밋은 경로로 가를 수 없으니 scope가 이 앱 것인 줄만 담는다.
    """
    released, released_refs = pr_numbers(cfg, base, last_only=True), pr_numbers(cfg, base)
    paths = ["--", app.source_dir] if app.source_dir else []
    raw = str(git(cfg.root, "log", "--format=%h%x1f%cs%x1f%s%x1f%b%x1e", f"{base}..{tag}", *paths))
    entries: list[tuple[str, str, str, list[str], bool]] = []
    for record in raw.split("\x1e"):
        if not record.strip():
            continue
        sha, day, subject, body = record.strip("\n").split("\x1f", 3)
        if m := MERGE_RE.match(subject):
            title = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
            entries.append((sha, day, title, [m.group(1)], False))
        elif subject.startswith(("release", "Release")):
            entries += [(sha, day, ln[2:].strip(), PR_RE.findall(ln), True) for ln in body.splitlines()
                        if ln.startswith("* ") and PR_RE.search(ln)]
        elif not subject.startswith("Merge "):
            entries.append((sha, day, subject, PR_RE.findall(subject), False))
    # 제목 끝의 `(#N)`이 그 PR이다. 앞의 `(#N)`은 이슈 참조이거나 cherry-pick·forward-port한 원래 PR이라
    # 링크·PR 본문 조회에는 쓰지 않고 중복 판정에만 쓴다.
    changes, seen, seen_refs = [], set(released), set(released_refs)
    for sha, day, subject, refs, bundled in entries:
        prs, earlier = refs[-1:], refs[:-1]
        if SKIP_RE.match(subject) or (not prs and not cfg.include_direct_commits):
            continue
        # 이미 나온 번호(되돌린 PR, 릴리스 본문의 브랜치 커밋 줄)거나 이미 나간 PR을 옮겨 온 줄이면 뺀다
        if any(p in seen_refs for p in prs) or any(p in seen for p in earlier):
            continue
        m = TYPE_RE.match(subject)
        kind, scope, text = (m.group(1), m.group(2) or "", m.group(3)) if m else ("other", "", subject)
        ours = not app.ship_scopes or any(k in scope for k in app.ship_scopes)
        if bundled and not ours:
            continue
        seen.update(prs)
        seen_refs.update(refs)
        text = PR_RE.sub("", text).strip()
        group = kind if kind in ("feat", "fix") else "other"
        if scope and not ours:
            group = "other"  # 개발 도구·CI처럼 배포본에 실리지 않는 범위
        if kind == "chore" and re.search(r"버전을|bump version|version bump", text, re.I):
            continue  # 버전 올리기 커밋은 목록에 의미가 없다
        changes.append({"sha": sha, "day": day, "scope": scope, "text": text, "prs": prs, "group": group})
    return changes


def release_assets(cfg: Config, tag: str) -> tuple[str, list[dict]]:
    url = f"https://github.com/{cfg.repo}/releases/tag/{tag}" if cfg.repo else ""
    if not cfg.repo:
        return url, []
    try:
        out = subprocess.run(["gh", "release", "view", tag, "--repo", cfg.repo, "--json", "url,assets"],
                             check=True, capture_output=True, text=True, timeout=30).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return url, []
    data = json.loads(out)
    skip = (".blockmap", ".yml", ".yaml", ".sha256", ".sig", ".txt", ".json")
    return data["url"], [a for a in data["assets"] if not a["name"].endswith(skip)]


# ── 렌더링 ────────────────────────────────────────────────────────────────


class Renderer:
    def __init__(self, cfg: Config, story: dict, media: Media, labels: dict[str, str]):
        self.cfg, self.story, self.media, self.labels = cfg, story, media, labels
        self.inline = Inline(cfg.repo)

    def pr_link(self, p: str) -> str:
        return f'<a class="pr" href="https://github.com/{self.cfg.repo}/pull/{p}">#{p}</a>' if self.cfg.repo else f"#{p}"

    def shot(self, spec: dict, cls: str = "") -> str:
        cap = spec.get("caption")
        alt = html.escape(plain(cap) if cap else spec.get("golden", spec.get("file", spec.get("local", ""))))
        img = f'<img src="{self.media.image(spec)}" alt="{alt}" data-zoom>'
        ver = self.labels.get(spec.get("ref", "tag"), "")
        badge = f'<span class="ver">{html.escape(ver)}</span>' if spec.get("showVersion") else ""
        caption = f"<figcaption>{self.inline(cap)}</figcaption>" if cap else ""
        return f'<figure class="shot {cls}"><div class="window">{badge}{img}</div>{caption}</figure>'

    def media_block(self, m: dict | None) -> str:
        if m is None:
            return ""
        kind = m.get("kind", "image")
        if kind == "image":
            return self.shot(m)
        if kind == "row":
            return '<div class="row">' + "".join(self.shot(s) for s in m["items"]) + "</div>"
        if kind == "stack":
            return '<div class="stack">' + "".join(self.media_block(x) for x in m["items"]) + "</div>"
        return getattr(self, kind)(m)

    def compare(self, m: dict) -> str:
        before, after = m["before"], m["after"]
        bl = before.get("label") or self.labels.get(before.get("ref", "base"), "이전")
        al = after.get("label") or self.labels.get(after.get("ref", "tag"), "이후")
        cap = f"<figcaption>{self.inline(m['caption'])}</figcaption>" if m.get("caption") else ""
        return f"""
<figure class="compare" data-compare>
  <div class="compare-toggle" role="tablist">
    <button type="button" data-side="before">이전 · {html.escape(bl)}</button>
    <button type="button" data-side="split" class="on">나란히</button>
    <button type="button" data-side="after">이후 · {html.escape(al)}</button>
  </div>
  <div class="compare-stage split">
    <div class="side before"><div class="window"><span class="ver">{html.escape(bl)}</span>
      <img src="{self.media.image(before, "base")}" alt="이전 화면" data-zoom></div></div>
    <div class="arrow" aria-hidden="true">→</div>
    <div class="side after"><div class="window"><span class="ver new">{html.escape(al)}</span>
      <img src="{self.media.image(after)}" alt="이후 화면" data-zoom></div></div>
  </div>
  {cap}
</figure>"""

    def steps(self, m: dict) -> str:
        items = m["items"]
        dots = "".join(
            f'<button type="button" class="dot{" on" if i == 0 else ""}" data-i="{i}">'
            f'<b>{html.escape(it.get("label", str(i + 1)))}</b><span>{html.escape(it.get("title", ""))}</span></button>'
            for i, it in enumerate(items)
        )
        slides = "".join(
            f'<div class="slide{" on" if i == 0 else ""}"><div class="window">'
            f'<img src="{self.media.image(it)}" alt="{html.escape(it.get("title", ""))}" data-zoom></div>'
            f'<p>{self.inline(it.get("caption", ""))}</p></div>'
            for i, it in enumerate(items)
        )
        return f"""
<div class="stepper" data-stepper>
  <div class="stepper-nav">{dots}</div>
  <div class="stepper-body">
    <button type="button" class="nav prev" aria-label="이전">‹</button>
    <div class="slides">{slides}</div>
    <button type="button" class="nav next" aria-label="다음">›</button>
  </div>
</div>"""

    def tabs(self, m: dict) -> str:
        items = m["items"]
        heads = "".join(f'<button type="button" class="{"on" if i == 0 else ""}" data-i="{i}">'
                        f'{html.escape(it["label"])}</button>' for i, it in enumerate(items))
        panes = "".join(f'<div class="pane{" on" if i == 0 else ""}">{self.shot(it)}</div>' for i, it in enumerate(items))
        return f'<div class="tabs" data-tabs><div class="tab-heads">{heads}</div>{panes}</div>'

    def video(self, m: dict) -> str:
        b64, mime, chapters = self.media.clip(m["clip"])
        poster = f' poster="{self.media.image(m["poster"])}"' if m.get("poster") else ""
        chap = "".join(
            f'<li><button type="button" data-t="{c["t"]:.2f}"><time>{int(c["t"]) // 60}:{int(c["t"]) % 60:02d}</time>'
            f"<span>{self.inline(c['caption'])}</span></button></li>"
            for c in chapters
        )
        return f"""
<div class="video" data-video>
  <div class="window video-frame">
    <video{poster} muted playsinline preload="auto" controls data-type="{mime}"></video>
    <script type="application/octet-stream" class="clip-data">{b64}</script>
    <button type="button" class="play" aria-label="재생">▶</button>
  </div>
  <ol class="chapters">{chap}</ol>
</div>"""

    def flow(self, m: dict) -> str:
        lanes = []
        for lane in m["lanes"]:
            steps = "".join(f'<li class="{html.escape(s.get("tone", ""))}">{self.inline(s["text"])}</li>'
                            for s in lane["steps"])
            lanes.append(f'<div class="lane {html.escape(lane.get("tone", ""))}"><h4>{self.inline(lane["title"])}</h4>'
                         f"<ol>{steps}</ol></div>")
        cap = f"<figcaption>{self.inline(m['caption'])}</figcaption>" if m.get("caption") else ""
        return f'<figure class="flow">{"".join(lanes)}{cap}</figure>'

    def highlight(self, i: int, h: dict) -> str:
        ink = self.inline
        points = "".join(f"<li>{ink(p)}</li>" for p in h.get("points", []))
        how = "".join(f"<li>{ink(p)}</li>" for p in h.get("how", []))
        who = "".join(f'<span class="who">{html.escape(w)}</span>' for w in h.get("who", []))
        prs = " ".join(self.pr_link(p) for p in h.get("prs", []))
        how_title = html.escape(h.get("howTitle", "이렇게 써 보세요"))
        return f"""
<section class="hl {h.get("layout", "side")}" id="{html.escape(h['id'])}">
  <div class="hl-text">
    <div class="hl-meta"><span class="badge {html.escape(h.get('badgeTone', 'new'))}">{html.escape(h['badge'])}</span>{who}</div>
    <h2><span class="num">{i:02d}</span>{ink(h['title'])}</h2>
    <p class="lead">{ink(h['lead'])}</p>
    {f'<ul class="points">{points}</ul>' if points else ''}
    {f'<div class="how"><h3>{how_title}</h3><ol>{how}</ol></div>' if how else ''}
    {f'<p class="prs">관련 PR {prs}</p>' if prs else ''}
  </div>
  <div class="hl-media">{self.media_block(h.get('media'))}</div>
</section>"""

    def minor(self, items: list[dict]) -> str:
        cards = "".join(f'<article class="mini">{self.media_block(it.get("media"))}<h3>{self.inline(it["title"])}</h3>'
                        f'<p>{self.inline(it["body"])}</p></article>' for it in items)
        return (f'<section class="minis" id="more"><h2 class="sec">그 밖에 눈에 띄는 변화</h2>'
                f'<div class="mini-grid">{cards}</div></section>')

    def changes(self, changes: list[dict]) -> str:
        counts = {g: sum(1 for c in changes if c["group"] == g) for g, _ in CHANGE_GROUPS}
        chips = "".join(f'<button type="button" class="chip on" data-group="{g}">{label} <b>{counts[g]}</b></button>'
                        for g, label in CHANGE_GROUPS)

        def row(c: dict) -> str:
            links = " ".join(self.pr_link(p) for p in c["prs"]) or c["sha"]
            return (f'<li data-group="{c["group"]}"><span class="g {c["group"]}"></span>'
                    f'<span class="t">{html.escape(c["text"])}</span><span class="m">{links} · {c["day"][5:]}</span></li>')

        return f"""
<section class="changes" id="changes">
  <h2 class="sec">전체 변경 목록 <small>{len(changes)}건</small></h2>
  <p class="hint">직전 정식 버전에 없던 변경만 모았어요. 버전 올리기 커밋은 뺐어요.</p>
  <div class="change-tools">{chips}<input type="search" placeholder="찾기" aria-label="변경 목록 찾기"></div>
  <ul class="change-list">{"".join(row(c) for c in changes)}</ul>
</section>"""

    def downloads(self, url: str, assets: list[dict]) -> str:
        def label(name: str) -> str:
            n = name.lower()
            for test, text in ((n.endswith(".exe") or n.endswith(".msi"), "Windows"),
                               (n.endswith(".dmg") and "arm64" in n, "macOS · Apple 칩"),
                               (n.endswith((".dmg", ".pkg")), "macOS"),
                               (n.endswith((".appimage", ".deb", ".rpm")), "Linux"),
                               (n.endswith((".apk", ".aab")), "Android"), (n.endswith(".ipa"), "iOS")):
                if test:
                    return text
            return name

        items = "".join(f'<a class="dl" href="{html.escape(a["url"])}"><b>{label(a["name"])}</b>'
                        f'<span>{html.escape(a["name"])} · {a["size"] / 1_000_000:.0f}MB</span></a>' for a in assets)
        if not items and not url:
            return ""
        ghost = f'<a class="dl ghost" href="{html.escape(url)}"><b>GitHub Release</b><span>원문 노트·이력</span></a>' if url else ""
        return f"""
<section class="downloads" id="download">
  <h2 class="sec">설치·업데이트</h2>
  <p class="hint">{self.inline(self.story.get("downloadNote", ""))}</p>
  <div class="dl-grid">{items}{ghost}</div>
</section>"""


def build(cfg: Config, story_dir: Path, out: Path, record: bool) -> Path:
    story = load_story(story_dir)
    app = cfg.apps[story["app"]]
    tag, base = story["tag"], story["base"]
    refs = {"tag": tag, "base": base}
    short = lambda t: t.removeprefix(app.tag_prefix)  # noqa: E731
    labels = {"tag": story.get("versionLabel", short(tag)), "base": story.get("baseLabel", short(base))}
    if record:
        record_clips(cfg, app, story_dir, tag)

    media = Media(cfg, app, refs, story_dir)
    r = Renderer(cfg, story, media, labels)
    ink = r.inline
    changes = collect_changes(cfg, app, tag, base)
    url, assets = release_assets(cfg, tag)
    icon = ""
    if app.icon:
        icon = f'<img src="{media.image({"file": app.icon})}" alt="">'
    audience = "".join(f'<div class="aud"><h3>{ink(a["who"])}</h3><p>{ink(a["what"])}</p></div>'
                       for a in story.get("audience", []))
    downloads = r.downloads(url, assets)
    toc = "".join(f'<a href="#{html.escape(h["id"])}">{ink(h.get("short", h["title"]))}</a>' for h in story["highlights"])
    toc += '<a href="#more">그 밖에</a>' if story.get("minor") else ""
    toc += '<a href="#changes">전체 변경</a>' + ('<a href="#download">설치</a>' if downloads else "")
    notes = "".join(f'<details class="note"><summary>{ink(n["title"])}</summary>'
                    + "".join(f"<p>{ink(p)}</p>" for p in n["body"]) + "</details>" for n in story.get("notes", []))
    body = {
        "TITLE": html.escape(story["title"]), "ICON": icon, "APP": html.escape(app.label),
        "VERSION": html.escape(labels["tag"]), "DATE": html.escape(story["date"]),
        "CHANNEL": html.escape(story.get("channel", "production")), "TAGLINE": ink(story["tagline"]),
        "CONTEXT": ink(story.get("context", "")), "AUDIENCE": audience, "TOC": toc,
        "HIGHLIGHTS": "".join(r.highlight(i + 1, h) for i, h in enumerate(story["highlights"])),
        "MINOR": r.minor(story["minor"]) if story.get("minor") else "",
        "NOTES": f'<section class="notes" id="notes"><h2 class="sec">팀 참고</h2>{notes}</section>' if notes else "",
        "CHANGES": r.changes(changes), "DOWNLOADS": downloads,
        "FOOTER": ink(f"{base} → {tag} · 화면은 저장소에 커밋된 스크린샷과 녹화예요"),
        "FRAME_W": str(cfg.frame_width), "VIDEO_W": str(cfg.video_width), "BRAND": cfg.brand, "BRAND_2": blend(cfg.brand, 0.18), "BRAND_SOFT": blend(cfg.brand, 0.9),
    }
    page = TEMPLATE.read_text()
    for key, value in body.items():
        page = page.replace("{{" + key + "}}", value)
    out.write_text(page)
    return out


# ── 검사 ──────────────────────────────────────────────────────────────────
#
# 글을 잘 쓰는 법은 SKILL.md가 가르치지만, 지켰는지는 여기서 기계로 본다. 오류(✗)가 하나라도 있으면
# 빌드하지 않는다. 경고(△)는 고치거나, 그대로 둘 이유를 알고 둔다.


def ref_exists(cfg: Config, ref: str, path: str | None = None) -> bool:
    target = f"{ref}:{path}" if path else f"{ref}^{{commit}}"
    return subprocess.run(["git", "-C", str(cfg.root), "cat-file", "-e", target], capture_output=True).returncode == 0


class Report:
    def __init__(self) -> None:
        self.items: list[tuple[str, str, str]] = []

    def error(self, where: str, msg: str) -> None:
        self.items.append(("✗", where, msg))

    def warn(self, where: str, msg: str) -> None:
        self.items.append(("△", where, msg))

    def info(self, where: str, msg: str) -> None:
        self.items.append(("·", where, msg))

    @property
    def errors(self) -> int:
        return sum(1 for k, _, _ in self.items if k == "✗")

    def print(self) -> None:
        for kind, where, msg in sorted(self.items, key=lambda x: "✗△·".index(x[0])):
            print(f"{kind} {where}: {msg}")
        warns = sum(1 for k, _, _ in self.items if k == "△")
        print(f"\n검사: 오류 {self.errors} · 경고 {warns}")


def media_captions(m: dict | None) -> list[str]:
    if not isinstance(m, dict):
        return []
    caps = [m[k] for k in ("caption", "title", "label", "text") if isinstance(m.get(k), str)]
    for key in ("items", "lanes", "steps"):
        for child in m.get(key, []):
            caps += media_captions(child)
    for key in ("before", "after", "poster"):
        caps += media_captions(m.get(key))
    return caps


def prose(story: dict) -> list[tuple[str, str, bool]]:
    """(위치, 글, 문장인가) — 문장은 해요체로 끝나야 하고, 제목·라벨은 명사형이어도 된다."""
    out: list[tuple[str, str, bool]] = [("tagline", story.get("tagline", ""), False),
                                         ("context", story.get("context", ""), True),
                                         ("downloadNote", story.get("downloadNote", ""), True)]
    for i, a in enumerate(story.get("audience", [])):
        out += [(f"audience[{i}].who", a.get("who", ""), False), (f"audience[{i}].what", a.get("what", ""), True)]
    for h in story.get("highlights", []):
        hid = h.get("id", "?")
        out += [(f"{hid}.title", h.get("title", ""), False), (f"{hid}.lead", h.get("lead", ""), True)]
        out += [(f"{hid}.points", p, True) for p in h.get("points", [])]
        out += [(f"{hid}.how", p, True) for p in h.get("how", [])]
        out += [(f"{hid}.media", c, False) for c in media_captions(h.get("media"))]
    for i, m in enumerate(story.get("minor", [])):
        out += [(f"minor[{i}].title", m.get("title", ""), False), (f"minor[{i}].body", m.get("body", ""), True)]
        out += [(f"minor[{i}].media", c, False) for c in media_captions(m.get("media"))]
    return out


def ui_labels(text: str) -> list[str]:
    """글에 쓴 화면 문구 — 영문만이 아닌 `문구`와 **설정 › 메뉴** 경로의 마디."""
    labels = [c for c in re.findall(r"`([^`]+)`", text) if not c.isascii()]
    for path in re.findall(r"\*\*([^*]*›[^*]*)\*\*", text):
        labels += [seg.strip() for seg in path.split("›")]
    return [label for label in labels if label and not label.isascii()]


class Checker:
    def __init__(self, cfg: Config, story_dir: Path, story: dict):
        self.cfg, self.dir, self.story = cfg, story_dir, story
        self.r = Report()
        self.app = cfg.apps.get(story.get("app", ""))
        self.refs = {"tag": story.get("tag", ""), "base": story.get("base", "")}
        clips = story_dir / "clips.json"
        self.clips = json.loads(clips.read_text()) if clips.exists() else []
        self.clip_ids = {c["id"] for c in self.clips}
        self.clip_ids |= {p.name.split(".")[0] for ext in ("*.webm", "*.mp4") for p in (story_dir / ".media").glob(ext)}
        self._ui: dict[str, bool] = {}

    def run(self) -> Report:
        s, r = self.story, self.r
        for key in ("app", "tag", "base", "title", "date", "tagline", "highlights"):
            if not s.get(key):
                r.error("story", f"`{key}`가 비어 있어요")
        if self.app is None:
            r.error("app", f"설정의 apps 중 하나여야 해요: {sorted(self.cfg.apps)} (지금 {s.get('app')!r})")
            return r
        for key in ("tag", "base"):
            if s.get(key) and not ref_exists(self.cfg, s[key]):
                r.error(key, f"태그 {s[key]}가 없어요 — `git fetch --tags`")
        if re.search(r"staging|beta|rc|alpha|nightly", s.get("base", ""), re.I):
            r.error("base", "사전 배포 태그는 기준이 될 수 없어요 — 사용자가 직전에 쓰던 정식 태그를 넣어요")
        if r.errors:
            return r
        self.check_text()
        self.check_clips()
        self.check_highlights()
        self.check_prs()
        self.check_labels()
        return r

    def strings(self, node: object, where: str = "story") -> list[tuple[str, str]]:
        if isinstance(node, str):
            return [(where, node)]
        if isinstance(node, list):
            return [x for i, v in enumerate(node) for x in self.strings(v, f"{where}[{i}]")]
        if isinstance(node, dict):
            skip = {"golden", "file", "local", "ref", "clip", "kind", "tone", "badgeTone", "layout", "id", "app",
                    "tag", "base"}
            return [x for k, v in node.items() if k not in skip for x in self.strings(v, f"{where}.{k}")]
        return []

    def check_text(self) -> None:
        for where, text in self.strings(self.story):
            if "TODO" in text:
                self.r.error(where, "TODO가 남아 있어요")
            if self.cfg.deny and (m := self.cfg.deny.search(text)):
                self.r.error(where, f"쓰지 않기로 한 말 `{m.group(0)}`(설정 denyPattern) — 지우거나 PR 링크로 가리켜요")
        for where, text, sentence in prose(self.story):
            t = plain(text)
            for word in self.cfg.jargon:
                if re.search(rf"(?<![A-Za-z가-힣]){re.escape(word)}(?![A-Za-z])", t):
                    self.r.warn(where, f"내부 구현어 `{word}` — 사용자가 겪는 말로 바꾸거나 notes로 옮겨요")
            if sentence and self.cfg.tone != "off":
                # 해요체 문서에 섞인 다·니다 끝, 합니다체 문서에 섞인 요 끝을 잡는다
                wrong = r"(니다|[했였었한된]다|이다|있다|없다|한다|된다)$" if self.cfg.tone == "해요체" else r"요$"
                for sent in re.split(r"(?<=[.!?])\s+", t.strip()):
                    tail = re.sub(r"[\s.!?\"'”’)\]]+$", "", sent)
                    if re.search(wrong, tail):
                        self.r.warn(where, f"{self.cfg.tone}가 아니에요: …{tail[-20:]}")
            elif len(t) > 60:
                self.r.warn(where, f"제목·라벨이 길어요 ({len(t)}자) — 60자 안으로")

    def check_clips(self) -> None:
        """녹화가 쓰는 파일(실제 자료·목 응답·첨부)이 있는지 — 실데이터는 저장소 밖(.media/)이라 빠지기 쉽다."""
        for c in self.clips:
            paths = [c[k] for k in ("initScript", "initData") if c.get(k)]
            paths += [f for st in c.get("steps", []) for f in st.get("upload", [])]
            for rel in paths:
                if not (self.dir / rel).exists():
                    hint = " — 실제 자료는 커밋하지 않으니 원본을 받아 같은 자리에 둬요" if ".media" in rel else ""
                    self.r.error(f"clips.{c.get('id', '?')}", f"{rel}이 없어요{hint}")

    def check_highlights(self) -> None:
        r, hs = self.r, self.story.get("highlights", [])
        if not 3 <= len(hs) <= 6:
            r.warn("highlights", f"{len(hs)}개 — 3~6개가 읽기 좋아요. 나머지는 minor 카드로")
        if not 2 <= len(self.story.get("audience", [])) <= 4:
            r.warn("audience", "독자별 카드 2~4개 — 각자 할 일이 있는지 먼저 말해요")
        seen: set[str] = set()
        for h in hs:
            hid = h.get("id", "?")
            if hid in seen:
                r.error(hid, "id가 겹쳐요")
            seen.add(hid)
            for key in ("id", "short", "badge", "title", "lead"):
                if not h.get(key):
                    r.error(hid, f"`{key}`가 비어 있어요")
            tone = h.get("badgeTone", "new")
            if tone not in HIGHLIGHT_TONES:
                r.error(hid, f"badgeTone은 {sorted(HIGHLIGHT_TONES)} 중 하나")
            if not h.get("media"):
                r.error(hid, "시각 자료(media)가 없어요 — 하이라이트마다 하나는 있어야 해요")
            if not h.get("how") and tone in ("new", "better"):
                r.warn(hid, "`how`(따라 할 순서·알아 둘 점)가 없어요")
            if not h.get("prs") and self.cfg.repo:
                r.warn(hid, "관련 PR이 없어요")
            sentences = [x for x in re.split(r"(?<=[.!?])\s+", plain(h.get("lead", ""))) if x]
            if len(sentences) > 3:
                r.warn(hid, f"lead가 {len(sentences)}문장 — 예전·지금 두 문장으로")
            if len(h.get("points", [])) > 6:
                r.warn(hid, "points가 6개를 넘어요")
            self.check_media(hid, h.get("media"))
        for i, m in enumerate(self.story.get("minor", [])):
            self.check_media(f"minor[{i}]", m.get("media"))

    def image_blob(self, spec: dict, default_ref: str) -> str | None:
        """그림의 내용 식별자 — 없으면 None."""
        if "local" in spec:
            p = self.dir / spec["local"]
            return f"local:{hashlib.sha1(p.read_bytes()).hexdigest()}" if p.exists() else None
        if "golden" not in spec and "file" not in spec:
            return None
        if "golden" in spec and not self.app.goldens_dir:
            return None
        path = f"{self.app.goldens_dir}/{spec['golden']}" if "golden" in spec else spec["file"]
        ref = self.refs.get(spec.get("ref", default_ref), spec.get("ref", default_ref))
        out = subprocess.run(["git", "-C", str(self.cfg.root), "rev-parse", f"{ref}:{path}"], capture_output=True, text=True)
        return out.stdout.strip() if out.returncode == 0 else None

    def check_image(self, where: str, spec: dict, default_ref: str = "tag") -> None:
        if self.image_blob(spec, default_ref) is None:
            name = spec.get("golden") or spec.get("file") or spec.get("local") or "?"
            ref = self.refs.get(spec.get("ref", default_ref), spec.get("ref", default_ref))
            hint = "`goldens`로 이름을 확인해요" if "golden" in spec else "경로를 확인해요"
            self.r.error(where, f"그림 {name}이 {'story 폴더' if 'local' in spec else ref}에 없어요 — {hint}")

    def check_media(self, where: str, m: dict | None, default_ref: str = "tag") -> None:
        if m is None:
            return
        r, kind = self.r, m.get("kind", "image")
        if kind not in MEDIA_KINDS:
            r.error(where, f"알 수 없는 media kind {kind!r}")
        elif kind == "image":
            self.check_image(where, m, default_ref)
        elif kind == "compare":
            for side, ref in (("before", "base"), ("after", "tag")):
                if side not in m:
                    r.error(where, f"compare에 `{side}`가 없어요")
                else:
                    self.check_image(f"{where}.{side}", m[side], ref)
            if "before" in m and "after" in m:
                b = self.image_blob(m["before"], "base")
                if b and b == self.image_blob(m["after"], "tag"):
                    r.error(where, "이전·이후가 같은 그림이에요 — 바뀌지 않은 화면은 image로")
        elif kind == "video":
            if m.get("clip") not in self.clip_ids:
                r.error(where, f"영상 {m.get('clip')!r}이 clips.json에도 .media/에도 없어요")
            if m.get("poster"):
                self.check_image(f"{where}.poster", m["poster"])
        elif kind == "flow":
            if len(m.get("lanes", [])) < 2:
                r.warn(where, "flow는 이전·이후 두 줄을 나란히 둘 때 써요")
        else:
            items = m.get("items", [])
            if kind in ("steps", "tabs") and len(items) < 2:
                r.warn(where, f"{kind}는 두 장 이상일 때 쓰고, 한 장이면 image로")
            for i, it in enumerate(items):
                if kind == "stack":
                    self.check_media(f"{where}.stack[{i}]", it)
                else:
                    self.check_image(f"{where}.{kind}[{i}]", it)

    def check_prs(self) -> None:
        """하이라이트에 단 PR이 태그에 실제로 들어 있는지 — 머지됐지만 아직 안 나간 기능을 막는다."""
        if not self.cfg.repo:
            return
        in_tag, in_base = pr_numbers(self.cfg, self.refs["tag"]), pr_numbers(self.cfg, self.refs["base"])
        cited: set[str] = set()
        for h in self.story.get("highlights", []):
            prs = set(h.get("prs", [])) | set(re.findall(r"#(\d{1,6})\b", json.dumps(h, ensure_ascii=False)))
            cited |= prs
            for p in sorted(prs):
                if p not in in_tag:
                    self.r.error(h.get("id", "?"), f"#{p}는 {self.refs['tag']}에 없어요 — 아직 나가지 않은 변경이에요")
                elif p in in_base:
                    self.r.warn(h.get("id", "?"), f"#{p}는 이미 {self.refs['base']}에 있던 변경이에요")
        rest = json.dumps([self.story.get("minor", []), self.story.get("notes", [])], ensure_ascii=False)
        cited |= set(re.findall(r"#(\d{1,6})\b", rest))
        missed = [c for c in collect_changes(self.cfg, self.app, self.refs["tag"], self.refs["base"])
                  if c["group"] == "feat" and not set(c["prs"]) & cited]
        if missed:
            listing = "; ".join(f"#{c['prs'][0] if c['prs'] else c['sha']} {c['text'][:40]}" for c in missed[:12])
            self.r.info("범위", f"글에 안 쓴 새 기능 {len(missed)}건 — 빠뜨린 게 없는지 봐요: {listing}")

    def check_labels(self) -> None:
        """`문구`·**설정 › 메뉴**로 쓴 말이 태그 시점 앱 소스에 그대로 있는지 본다."""
        if not self.app.ui_dir:
            return
        for where, text, _ in prose(self.story):
            for label in ui_labels(text):
                if label not in self._ui:
                    hit = subprocess.run(["git", "-C", str(self.cfg.root), "grep", "-q", "-F", "-e", label,
                                          self.refs["tag"], "--", self.app.ui_dir], capture_output=True)
                    self._ui[label] = hit.returncode == 0
                if not self._ui[label]:
                    self.r.warn(where, f"`{label}`를 앱 소스({self.app.ui_dir})에서 찾지 못했어요 — 앱 문구 그대로 써요")


def check(cfg: Config, story_dir: Path) -> Report:
    story = load_story(story_dir)
    report = Checker(cfg, story_dir, story).run()
    copy = story_dir / ".media" / "copy.txt"
    copy.parent.mkdir(exist_ok=True)
    # 한국어 문장 린트(ko-natural 등)에 그대로 넣을 수 있게 사람이 읽는 글만 모은다
    copy.write_text("\n".join(plain(t) for _, t, _ in prose(story) if t) + "\n")
    report.print()
    print(f"글 모음: {copy}")
    return report


# ── 초안 ──────────────────────────────────────────────────────────────────

PRE_RE = re.compile(r"staging|beta|alpha|rc\.?\d|nightly|canary|preview", re.I)


def production_tags(cfg: Config, app: App) -> list[tuple[str, str]]:
    """(태그, 날짜) 오래된 순 — 사전 배포 태그 제외."""
    out = str(git(cfg.root, "tag", "-l", f"{app.tag_prefix}*", "--sort=creatordate",
                  "--format=%(refname:short)\t%(creatordate:short)"))
    rows = [line.split("\t") for line in out.splitlines()]
    return [(t, d) for t, d in rows if not PRE_RE.search(t.removeprefix(app.tag_prefix))]


def suggest_base(cfg: Config, app: App, tag: str) -> tuple[str, list[str]]:
    """사용자가 실제로 머물던 직전 정식 버전 — 며칠 만에 다음 버전이 나온 핫픽스 사슬은 건너뛴다."""
    tags = production_tags(cfg, app)
    names = [t for t, _ in tags]
    if tag not in names:
        raise SystemExit(f"정식 태그 {tag}가 없어요 — `git fetch --tags`")
    i = names.index(tag)
    if i == 0:
        raise SystemExit("직전 정식 태그가 없어요 — --base로 지정해요")
    why, j = [], i - 1
    while j > 0:
        life = (date.fromisoformat(tags[j + 1][1]) - date.fromisoformat(tags[j][1])).days
        if life >= LIFETIME_DAYS:
            break
        why.append(f"{tags[j][0]}({tags[j][1]})는 {life}일 만에 다음 버전이 나와 건너뜀")
        j -= 1
    why.append(f"{tags[j][0]}({tags[j][1]})를 기준으로 씀 — 사용자가 직전에 실제로 쓰던 정식 버전인지 확인해요")
    return tags[j][0], why


def pr_brief(cfg: Config, number: str) -> str:
    try:
        out = subprocess.run(["gh", "pr", "view", number, "--repo", cfg.repo, "--json", "body"],
                             check=True, capture_output=True, text=True, timeout=30).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return "(PR 본문을 읽지 못함 — `gh auth status`)"
    body = re.sub(r"<!--.*?-->", "", json.loads(out).get("body") or "", flags=re.S)
    body = re.sub(r"\n{2,}", "\n", body).strip()
    return body[:700] + ("…" if len(body) > 700 else "")


def init(cfg: Config, tag: str, base: str | None, force: bool) -> None:
    app = app_for_tag(cfg, tag)
    why = [f"--base로 {base}를 지정"] if base else []
    if base is None:
        base, why = suggest_base(cfg, app, tag)
    story_dir = cfg.stories_dir / tag
    story_path = story_dir / "story.json"
    if story_path.exists() and not force:
        raise SystemExit(f"{story_path}가 이미 있어요 — 덮어쓰려면 --force")
    (story_dir / ".media").mkdir(parents=True, exist_ok=True)
    version, base_version = tag.removeprefix(app.tag_prefix), base.removeprefix(app.tag_prefix)
    day = str(git(cfg.root, "log", "-1", "--format=%cs", tag)).strip()
    todo = "TODO"
    story = {
        "app": app.key, "title": f"{app.label} {version} — 무엇이 달라졌나", "tag": tag, "base": base,
        "date": day, "channel": "production", "tagline": f"{todo}: 사용자가 얻는 것 한 문장",
        "context": f"**{base_version}을 쓰던 분이 {version}로 올렸을 때** 달라지는 점을 정리했어요.",
        "audience": [{"who": w, "what": f"{todo}: 할 일이 있는지 없는지 먼저"}
                     for w in ("처음 쓰는 분", "이미 쓰던 분", "지원·영업")],
        "highlights": [{
            "id": "todo", "short": todo, "badge": "새 기능", "badgeTone": "new", "who": ["모든 사용자"],
            "title": todo, "lead": f"{todo}: 예전에는 … 이제는 ….", "points": [todo], "how": [todo], "prs": [],
            "media": {"kind": "image", "golden": f"{todo}.png"},
        }],
        "minor": [],
        "notes": [{"title": "이 문서의 화면에 대해", "body": [
            "TODO: 화면 속 자료가 실제 사례(식별 정보 가림)인지, 테스트 데이터인지 적어요.", *cfg.notes]}],
        "downloadNote": "",
    }
    story_path.write_text(json.dumps(story, ensure_ascii=False, indent=2) + "\n")
    if app.record and not (story_dir / "clips.json").exists():
        (story_dir / "clips.json").write_text("[]\n")

    changes = collect_changes(cfg, app, tag, base)
    lines = [f"# {tag} 재료 묶음", "", "`showcase.py init`이 만든 작업 메모예요(커밋하지 않음).", "", "## 범위", "",
             *[f"- {w}" for w in why],
             f"- 변경 {len(changes)}건: " + ", ".join(f"{label} {sum(c['group'] == g for c in changes)}"
                                                     for g, label in CHANGE_GROUPS), ""]
    if app.goldens_dir:
        lines += ["## 화면 후보 (커밋된 스크린샷)", "", "새 화면은 하이라이트 후보, 바뀜은 minor 카드 후보예요.", "",
                  *[f"- {s} `{n}`" for s, n in golden_diff(cfg, app, base, tag)], ""]
    lines += ["## 새 기능·바뀐 동작 — PR 본문", ""]
    for c in (c for c in changes if c["group"] == "feat"):
        ref = f"#{c['prs'][0]}" if c["prs"] else c["sha"]
        lines += [f"### {ref} {c['text']}", "", pr_brief(cfg, c["prs"][0]) if c["prs"] and cfg.repo else "", ""]
    lines += ["## 고친 것", "", *[f"- {'#' + c['prs'][0] if c['prs'] else c['sha']} {c['text']}"
                                 for c in changes if c["group"] == "fix"], ""]
    brief = story_dir / ".media" / "brief.md"
    brief.write_text("\n".join(lines))
    print(f"✓ {story_path}\n✓ {brief}")
    print("\n".join(f"  {w}" for w in why))


def golden_diff(cfg: Config, app: App, base: str, tag: str) -> list[tuple[str, str]]:
    out = str(git(cfg.root, "diff", "--name-status", base, tag, "--", app.goldens_dir))
    marks = {"A": "새 화면", "M": "바뀜", "D": "사라짐", "R": "이름 바뀜"}
    return [(marks.get(st[0], st), Path(paths[-1]).name) for st, *paths in (ln.split("\t") for ln in out.splitlines())]


# ── CLI ───────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="story.json 초안과 재료 묶음(.media/brief.md)")
    p.add_argument("tag")
    p.add_argument("--base", help="기준 태그 (기본: 사용자가 머물던 직전 정식 태그)")
    p.add_argument("--force", action="store_true")
    for name, text in (("goldens", "이전·이후 사이에 생기거나 바뀐 스크린샷"), ("check", "글·자료 검사"),
                       ("verify", "만들어 둔 HTML을 데스크톱·모바일 폭으로 검수")):
        sub.add_parser(name, help=text).add_argument("target", help="태그 또는 story 폴더")
    p = sub.add_parser("build", help="검사 → (녹화) → HTML → (검수)")
    p.add_argument("target", help="태그 또는 story 폴더")
    p.add_argument("--record", action="store_true", help="태그 시점 코드로 clips.json 흐름을 새로 녹화")
    p.add_argument("--verify", action="store_true", help="만든 뒤 검수하고 화면을 남긴다")
    p.add_argument("--out", type=Path)
    a = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # 하위 프로세스 출력과 순서가 섞이지 않게
    cfg = load_config()
    if a.cmd == "init":
        init(cfg, a.tag, a.base, a.force)
        return 0
    story_dir = story_dir_for(cfg, a.target)
    out = (getattr(a, "out", None) or story_dir / f"{story_dir.name}.html").resolve()
    if a.cmd == "goldens":
        story = load_story(story_dir)
        for status, name in golden_diff(cfg, cfg.apps[story["app"]], story["base"], story["tag"]):
            print(f"{status:6} {name}")
        return 0
    if a.cmd == "verify":
        return verify(cfg, out, story_dir)
    report = check(cfg, story_dir)
    if a.cmd == "check" or report.errors:
        return 1 if report.errors else 0
    path = build(cfg, story_dir, out, a.record)
    size = path.stat().st_size / 1_000_000
    print(f"✓ {path} ({size:.1f}MB)")
    if size > 10:
        print("△ 10MB를 넘어요 — 메신저 첨부 한도에 걸릴 수 있어요. 영상을 줄이거나 steps로 바꿔요")
    return verify(cfg, path, story_dir) if a.verify else 0


if __name__ == "__main__":
    sys.exit(main())
