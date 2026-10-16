#!/usr/bin/env python3
"""OpenRouter로 소개 영상의 소리·그림 재료를 만든다. 표준 라이브러리와 ffmpeg만 쓴다.

  models   현재 모델 목록(키 불필요). 모델 id는 자주 바뀌므로 쓰기 전에 확인한다
  tts      SCRIPT.md의 줄마다 음성 생성 → assets/voice/NN.wav + 단어 타이밍 → audio_meta.json
  measure  문장 하나를 읽는 데 걸리는 초(그래픽형 화면 문구의 최소 노출 시간)
  stt      오디오 → 단어 타이밍 JSON([{id,text,start,end}])
  image    프롬프트 → 이미지 파일(배경·텍스처용. 한글 글자는 이미지에 넣지 않는다)
  video    프롬프트 → 짧은 b-roll MP4(비동기 작업을 끝날 때까지 기다린다)
  key-check  키를 어디서 찾았는지와 한도·사용액·만료를 보여 준다(키 값은 보여 주지 않는다)

키는 스크립트가 직접 찾는다. 사람이나 에이전트가 키를 셸에 불러올 필요가 없다. 찾는 순서:
  1. 환경 변수 OPENROUTER_API_KEY            (CI 등 주입되는 환경용)
  2. 환경 변수 OPENROUTER_API_KEY_FILE이 가리키는 파일
  3. OS 키 저장소 — macOS 키체인(service=openrouter), Linux secret-tool(service openrouter)
     account는 OPENROUTER_KEY_ACCOUNT(기본 intro-video)
  4. ${XDG_CONFIG_HOME:-~/.config}/openrouter/key
파일은 본인 소유이고 다른 사용자가 읽을 수 없어야(chmod 600) 쓴다. 레포의 .env는 읽지 않는다.

예:
  python3 openrouter_media.py models --modality speech --grep ko-KR
  python3 openrouter_media.py tts --project videos/acme-intro
  python3 openrouter_media.py measure "데이터를 판단으로 바꿉니다"
  python3 openrouter_media.py image "abstract paper texture, warm grey" -o assets/gen/bg.png --aspect 16:9
  python3 openrouter_media.py video "slow macro shot of ink in water" -o assets/gen/ink.mp4 --duration 6
"""
import argparse
import base64
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import wave
from pathlib import Path

API = "https://openrouter.ai/api/v1"
DEFAULTS = {
    "tts_model": "microsoft/mai-voice-2.1",
    "voice": "ko-KR-Haena:MAI-Voice-2.1",
    "stt_model": "elevenlabs/scribe-v2",
    "image_model": "google/gemini-3.1-flash-image",
    "video_model": "google/veo-3.1-fast",
}
TITLE = "intro-video skill"


# ── 키 ───────────────────────────────────────────────────────────────────────
KEYCHAIN_SERVICE = "openrouter"
SETUP_HINT = """OpenRouter 키를 찾지 못했다. 이 스킬 전용 키(사용 한도를 건 키)를 만들어 아래 중 한 곳에 둔다.
  macOS 키체인(권장, 붙여넣기 프롬프트가 뜬다):
    security add-generic-password -U -s openrouter -a intro-video -w
  키 파일(레포 밖, 본인만 읽기):
    mkdir -p ~/.config/openrouter && (umask 077; read -rs k && printf '%s' "$k" > ~/.config/openrouter/key; unset k)
확인: python3 <SKILL_DIR>/scripts/openrouter_media.py key-check
자세한 내용: references/openrouter.md '키'"""
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
    account = os.environ.get("OPENROUTER_KEY_ACCOUNT", "intro-video")
    config = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / "openrouter" / "key"
    candidates = [
        ("환경 변수 OPENROUTER_API_KEY", lambda: os.environ.get("OPENROUTER_API_KEY", "").strip() or None),
        ("OPENROUTER_API_KEY_FILE", lambda: _read_key_file(os.environ["OPENROUTER_API_KEY_FILE"])
            if os.environ.get("OPENROUTER_API_KEY_FILE") else None),
        (f"OS 키 저장소(service={KEYCHAIN_SERVICE}, account={account})", lambda: _read_keystore(account)),
        (f"키 파일 {config}", lambda: _read_key_file(config)),
    ]
    for source, read in candidates:
        value = read()
        if value:
            if not value.startswith("sk-or-"):
                print(f"경고: {source}의 값이 OpenRouter 키 형식(sk-or-…)이 아니다.", file=sys.stderr)
            _KEY = (value, source)
            return _KEY
    sys.exit(SETUP_HINT)


