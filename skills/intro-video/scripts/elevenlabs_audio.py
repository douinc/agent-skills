#!/usr/bin/env python3
"""ElevenLabs로 소개 영상의 효과음·배경음악을 만든다. 표준 라이브러리와 ffmpeg만 쓴다.

OpenRouter 계정에 ZDR(데이터 무보존)을 강제하면 효과음·음악 모델이 대부분 거절된다. 그럴 때 쓰는 경로다.
사용자가 ElevenLabs 키를 쓰기로 했을 때만 실행한다(SKILL.md 1단계 질문).

  key-check  키를 어디서 찾았는지와 플랜·크레딧 사용량을 보여 준다(키 값은 보여 주지 않는다)
  sfx        설명문 → 효과음 WAV (0.5–30초). --project/--frame/--offset을 주면 audio_meta.json sfx에 등록
  music      설명문 → 배경음악 WAV (3–600초, 기본 연주곡). --project를 주면 audio_meta.json bgm에 등록

키는 스크립트가 직접 찾는다. 사람이나 에이전트가 키를 셸에 불러올 필요가 없다. 찾는 순서:
  1. 환경 변수 ELEVENLABS_API_KEY            (CI 등 주입되는 환경용)
  2. 환경 변수 ELEVENLABS_API_KEY_FILE이 가리키는 파일
  3. OS 키 저장소 — macOS 키체인(service=elevenlabs), Linux secret-tool(service elevenlabs)
     account는 ELEVENLABS_KEY_ACCOUNT(기본 intro-video)
  4. ${XDG_CONFIG_HOME:-~/.config}/elevenlabs/key
파일은 본인 소유이고 다른 사용자가 읽을 수 없어야(chmod 600) 쓴다. 레포의 .env는 읽지 않는다.

예:
  python3 elevenlabs_audio.py key-check
  python3 elevenlabs_audio.py sfx "soft UI click, short, clean, no reverb" -o assets/audio/sfx-click.wav --duration 0.6
  python3 elevenlabs_audio.py sfx "airy whoosh transition" -o assets/audio/sfx-whoosh.wav --duration 0.8 \\
      --project . --frame 2 --offset 0.1
  python3 elevenlabs_audio.py music "sophisticated upbeat minimal electronic, warm keys, 112 bpm" \\
      -o assets/audio/bed.wav --length 32 --project .
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
from pathlib import Path

API = "https://api.elevenlabs.io/v1"
DEFAULTS = {
    "sfx_model": "eleven_text_to_sound_v2",
    "music_model": "music_v1",
    "format": "mp3_44100_128",  # 무료 플랜에서도 되는 형식. 받은 뒤 WAV(PCM16)로 바꾼다
}

# ── 키 ───────────────────────────────────────────────────────────────────────
KEYCHAIN_SERVICE = "elevenlabs"
SETUP_HINT = """ElevenLabs 키를 찾지 못했다. 이 스킬 전용 키(권한·크레딧 한도를 건 키)를 만들어 아래 중 한 곳에 둔다.
  1) https://elevenlabs.io/app/settings/api-keys 에서 새 키를 만든다
     권한: Sound Effects, Music만 켠다(key-check까지 쓰려면 User 읽기도). 크레딧 한도를 건다
  2) 저장한다
  macOS 키체인(권장, 붙여넣기 프롬프트가 뜬다):
    security add-generic-password -U -s elevenlabs -a intro-video -w
  키 파일(레포 밖, 본인만 읽기):
    mkdir -p ~/.config/elevenlabs && (umask 077; read -rs k && printf '%s' "$k" > ~/.config/elevenlabs/key; unset k)
