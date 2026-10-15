# OpenRouter로 내레이션·자막·생성 소스 만들기

## 왜 이 경로를 쓰나

HyperFrames 워크플로의 기본 음성은 HeyGen(로그인 필요), Gemini(구글 키 직접 사용), Kokoro(로컬) 중 하나다. Kokoro에는 한국어가 없다(영어·스페인어·프랑스어·힌디어·이탈리아어·포르투갈어·일본어·중국어). OpenRouter 키 하나면 한국어 TTS, 단어 타이밍용 STT, 이미지, 짧은 b-roll 영상을 모두 부를 수 있다.

OpenRouter TTS는 오디오 바이트만 돌려주고 단어 타이밍은 주지 않는다. 그래서 `openrouter_media.py tts`가 다음 순서로 처리한다.

1. 줄마다 음성을 만든다.
2. STT로 그 음성을 다시 받아 적는다.
3. 원고 어절에 그 시각을 붙인다.

자막에는 원고 글자가 쓰이고, 타이밍은 실제 음성에서 나온다.

## 모델

2026-10-15 공개 모델 목록으로 확인했다. 모델 id는 자주 바뀐다(문서 예시의 OpenAI TTS는 이미 목록에서 빠졌다). 쓰기 전에 `models`로 다시 확인한다.

```bash
python3 <SKILL_DIR>/scripts/openrouter_media.py models --modality speech --grep ko-KR
python3 <SKILL_DIR>/scripts/openrouter_media.py models --modality transcription
```

| 용도 | 기본 | 대안 | 메모 |
|---|---|---|---|
| 한국어 내레이션 | `microsoft/mai-voice-2.1`, 음성 `ko-KR-Haena`·`ko-KR-Junho`·`ko-KR-Harper`·`ko-KR-Grant`(뒤에 `:MAI-Voice-2.1`) | `google/gemini-3.8-flash-tts`(음성 `Kore`, `Charon` 등 30종) | MAI는 한국어 전용 음성이 있고 `instructions`를 무시한다. 톤은 음성 선택으로 정한다. Gemini는 `instructions`로 톤을 지시할 수 있다 |
| 단어 타이밍 | `elevenlabs/scribe-v2` | `openai/whisper-large-v3`, 로컬 `npx hyperframes transcribe <wav> --model small --language ko` | `.en` 모델은 한국어를 영어로 번역해 버리므로 쓰지 않는다 |
| 배경·텍스처 이미지 | `google/gemini-3.1-flash-image` | `bytedance-seed/seedream-5-0-pro`, `openai/gpt-image-2` | `/api/v1/images`. 한글 글자는 이미지에 넣지 않는다. Gemini는 평범한 프롬프트도 저작권 오탐(`IMAGE_RECITATION`)으로 막을 때가 있다. 그러면 프롬프트를 바꾸거나 Seedream을 쓴다 |
| b-roll 영상 | `google/veo-3.1-fast`(4·6·8초) | `google/veo-3.1-lite`(720p 무음 초당 약 $0.03), `kwaivgi/kling-v3.0-std`, `alibaba/wan-3.0`(2–30초) | 비동기 작업이다. 소리는 끄고 받는다. **ZDR 계정에서는 쓸 수 없다**(아래 참고) |
| 효과음 | `bytedance-seed/seed-audio-1-0`(`/audio/speech`에 음성 없이 설명문) | HyperFrames `media-use` 번들 효과음 | 스크립트에는 없다. 필요하면 `measure`처럼 직접 호출한다 |
| 음악 | 검증 안 됨(`google/lyria-3-*`는 요청 형식 문서가 없다) | 사용자가 준 파일, 무음 | 확인 전에는 쓰지 않는다 |

### 실측 메모

2026-10-15에 이 스킬을 만들며 같은 문장 하나(59자)를 음성 세 개로 만들어 쟀다. 표본이 작으니 계획용 추정치로만 쓰고, 실제 길이는 `tts` 결과에 맞춘다.

- **읽기 속도:** 9.4–10.4초가 걸려 공백·문장부호를 포함해 초당 약 6자였다. 30초 내레이션 원고는 150–170자 안팎에서 시작해 `tts` 결과로 조정한다.
- **발음:** scribe-v2로 다시 받아 적었을 때 세 음성 모두 원고와 일치했다(유사도 1.0). "2026년"도 문제없이 읽었다.
- **라우드니스:** 음성마다 다르다. MAI Haena는 −19.5 LUFS, Junho는 −19.8 LUFS, Gemini Kore는 −14.7 LUFS였다. `tts`가 줄마다 맞춘다. 맞추지 않은 내레이션 영상은 렌더 결과가 −17.1 LUFS였고, 맞춘 뒤에는 −13.5 LUFS였다.
- **이미지 크기:** 요청한 비율은 지키지만 픽셀 크기는 모델마다 다르다. Gemini 1K 16:9는 1376×768, Seedream 2K는 2048×1152였다. 컴포지션에서는 `object-fit: cover`로 채우고 정확한 크기를 가정하지 않는다.