def key():
    return resolve_key()[0]


def redact(text):
    """출력에 키가 섞이면 가린다. 키를 아직 찾지 않았으면 sk-or- 형식만 가린다."""
    if _KEY:
        text = text.replace(_KEY[0], "sk-or-…(가림)")
    return re.sub(r"sk-or-[A-Za-z0-9_-]{8,}", "sk-or-…(가림)", text)


# ── HTTP ─────────────────────────────────────────────────────────────────────
def request(method, url, body=None, auth=True, timeout=180, retries=2):
    """(status, headers, bytes). 429·5xx는 두 번까지 다시 시도한다.

    키는 openrouter.ai로 가는 요청에만 붙인다. 응답에 담긴 다른 도메인의 URL(서명된 다운로드 링크 등)로
    키가 새지 않게 하기 위해서다.
    """
    headers = {"X-OpenRouter-Title": TITLE}
    host = urllib.parse.urlparse(url).hostname or ""
    if auth and (host == "openrouter.ai" or host.endswith(".openrouter.ai")):
        headers["Authorization"] = f"Bearer {key()}"
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
                time.sleep(2 * (attempt + 1))
                continue
            hint = ""
            if b"zdr-violation" in payload:
                hint = ("\n→ 계정의 ZDR(데이터 무보존) 설정이 이 모델의 엔드포인트를 막았다. 설정을 바꾸지 말고 "
                        "사용자에게 알린 뒤 `models --zdr`로 ZDR을 지원하는 모델을 고른다.")
            elif b"IMAGE_RECITATION" in payload:
                hint = "\n→ 이미지 모델이 저작권 오탐으로 막았다. 프롬프트를 바꿔 다시 시도하거나 다른 이미지 모델을 쓴다."
            elif e.code == 401:
                hint = "\n→ 키가 틀렸거나 폐기됐다. key-check로 어떤 키를 쓰고 있는지 확인한다."
            elif e.code == 402:
                hint = "\n→ 크레딧이나 이 키의 사용 한도가 바닥났다. key-check로 남은 한도를 확인한다."
            sys.exit(redact(f"{method} {url} → HTTP {e.code}: {payload[:600].decode(errors='replace')}{hint}"))
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            sys.exit(redact(f"{method} {url} 연결 실패: {e.reason}"))


def post_json(path, body, **kw):
    status, headers, raw = request("POST", f"{API}{path}", body, **kw)
    return json.loads(raw)


# ── 오디오 유틸 ──────────────────────────────────────────────────────────────
def save_audio(raw, content_type, out):
    """TTS 응답 바이트를 WAV로 저장하고 길이(초)를 돌려준다."""
    out.parent.mkdir(parents=True, exist_ok=True)
    ct = (content_type or "").lower()
    if ct.startswith("audio/pcm") or ct.startswith("audio/l16"):
        params = dict(p.strip().split("=", 1) for p in ct.split(";")[1:] if "=" in p)
        rate, channels = int(params.get("rate", 24000)), int(params.get("channels", 1))
        if len(raw) % (2 * channels):
            sys.exit(f"PCM 길이가 16비트 샘플 경계와 맞지 않는다({len(raw)} bytes, {ct})")
        with wave.open(str(out), "wb") as w:
            w.setnchannels(channels)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(raw)
    else:  # mp3·wav 등은 ffmpeg로 WAV(PCM16)로 바꾼다
        if not shutil.which("ffmpeg"):
            sys.exit("ffmpeg가 PATH에 없다")
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
            tmp.write(raw)
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", tmp.name,
                            "-c:a", "pcm_s16le", str(out)], capture_output=True, text=True)
        os.unlink(tmp.name)
        if r.returncode:
            sys.exit(f"오디오 변환 실패({ct}): {r.stderr.strip()}")
    return wav_duration(out)