확인: python3 <SKILL_DIR>/scripts/elevenlabs_audio.py key-check
자세한 내용: references/elevenlabs.md '키'"""
_KEY = None  # (value, source)


def _read_key_file(path):
    p = Path(path).expanduser()
    if not p.is_file():
        return None
    st = p.stat()
    if os.name == "posix":
        if st.st_uid != os.getuid():
            sys.exit(f"{p}의 소유자가 현재 사용자가 아니다. 키 파일은 본인 소유여야 한다.")
        if st.st_mode & 0o077:
            sys.exit(f"{p}를 다른 사용자도 읽을 수 있다(권한 {oct(st.st_mode & 0o777)}). chmod 600 {p} 뒤 다시 실행한다.")
    return p.read_text().strip() or None


def _read_keystore(account):
    if sys.platform == "darwin" and shutil.which("security"):
        r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account, "-w"],
                           capture_output=True, text=True)
        return (r.stdout.strip() or None) if r.returncode == 0 else None
    if shutil.which("secret-tool"):
        r = subprocess.run(["secret-tool", "lookup", "service", KEYCHAIN_SERVICE, "account", account],
                           capture_output=True, text=True)
        return (r.stdout.strip() or None) if r.returncode == 0 else None
    return None


def resolve_key():
    """(키, 출처). 출처는 키 값이 아니라 어디서 찾았는지만 담는다."""
    global _KEY
    if _KEY:
        return _KEY
    account = os.environ.get("ELEVENLABS_KEY_ACCOUNT", "intro-video")
    config = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / "elevenlabs" / "key"
    candidates = [
        ("환경 변수 ELEVENLABS_API_KEY", lambda: os.environ.get("ELEVENLABS_API_KEY", "").strip() or None),
        ("ELEVENLABS_API_KEY_FILE", lambda: _read_key_file(os.environ["ELEVENLABS_API_KEY_FILE"])
            if os.environ.get("ELEVENLABS_API_KEY_FILE") else None),
        (f"OS 키 저장소(service={KEYCHAIN_SERVICE}, account={account})", lambda: _read_keystore(account)),
        (f"키 파일 {config}", lambda: _read_key_file(config)),
    ]
    for source, read in candidates:
        value = read()
        if value:
            if value.startswith("sk-or-"):
                sys.exit(f"{source}에 OpenRouter 키(sk-or-…)가 들어 있다. ElevenLabs 키를 따로 저장한다.")
            _KEY = (value, source)
            return _KEY
    sys.exit(SETUP_HINT)


def redact(text):
    """출력에 키가 섞이면 가린다. 키를 아직 찾지 않았으면 sk_ 형식만 가린다."""
    if _KEY:
        text = text.replace(_KEY[0], "sk_…(가림)")
    return re.sub(r"sk_[A-Za-z0-9]{16,}", "sk_…(가림)", text)


# ── HTTP ─────────────────────────────────────────────────────────────────────
def request(method, url, body=None, timeout=300, retries=2):
    """(status, headers, bytes). 429·5xx는 두 번까지 다시 시도한다. 키는 elevenlabs.io로 가는 요청에만 붙인다."""
    headers = {"Accept": "*/*"}
    host = urllib.parse.urlparse(url).hostname or ""
    if host == "elevenlabs.io" or host.endswith(".elevenlabs.io"):
        headers["xi-api-key"] = resolve_key()[0]
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode()
        headers["Content-Type"] = "application/json"
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            payload = e.read()
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(3 * (attempt + 1))
                continue
            hint = ""
            if b"missing_permissions" in payload:
                hint = ("\n→ 키에 이 기능 권한이 없다. ElevenLabs 대시보드의 API Keys에서 이 키의 권한"
                        "(Sound Effects / Music / User 읽기)을 켠다.")
            elif e.code == 401:
                hint = "\n→ 키가 틀렸거나 폐기됐다. key-check로 어떤 키를 쓰고 있는지 확인한다."
            elif b"quota_exceeded" in payload or e.code == 402:
                hint = "\n→ 크레딧이나 이 키의 크레딧 한도가 바닥났다. 한도를 올릴지는 사용자가 정한다."
            elif b"paid_plan_required" in payload or b"subscription" in payload.lower():
                hint = "\n→ 이 기능이나 출력 형식은 유료 플랜이 필요할 수 있다. 사용자에게 플랜을 확인한다."
            elif e.code == 403:
                hint = "\n→ 키의 IP 허용 목록이나 권한이 이 요청을 막았다."
            sys.exit(redact(f"{method} {url} → HTTP {e.code}: {payload[:600].decode(errors='replace')}{hint}"))
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(3 * (attempt + 1))
                continue
            sys.exit(redact(f"{method} {url} 연결 실패: {e.reason}"))


# ── 오디오 ───────────────────────────────────────────────────────────────────
def to_wav(raw, out, trim_to=None):
    """받은 오디오(mp3 등)를 WAV(PCM16)로 저장하고 길이(초)를 돌려준다."""
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg가 PATH에 없다")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(raw)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", tmp.name]
    if trim_to:
        cmd += ["-t", f"{trim_to:.3f}"]
    cmd += ["-c:a", "pcm_s16le", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    os.unlink(tmp.name)
    if r.returncode:
        sys.exit(f"오디오 변환 실패: {r.stderr.strip()}")
    with wave.open(str(out), "rb") as w:
        return round(w.getnframes() / w.getframerate(), 3)


def generate(path, body, fmt):
    q = urllib.parse.urlencode({"output_format": fmt})
    _, headers, raw = request("POST", f"{API}{path}?{q}", body)
    ct = next((v for k, v in headers.items() if k.lower() == "content-type"), "")
    if "json" in ct.lower():
        sys.exit(redact(f"오디오 대신 JSON이 왔다: {raw[:400].decode(errors='replace')}"))
    return raw, headers


def rel_to(root, out):
    try:
        return str(out.resolve().relative_to(root.resolve()))
    except ValueError:
        sys.exit(f"{out}가 프로젝트({root}) 밖에 있다. audio_meta.json에 등록하려면 프로젝트 안(assets/audio/)에 둔다.")


def update_meta(root, fn):
    path = root / "audio_meta.json"
    try:
        meta = json.loads(path.read_text())
    except FileNotFoundError:
        meta = {}
    meta.setdefault("bgm", None)
    meta.setdefault("sfx", [])
    fn(meta)
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return path


# ── 서브커맨드 ───────────────────────────────────────────────────────────────
def cmd_key_check(a):
    value, source = resolve_key()
    info = {"source": source, "key": f"…{value[-4:]}"}
    req =urllib.request.Request(f"{API}/user/subscription", headers={"xi-api-key": value})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
        info.update({
            "tier": d.get("tier"),
            "status": d.get("status"),
            "credits_used": d.get("character_count"),
            "credits_limit": d.get("character_limit"),
            "credits_reset": time.strftime("%Y-%m-%d", time.localtime(d["next_character_count_reset_unix"]))
            if d.get("next_character_count_reset_unix") else None,
        })
    except urllib.error.HTTPError as e:
        payload = e.read()
        if b"missing_permissions" in payload:
            info["note"] = ("키는 유효하지만 User 읽기 권한이 없어 플랜·사용량을 볼 수 없다. "
                            "sfx·music 권한만 있으면 생성은 된다.")
        else:
            sys.exit(redact(f"key-check 실패 HTTP {e.code}: {payload[:300].decode(errors='replace')}"
                            "\n→ 키가 틀렸거나 폐기됐다. 새 키를 만들어 같은 방법으로 다시 저장한다."))
    print(redact(json.dumps(info, ensure_ascii=False, indent=2)))
    if source.startswith("환경 변수"):
        print("경고: 키가 환경 변수에 있다. 그 셸에서 뜨는 모든 프로세스가 볼 수 있다. 키체인이나 키 파일로 옮긴다.",
              file=sys.stderr)
    if info.get("tier") == "free":
        print("경고: 무료 플랜이다. 무료 플랜 결과물은 상업적 사용이 제한될 수 있다. 납품 전에 사용자에게 "
              "플랜과 라이선스를 확인한다(references/elevenlabs.md '라이선스').", file=sys.stderr)


def cmd_sfx(a):
    if a.duration is not None and not 0.5 <= a.duration <= 30:
        sys.exit("--duration은 0.5–30초다")
    body = {"text": a.prompt, "model_id": a.model, "prompt_influence": a.influence}
    if a.duration is not None:
        body["duration_seconds"] = a.duration
    if a.loop:
        body["loop"] = True
    raw, _ = generate("/sound-generation", body, a.format)
    out = Path(a.output).with_suffix(".wav")
    dur = to_wav(raw, out)
    result = {"out": str(out), "duration_s": dur, "model": a.model, "prompt": a.prompt}
    if a.project:
        if a.frame is None:
            sys.exit("--project로 등록하려면 --frame(프레임 번호)과 --offset(프레임 안 시작 초)을 준다")
        root = Path(a.project)
        entry = {"frame": a.frame, "file": rel_to(root, out), "offset_s": a.offset, "duration_s": dur,
                 "volume": a.volume, "source": "host"}
        result["audio_meta"] = str(update_meta(root, lambda m: m["sfx"].append(entry)))
    print(json.dumps(result, ensure_ascii=False))


def cmd_music(a):
    if not 3 <= a.length <= 600:
        sys.exit("--length는 3–600초다")
    body = {"prompt": a.prompt, "music_length_ms": int(a.length * 1000), "model_id": a.model,
            "force_instrumental": not a.vocals}
    raw, headers = generate("/music", body, a.format)
    out = Path(a.output).with_suffix(".wav")
    dur = to_wav(raw, out)
    song_id = next((v for k, v in headers.items() if k.lower() in ("song-id", "x-song-id")), None)
    result = {"out": str(out), "duration_s": dur, "model": a.model, "prompt": a.prompt,
              "instrumental": not a.vocals, "song_id": song_id}
    if a.project:
        root = Path(a.project)
        bgm = {"path": rel_to(root, out), "volume": a.volume, "source": "host"}

        def put(m):
            m["bgm"] = bgm
            m["bgm_pending"] = False
        result["audio_meta"] = str(update_meta(root, put))
    print(json.dumps(result, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("key-check", help="키 출처·플랜·크레딧 확인(키 값은 출력하지 않음)")
    p.set_defaults(fn=cmd_key_check)

    p = sub.add_parser("sfx", help="설명문 → 효과음 WAV")
    p.add_argument("prompt", help="영어 설명문 권장. 예: 'soft UI click, short, clean, no reverb'")
    p.add_argument("-o", "--output", required=True, help="assets/audio/sfx-<이름>.wav")
    p.add_argument("--duration", type=float, help="0.5–30초. 없으면 모델이 정한다")
    p.add_argument("--influence", type=float, default=0.3, help="프롬프트 충실도 0–1(기본 0.3)")
    p.add_argument("--loop", action="store_true", help="끊김 없이 반복되는 소리")
    p.add_argument("--model", default=DEFAULTS["sfx_model"])
    p.add_argument("--format", default=DEFAULTS["format"])
    p.add_argument("--project", help="주면 <project>/audio_meta.json sfx에 host 항목으로 등록")
    p.add_argument("--frame", type=int, help="등록할 프레임 번호")
    p.add_argument("--offset", type=float, default=0.0, help="프레임 안에서 시작할 초")
    p.add_argument("--volume", type=float, default=1.0)
    p.set_defaults(fn=cmd_sfx)

    p = sub.add_parser("music", help="설명문 → 배경음악 WAV")
    p.add_argument("prompt", help="장르·분위기·악기·bpm. 실존 아티스트·곡 이름은 쓰지 않는다")
    p.add_argument("-o", "--output", required=True, help="assets/audio/bed.wav")
    p.add_argument("--length", type=float, required=True, help="초(3–600). 영상 길이 + 끝 여유 1–2초")
    p.add_argument("--vocals", action="store_true", help="보컬 허용(기본: 연주곡만)")
    p.add_argument("--model", default=DEFAULTS["music_model"])
    p.add_argument("--format", default=DEFAULTS["format"])
    p.add_argument("--project", help="주면 <project>/audio_meta.json bgm에 host 항목으로 등록")
    p.add_argument("--volume", type=float, default=1.0)
    p.set_defaults(fn=cmd_music)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