### ZDR(데이터 무보존) 계정

계정의 개인정보 설정에서 ZDR을 강제하면 ZDR 엔드포인트가 없는 모델은 HTTP 404(`zdr-violation-by-account`)로 거절된다. 설정은 사용자의 정책이므로 바꾸지 않는다. 사용자에게 알리고 ZDR을 지원하는 모델을 고른다.

```bash
python3 <SKILL_DIR>/scripts/openrouter_media.py models --modality speech --zdr --grep ko-KR
```

2026-10-15 기준으로 기본 음성(MAI)·STT(scribe-v2)·이미지(Gemini, Seedream) 모델은 모두 ZDR을 지원한다. 영상 생성 모델은 하나도 지원하지 않는다. ZDR 계정에서는 b-roll을 생성하지 말고, 사용자가 준 영상이나 코드로 그린 장면을 쓴다.

### 가격

가격은 2026-10-15 목록 기준이다. MAI 음성은 글자당 약 $0.000022로 30초 원고(약 150자)에 1센트도 안 든다. scribe는 초당 약 $0.00003이다. 이미지는 장당 수 센트, Veo fast는 1080p 무음 초당 약 $0.10(6초에 약 $0.6)이다. 이미지나 영상을 생성하기 전에는 개수와 대략의 비용을 사용자에게 알린다.

## 내레이션 절차

워크플로(`product-launch-video`, `faceless-explainer`)의 Step 3.1 Audio를 아래로 **대체한다**. 워크플로의 `audio.mjs` 생성 명령(`--script … --out ./audio_meta.json`)은 실행하지 않는다. 실행하면 음성을 HeyGen이나 Kokoro로 다시 만들어 덮어쓴다.

1. **원고를 HyperFrames `SCRIPT.md` 형식으로 쓴다.** `## Line N — <이름> (Frame N)` 헤더, `**Delivery:**` 한 줄, 4칸 들여쓴 읽을 문장 순서다. 머리에 `**Voice direction:**`을 두면 Gemini 계열에 톤 지시로 전달된다.
   - 라틴 문자 브랜드명·약어는 `{표기|읽기}`로 쓴다. 예: `{AI|에이아이}를`, `{DOU INC.|도우 인크}`. TTS는 읽기를, 자막은 표기를 쓴다. 그냥 "에이아이"로 쓰면 자막에도 "에이아이"가 나간다.
   - 자막 구절 경계는 ` / `(앞뒤 공백)로 표시한다. TTS에는 전달되지 않고 `ko_captions.py`가 쓴다. 관형절("그 바탕이 되는 / 인프라")처럼 자동으로는 못 나누는 곳에 특히 쓴다.
   - 숫자는 그대로 둬도 되지만, 첫 생성 뒤 읽는 방식을 확인한다.
   - 분량은 초당 약 6자로 잡고 시작한다(실측 메모). 사실이 적으면 문장을 늘리지 말고 속도(`--speed 0.9`)와 끝 홀드로 길이를 맞춘다.
2. **음성을 고른다.** 사용자가 음성을 정하지 않았으면 후보 2–3개로 같은 첫 문장을 만들어 들려준다. 아무도 들을 수 없는 상황이면 요청한 성별의 MAI 한국어 음성을 고른다(억양 위험이 가장 낮다).

   | 음성 | 성별 | 메모 |
   |---|---|---|
   | `ko-KR-Haena:MAI-Voice-2.1` | 여성 | 스모크 테스트 선택 음성 |
   | `ko-KR-Harper:MAI-Voice-2.1` | 여성 | |
   | `ko-KR-Junho:MAI-Voice-2.1` | 남성 | |
   | `ko-KR-Grant:MAI-Voice-2.1` | 남성 | |
   | Gemini `Kore` / `Charon` | 여성 / 남성 | 다국어 음성이다. `instructions`로 톤을 지시할 수 있다 |

   ```bash
   python3 <SKILL_DIR>/scripts/openrouter_media.py measure "<첫 문장>" --voice ko-KR-Haena:MAI-Voice-2.1 -o /tmp/voice-haena.wav
   python3 <SKILL_DIR>/scripts/openrouter_media.py measure "<첫 문장>" --voice ko-KR-Junho:MAI-Voice-2.1 -o /tmp/voice-junho.wav
   python3 <SKILL_DIR>/scripts/openrouter_media.py measure "<첫 문장>" --model google/gemini-3.8-flash-tts --voice Kore --instructions "차분하고 확신 있는 내레이터" -o /tmp/voice-kore.wav
   ```