def wav_duration(path):
    with wave.open(str(path), "rb") as w:
        return round(w.getnframes() / w.getframerate(), 3)


def lufs(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=framelog=quiet",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"I:\s+(-?[\d.]+)\s+LUFS", r.stderr.rsplit("Summary:", 1)[-1])
    return float(m.group(1)) if m else None


def level(path, target, ceiling_db=-1.5):
    """클립을 목표 LUFS로 올리거나 내리고, 피크는 리미터로 ceiling_db 아래에 묶는다.

    TTS 클립은 피크가 0 dBFS 가까이 붙어 있어 단순 게인(normalize-audio)으로는 올릴 수 없다.
    """
    before = lufs(path)
    if before is None:
        return None
    gain = target - before
    limit = 10 ** (ceiling_db / 20)
    tmp = Path(path).with_suffix(".leveling.wav")
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(path), "-af",
                        f"volume={gain:.2f}dB,alimiter=limit={limit:.3f}:level=0", "-c:a", "pcm_s16le", str(tmp)],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"레벨링 실패: {r.stderr.strip()}")
    os.replace(tmp, path)
    return round(before, 1)


def synthesize(text, out, model, voice, instructions=None, speed=None):
    body = {"model": model, "input": text, "response_format": "pcm"}
    if voice:
        body["voice"] = voice
    if instructions:
        body["instructions"] = instructions
    if speed and float(speed) != 1.0:
        body["speed"] = float(speed)
    status, headers, raw = request("POST", f"{API}/audio/speech", body)
    ct = next((v for k, v in headers.items() if k.lower() == "content-type"), "")
    if "json" in ct.lower():
        sys.exit(f"TTS가 오디오 대신 JSON을 돌려줬다: {raw[:400].decode(errors='replace')}")
    return save_audio(raw, ct, out)


# ── 전사와 정렬 ──────────────────────────────────────────────────────────────
def transcribe(path, model, language="ko"):
    fmt = Path(path).suffix.lstrip(".").lower() or "wav"
    body = {
        "model": model,
        "input_audio": {"data": base64.b64encode(Path(path).read_bytes()).decode(), "format": fmt},
        "language": language,
        "response_format": "verbose_json",
        "timestamp_granularities": ["word"],
    }
    res = post_json("/audio/transcriptions", body)
    words = [w for w in res.get("words") or [] if str(w.get("word", "")).strip()]
    return res.get("text", ""), words


def norm(token):
    token = unicodedata.normalize("NFC", token).lower()
    return "".join(ch for ch in token if ch.isalnum())


BRACE = re.compile(r"\{([^{}|]*)\|([^{}]*)\}")
_SP = ""  # 중괄호 안 공백을 잠시 숨기는 문자


def forms(raw):
    """원고 한 줄 → (표기 어절, 읽기 어절).

    `{AI|에이아이}를`처럼 쓰면 화면·자막에는 `AI를`, TTS에는 `에이아이를`이 간다.
    단독 ` / `는 자막 구절 경계 표시라서 둘 다에서 빠진다.
    """
    hidden = BRACE.sub(lambda m: "{%s|%s}" % (m.group(1).replace(" ", _SP), m.group(2).replace(" ", _SP)), raw)
    shown, spoken = [], []
    for tok in hidden.split():
        if tok == "/":
            continue
        shown.append(BRACE.sub(lambda m: m.group(1), tok).replace(_SP, " "))
        spoken.append(BRACE.sub(lambda m: m.group(2), tok).replace(_SP, " "))
    return shown, spoken


def spoken_text(raw):
    return " ".join(forms(raw)[1])


def align(script_text, stt_words, duration):
    """원고 어절에 STT 단어 시각을 붙인다. 자막 글자는 원고 표기를, 시각은 실제 음성을 쓴다.

    돌려주는 값: (words, similarity). similarity가 낮으면 TTS가 원고와 다르게 읽었을 수 있다.
    """
    tokens, spoken = forms(script_text)
    heard = [norm(w["word"]) for w in stt_words]
    wanted = [norm(t) for t in spoken]
    times = [None] * len(tokens)
    sm = difflib.SequenceMatcher(a=wanted, b=heard, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                w = stt_words[j1 + k]
                times[i1 + k] = (float(w["start"]), float(w["end"]))
        elif tag == "replace" and j2 > j1:
            # 같은 구간을 다르게 들은 경우(숫자·영문 표기 차이 등): 그 구간 시간을 글자 수로 나눈다
            start, end = float(stt_words[j1]["start"]), float(stt_words[j2 - 1]["end"])
            spread(times, tokens, i1, i2, start, end)
    # 못 맞춘 어절은 앞뒤 시각 사이에 글자 수 비율로 채운다
    i = 0
    while i < len(tokens):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(tokens) and times[j] is None:
            j += 1
        start = times[i - 1][1] if i > 0 else 0.0
        end = times[j][0] if j < len(tokens) else duration
        spread(times, tokens, i, j, start, max(end, start))
        i = j
    words = [{"id": f"w{n}", "text": t, "start": round(s, 3), "end": round(e, 3)}
             for n, (t, (s, e)) in enumerate(zip(tokens, times))]
    # STT가 읽기 대신 표기("AI")로 받아 적어도 낮게 나오지 않도록 둘 중 높은 쪽을 쓴다
    heard_s = "".join(heard)
    similarity = max(difflib.SequenceMatcher(a="".join(wanted), b=heard_s, autojunk=False).ratio(),
                     difflib.SequenceMatcher(a="".join(norm(t) for t in tokens), b=heard_s, autojunk=False).ratio())
    return words, round(similarity, 3)


def spread(times, tokens, i1, i2, start, end):
    weights = [max(len(norm(t)), 1) for t in tokens[i1:i2]]
    total, cur = sum(weights), start
    for k, wgt in enumerate(weights):
        nxt = cur + (end - start) * wgt / total
        times[i1 + k] = (cur, nxt)
        cur = nxt


# ── SCRIPT.md ───────────────────────────────────────────────────────────────
def parse_script(md):
    """HyperFrames SCRIPT.md: `## … (Frame N)` 줄, `**Delivery:**`, 들여쓴 블록이 읽을 문장."""
    direction = ""
    m = re.search(r"^\*\*Voice direction:\*\*\s*(.+)$", md, re.M)
    if m:
        direction = m.group(1).strip()
    lines, cur = [], None
    for line in md.splitlines():
        h = re.match(r"^#{2,3}\s+.*?\(frame\s+(\d+)\)", line, re.I)
        if h:
            if cur and cur["text"].strip():
                lines.append(cur)
            cur = {"frame": int(h.group(1)), "text": "", "delivery": ""}
            continue
        if not cur:
            continue
        d = re.match(r"^\s*\*\*Delivery:\*\*\s*(.+)$", line)
        if d:
            cur["delivery"] = d.group(1).strip()
            continue
        if re.match(r"^\s*\*\*", line):
            continue
        t = re.match(r"^(?: {4,}|\t)(.+)$", line)
        if t:
            cur["text"] += (" " if cur["text"] else "") + t.group(1).strip()
    if cur and cur["text"].strip():
        lines.append(cur)
    return direction, lines


def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return {}


# ── 서브커맨드 ───────────────────────────────────────────────────────────────
def cmd_key_check(a):
    value, source = resolve_key()
    _, _, raw = request("GET", f"{API}/key")
    d = json.loads(raw).get("data", {})
    info = {
        "source": source,
        "key": f"…{value[-4:]}",
        "label": d.get("label"),
        "limit_usd": d.get("limit"),
        "limit_remaining_usd": d.get("limit_remaining"),
        "limit_reset": d.get("limit_reset"),
        "usage_daily_usd": d.get("usage_daily"),
        "usage_monthly_usd": d.get("usage_monthly"),
        "expires_at": d.get("expires_at"),
        "is_management_key": d.get("is_management_key"),
        "effective_budget": d.get("effective_budget"),
    }
    print(redact(json.dumps(info, ensure_ascii=False, indent=2)))
    warn = []
    if source.startswith("환경 변수"):
        warn.append("키가 환경 변수에 있다. 그 셸에서 뜨는 모든 프로세스가 볼 수 있고, HyperFrames capture 같은 도구가 "
                    "자동으로 써서 화면을 외부로 보낼 수 있다. 키체인이나 키 파일로 옮긴다.")
    if d.get("is_management_key"):
        warn.append("관리(management) 키다. 키를 만들고 지울 수 있는 권한이라 영상 작업에 쓰지 않는다. 추론용 일반 키를 쓴다.")
    if d.get("limit") is None and not d.get("effective_budget"):
        warn.append("이 키에는 사용 한도가 없다. 대시보드에서 이 스킬 전용 키에 한도(예: 월 $5)를 건다.")
    remaining = d.get("limit_remaining")
    if remaining is not None and remaining < 1:
        warn.append(f"남은 한도가 ${remaining}다. 이미지·영상 생성 전에 한도를 확인한다.")
    if not d.get("expires_at"):
        warn.append("만료일이 없는 키다. 정기적으로 교체하거나 만료일을 정해 둔다.")
    for w in warn:
        print(f"경고: {w}", file=sys.stderr)


def cmd_models(a):
    q = urllib.parse.urlencode({"output_modalities": a.modality})
    _, _, raw = request("GET", f"{API}/models?{q}", auth=False)
    models = json.loads(raw)["data"]
    if a.modality == "video":  # 영상 모델은 일반 목록에 없을 수 있어 전용 목록을 쓴다
        _, _, raw = request("GET", f"{API}/videos/models", auth=False)
        body = json.loads(raw)
        models = body.get("data", body) if isinstance(body, dict) else body
    if a.zdr:
        _, _, raw = request("GET", f"{API}/endpoints/zdr", auth=False)
        zdr_ids = {e.get("model_id") for e in json.loads(raw).get("data", [])}
        models = [m for m in models if m["id"] in zdr_ids]
    pat = re.compile(a.grep, re.I) if a.grep else None
    for m in models:
        voices = m.get("supported_voices") or []
        hay = " ".join([m["id"], m.get("description") or "", " ".join(map(str, voices))])
        if pat and not pat.search(hay):
            continue
        price = {k: v for k, v in (m.get("pricing") or m.get("pricing_skus") or {}).items()
                 if v not in ("0", 0, None, "")}
        line = f"{m['id']}  {json.dumps(price)}"
        if m.get("supported_durations"):
            line += f"  durations: {m['supported_durations']}  resolutions: {m.get('supported_resolutions')}"
        if pat and voices:
            hits = [v for v in voices if pat.search(str(v))]
            if hits:
                line += f"  voices: {', '.join(map(str, hits[:8]))}"
        print(line)


def cmd_tts(a):
    root = Path(a.project)
    script = Path(a.script) if a.script else root / "SCRIPT.md"
    direction, lines = parse_script(script.read_text())
    if not lines:
        sys.exit(f"{script}에서 읽을 줄을 찾지 못했다(`## … (Frame N)` 헤더와 4칸 들여쓴 문장이 필요하다)")
    if a.instructions:
        direction = a.instructions
    only = {int(f) for f in a.frames.split(",")} if a.frames else None
    pl = load_json(root / "audio_meta.json")
    kept = {v["frame"]: v for v in pl.get("voices") or []} if only else {}
    voices_pl, report = [], []
    for ln in lines:
        nn = f"{ln['frame']:02d}"
        rel = f"assets/voice/{nn}.wav"
        if only and ln["frame"] not in only and ln["frame"] in kept and (root / rel).exists():
            voices_pl.append(kept[ln["frame"]])  # 고치지 않는 줄은 그대로 둔다
            continue
        instr = " ".join(x for x in (direction, ln["delivery"]) if x) or None
        dur = synthesize(spoken_text(ln["text"]), root / rel, a.model, a.voice, instr, a.speed)
        was = level(root / rel, float(a.lufs)) if a.lufs != "none" else None
        words, sim = [], None
        if a.stt_model != "none":
            _, heard = transcribe(root / rel, a.stt_model, a.language)
            words, sim = align(ln["text"], heard, dur)
        voices_pl.append({"frame": ln["frame"], "path": rel, "duration_s": dur, "words": words})
        report.append({"frame": ln["frame"], "duration_s": dur, "similarity": sim})
        flag = "" if sim is None or sim >= 0.85 else "  ← 원고와 다르게 읽었을 수 있다. 들어 보고 확인"
        lv = f"  {was}→{a.lufs} LUFS" if was is not None else ""
        print(f"frame {nn}: {dur:5.2f}s  {rel}  similarity={sim}{lv}{flag}")
    voices_neutral = [{"id": f"{v['frame']:02d}", "path": v["path"], "duration_s": v["duration_s"],
                       "words": v["words"]} for v in voices_pl]

    meta = {"tts_provider": "openrouter", "tts_model": a.model, "voice": a.voice}
    pl.setdefault("bgm", None)
    pl.setdefault("bgm_pending", False)
    pl.setdefault("sfx", [])
    pl.update(meta, voices=voices_pl)
    (root / "audio_meta.json").write_text(json.dumps(pl, ensure_ascii=False, indent=2))
    # fetch-sfx 등 HyperFrames 오디오 패스가 다시 만들 때 음성을 지우지 않도록 엔진 쪽 사이드카에도 쓴다
    ne = load_json(root / "audio_engine_meta.json")
    ne.update(meta, voices=voices_neutral)
    (root / "audio_engine_meta.json").write_text(json.dumps(ne, ensure_ascii=False, indent=2))
    total = round(sum(v["duration_s"] for v in voices_pl), 2)
    print(json.dumps({"ok": True, "generated": len(report), "lines": len(voices_pl), "total_voice_s": total,
                      "audio_meta": str(root / "audio_meta.json")}, ensure_ascii=False))


def cmd_measure(a):
    with tempfile.TemporaryDirectory() as d:
        out = Path(a.output) if a.output else Path(d) / "m.wav"
        dur = synthesize(spoken_text(a.text), out, a.model, a.voice, a.instructions, a.speed)
    print(json.dumps({"text": a.text, "chars": len(a.text), "seconds": dur, "model": a.model,
                      "voice": a.voice, "out": a.output}, ensure_ascii=False))


def cmd_stt(a):
    text, heard = transcribe(a.audio, a.model, a.language)
    if a.script_text:
        words, sim = align(a.script_text, heard, wav_duration(a.audio) if a.audio.endswith(".wav") else
                           (heard[-1]["end"] if heard else 0))
    else:
        words = [{"id": f"w{i}", "text": w["word"], "start": w["start"], "end": w["end"]} for i, w in enumerate(heard)]
        sim = None
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output).write_text(json.dumps(words, ensure_ascii=False, indent=2))
    print(json.dumps({"text": text, "words": len(words), "similarity": sim, "out": a.output}, ensure_ascii=False))