3. **전체 줄을 만든다.** 결과는 `assets/voice/NN.wav`이고, `audio_meta.json`과 `audio_engine_meta.json`의 `voices[]`가 채워진다. 이미 있는 `bgm`·`sfx` 항목은 그대로 둔다. 각 줄은 −14 LUFS로 맞추고 피크를 −1.5 dBFS 리미터로 묶는다(`--lufs`, 끄려면 `--lufs none`). TTS 원본은 음성마다 −15에서 −20 LUFS 사이로 들쭉날쭉하고, 피크가 0 dBFS에 붙어 있어 나중에 게인만으로는 올릴 수 없다.
   ```bash
   python3 <SKILL_DIR>/scripts/openrouter_media.py tts --project . --model <모델> --voice <음성>
   ```
4. **경고가 뜬 줄을 고친다.** `similarity`가 0.85보다 낮게 표시된 줄은 TTS가 원고와 다르게 읽었을 수 있다. 들어 보고 원고를 고친 뒤 그 줄만 다시 만든다(`--frames 3` 또는 `--frames 3,5`).
5. **프레임 길이를 실제 음성 길이에 맞춘다.**
   ```bash
   node <HF>/<workflow>/scripts/audio.mjs sync-durations --audio-meta ./audio_meta.json --storyboard ./STORYBOARD.md
   ```
6. **음악을 넣는다.** 사용자가 준 파일이면 `assets/`에 두고 `audio_meta.json`에 `"bgm": { "path": "assets/…", "source": "host" }`를 쓰고, 스토리보드에는 `music: none`을 둔다. 음악이 없으면 `music: none`만 둔다.
7. **효과음을 넣는다.** 스토리보드의 `sfx:` 큐가 있으면 워크플로의 `fetch-sfx`를 그대로 쓴다. `audio_engine_meta.json`에 음성이 있으므로 이 패스는 음성을 지우지 않는다. 직접 만든 효과음은 `sfx` 항목에 `"source": "host"`로 넣는다.
8. **자막을 만든다.** 워크플로의 `captions.mjs`가 `voices[].words`를 읽는다. 바로 뒤에 `python3 <SKILL_DIR>/scripts/ko_captions.py --project .`로 구절 단위로 다시 묶는다. 그다음 단계는 워크플로를 따른다.

## 그래픽형 화면 문구의 최소 노출 시간

한글 읽기 속도는 공개된 측정치가 없다. 그래서 같은 문구를 TTS로 읽힌 길이를 하한으로 쓴다.

```bash
python3 <SKILL_DIR>/scripts/openrouter_media.py measure "<화면 문구>"
```

출력의 `seconds`와 2초 중 긴 쪽을 그 문구의 최소 노출 시간으로 둔다. 키가 없으면 화면 문구를 짧게 줄이고, 2초 이상 노출하는 규칙만 지킨다.

## 생성 이미지·영상

- **쓰는 곳:** 배경 텍스처, 추상 b-roll, 실제 사람·장소처럼 코드로 그릴 수 없는 픽셀.
- **쓰지 않는 곳:** 로고(파일을 쓴다), 제품 UI(실제 화면이나 캡처를 쓴다), 한글 글자(HTML 레이어에 둔다), 실재하지 않는 고객·수치를 암시하는 화면.
- 결과물은 `assets/gen/`에 둔다. 파일마다 `BRIEF.md`의 `## Assets`에 `경로 — 모델, 프롬프트 요약, 생성일`을 한 줄로 남긴다. 출처를 추적할 수 있어야 다음 수정에서 같은 결과를 다시 만들 수 있다.
- 생성 영상은 HyperFrames 컴포지션 안에 `<video>` 클립으로 넣고, 타이틀은 그 위 HTML 레이어에 얹는다.

```bash
python3 <SKILL_DIR>/scripts/openrouter_media.py image "<프롬프트>" -o assets/gen/bg-01.png --aspect 16:9 --resolution 2K
python3 <SKILL_DIR>/scripts/openrouter_media.py video "<프롬프트>" -o assets/gen/broll-01.mp4 --duration 6 --aspect 16:9
```

## 키

- `OPENROUTER_API_KEY` 환경 변수에서만 읽는다. 값을 출력하거나 `BRIEF.md`·`.env`·로그에 쓰지 않는다.
- 키가 없으면 사용자에게 셸 프로필에 `export OPENROUTER_API_KEY=…`를 추가하고 새 셸을 열어 달라고 요청한다. 그동안 그래픽형 작업은 키 없이 진행할 수 있다.