def cmd_image(a):
    body = {"model": a.model, "prompt": a.prompt, "n": 1}
    if a.size:
        body["size"] = a.size
    else:
        body["aspect_ratio"] = a.aspect
        body["resolution"] = a.resolution
    if a.seed is not None:
        body["seed"] = a.seed
    res = post_json("/images", body, timeout=300)
    item = (res.get("data") or [None])[0]
    if not item or not item.get("b64_json"):
        sys.exit(f"이미지가 오지 않았다: {json.dumps(res)[:400]}")
    out = Path(a.output)
    ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/svg+xml": ".svg"}.get(
        item.get("media_type", ""), out.suffix or ".png")
    if out.suffix.lower() != ext:
        out = out.with_suffix(ext)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(item["b64_json"]))
    print(json.dumps({"out": str(out), "model": a.model, "media_type": item.get("media_type")}, ensure_ascii=False))


def cmd_video(a):
    body = {"model": a.model, "prompt": a.prompt, "duration": a.duration,
            "resolution": a.resolution, "aspect_ratio": a.aspect, "generate_audio": a.audio}
    if a.first_frame:
        p = Path(a.first_frame)
        mime = "image/jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else "image/png"
        url = f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"
        body["frame_images"] = [{"type": "image_url", "image_url": {"url": url}, "frame_type": "first_frame"}]
    job = post_json("/videos", body)
    poll = job.get("polling_url") or f"{API}/videos/{job['id']}"
    print(f"submitted {job.get('id')} ({job.get('status')})", file=sys.stderr)
    deadline = time.time() + a.timeout
    while True:
        _, _, raw = request("GET", poll)
        st = json.loads(raw)
        if st.get("status") == "completed":
            break
        if st.get("status") in ("failed", "cancelled", "expired"):
            sys.exit(f"영상 생성 실패: {st.get('error') or st.get('status')}")
        if time.time() > deadline:
            sys.exit(f"{a.timeout}s 안에 끝나지 않았다. 나중에 확인: {poll}")
        time.sleep(10)
    url = (st.get("unsigned_urls") or [None])[0] or f"{API}/videos/{job['id']}/content"
    _, _, data = request("GET", url, timeout=600)
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print(json.dumps({"out": str(out), "model": a.model, "bytes": len(data), "usage": st.get("usage")},
                     ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("key-check", help="키 출처·한도·사용액·만료 확인(키 값은 출력하지 않음)")
    p.set_defaults(fn=cmd_key_check)

    p = sub.add_parser("models", help="현재 모델 목록(키 불필요)")
    p.add_argument("--modality", default="speech", choices=["speech", "transcription", "image", "video", "audio", "all"])
    p.add_argument("--grep", help="id·설명·음성 이름에서 찾을 정규식(예: ko-KR)")
    p.add_argument("--zdr", action="store_true", help="ZDR(데이터 무보존) 엔드포인트가 있는 모델만")
    p.set_defaults(fn=cmd_models)

    def voice_args(p):
        p.add_argument("--model", default=DEFAULTS["tts_model"])
        p.add_argument("--voice", default=DEFAULTS["voice"])
        p.add_argument("--instructions", help="톤 지시(Gemini·Fish Audio만 반영, 다른 모델은 무시)")
        p.add_argument("--speed", help="속도 배수(지원하는 모델만)")

    p = sub.add_parser("tts", help="SCRIPT.md → 줄별 음성 + audio_meta.json")
    p.add_argument("--project", default=".", help="HyperFrames 프로젝트 루트")
    p.add_argument("--script", help="기본: <project>/SCRIPT.md")
    voice_args(p)
    p.add_argument("--stt-model", default=DEFAULTS["stt_model"], help="단어 타이밍용 STT 모델, none이면 생략")
    p.add_argument("--language", default="ko")
    p.add_argument("--frames", help="이 프레임 줄만 다시 만든다(예: 3,5). 나머지는 기존 파일 유지")
    p.add_argument("--lufs", default="-14", help="줄마다 맞출 라우드니스(기본 -14, 피크 -1.5 dBFS 리미터). none이면 생략")
    p.set_defaults(fn=cmd_tts)

    p = sub.add_parser("measure", help="문장을 읽는 데 걸리는 초")
    p.add_argument("text")
    voice_args(p)
    p.add_argument("-o", "--output", help="들어 볼 수 있게 WAV를 남길 경로(음성 후보 비교용)")
    p.set_defaults(fn=cmd_measure)

    p = sub.add_parser("stt", help="오디오 → 단어 타이밍")
    p.add_argument("audio")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--model", default=DEFAULTS["stt_model"])
    p.add_argument("--language", default="ko")
    p.add_argument("--script-text", help="원고 문장. 주면 화면용 글자를 원고에 맞춘다")
    p.set_defaults(fn=cmd_stt)

    p = sub.add_parser("image", help="프롬프트 → 이미지")
    p.add_argument("prompt")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--model", default=DEFAULTS["image_model"])
    p.add_argument("--aspect", default="16:9")
    p.add_argument("--resolution", default="2K")
    p.add_argument("--size", help="예: 1920x1080 (주면 aspect·resolution 대신 쓴다)")
    p.add_argument("--seed", type=int)
    p.set_defaults(fn=cmd_image)

    p = sub.add_parser("video", help="프롬프트 → b-roll MP4")
    p.add_argument("prompt")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--model", default=DEFAULTS["video_model"])
    p.add_argument("--duration", type=int, default=6)
    p.add_argument("--resolution", default="1080p")
    p.add_argument("--aspect", default="16:9")
    p.add_argument("--first-frame", help="첫 프레임으로 쓸 이미지(image-to-video)")
    p.add_argument("--audio", action="store_true", help="모델이 소리도 만들게 한다(기본: 끔)")
    p.add_argument("--timeout", type=int, default=900)
    p.set_defaults(fn=cmd_video)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
