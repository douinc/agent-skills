---
name: langfuse-laravel-ai
description: "Use when adding Langfuse tracing/observability to a Laravel app that uses the laravel/ai SDK (Laravel\\Ai\\ namespace, Agent classes, ->prompt()/->stream(), tools, conversations). Activate when the user wants to trace LLM/agent calls, token usage, or tool invocations to Langfuse in a Laravel project, pairs Langfuse with laravel/ai, or asks why traces aren't showing up. Laravel/PHP-specific: laravel/ai has no OpenTelemetry support and there is no first-party PHP Langfuse SDK, so the integration path is non-obvious."
metadata:
  author: initred
  email: initred@dou.so
  version: "1.0.0"
---

# Langfuse × laravel/ai

`laravel/ai` SDK(`Laravel\Ai\`)를 쓰는 Laravel 앱의 LLM/에이전트 호출을 Langfuse로 트레이싱한다.

## 핵심 전제 (먼저 알아야 할 것)

- laravel/ai는 **OpenTelemetry를 지원하지 않고**, 공식 PHP Langfuse SDK도 없다. 직접 OTLP/인제스션 클라이언트를 짜기 전에 **`axyr/laravel-langfuse`를 먼저 채택한다** — laravel/ai를 **zero-code 자동계측**하고 Langfuse 인제스션 API로 큐 배칭 전송한다.
- 패키지 비교(채택 전 근거):

| 패키지 | laravel/ai 자동계측 | 전송 | 주의 |
| --- | --- | --- | --- |
| `axyr/laravel-langfuse` ✅ | O | Langfuse 네이티브 인제스션 | require가 `illuminate`만 → laravel/ai 버전 **비강제**(충돌 없음) |
| `tracefast/laravel-ai-observability` | O | OTLP 경유 | `laravel/ai ^0.7`을 **강제** → 낮은 버전과 충돌 위험 |
| `dropsolid/` · `dij-digital/` · `janzaba/` | X (수동 trace API만) | Langfuse | 결국 이벤트 후킹은 직접 해야 함 |

## 설치 & 설정

1. `composer require axyr/laravel-langfuse`
   - post-install 훅이 `package.json`을 무관하게 건드리면 `git checkout package.json`으로 원복.
2. `php artisan vendor:publish --tag=langfuse-config`
3. `.env` (env 키가 표준이라 기존 `LANGFUSE_*` 값을 그대로 재사용):
   ```env
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_BASE_URL=https://cloud.langfuse.com   # self-hosted면 그 URL
   LANGFUSE_LARAVEL_AI_ENABLED=true               # ← 자동계측 ON (필수)
   LANGFUSE_QUEUE=default                          # 큐 worker로 비동기 전송
   ```
4. 등록 확인: `php artisan config:clear && php artisan event:list | grep LaravelAiSubscriber`
   → laravel/ai 6개 이벤트에 붙어야 정상.

## 자동계측이 잡는 것

`Axyr\Langfuse\LaravelAi\LaravelAiSubscriber`가 후킹한다:

| laravel/ai 이벤트 | Langfuse 관측치 |
| --- | --- |
| `PromptingAgent` / `StreamingAgent` | trace 생성 + 시작 시각 |
| `AgentPrompted` / `AgentStreamed` | generation (model, input, output, token usage) |
| `InvokingTool` / `ToolInvoked` | tool span (arguments, result) |

baseline(model·토큰·input/output·observation 타입·span 계층)은 **코드 변경 없이** 채워진다.

## 핵심 패턴 — trace 컨텍스트 보강

자동계측만으로는 **session_id·user_id·도메인 메타데이터가 없다**. subscriber의 `resolveTrace()`는 **이미 설정된 `currentTrace()`가 있으면 그걸 재사용**한다. 따라서 에이전트 호출 직전에 trace를 미리 열어두면 generation·tool span이 그 아래로 nest된다.

```php
use Axyr\Langfuse\Dto\TraceBody;
use Axyr\Langfuse\LangfuseFacade as Langfuse;

// 에이전트를 prompt()/stream() 하기 전에:
Langfuse::setCurrentTrace(Langfuse::trace(new TraceBody(
    name: 'questionnaire-builder',
    userId: (string) $user->id,
    sessionId: $conversationId,           // 멀티턴 대화 그룹핑
    metadata: ['questionnaire_id' => $q->id, 'team_id' => $team->id],
    tags: ['questionnaire-builder'],
)));

$response = (new MyAgent(...))
    ->continue($conversationId, as: $user)
    ->stream($prompt);
```

같은 요청 내 LLM 호출이 여러 개여도 한 trace로 묶인다. 큐 잡 등 비-HTTP 컨텍스트에서도 동일하게 호출 전에 `setCurrentTrace`를 호출하면 된다.

**순서가 중요하다.** `setCurrentTrace`를 **에이전트 호출보다 먼저** 해야 한다. 빠뜨리면 `resolveTrace()`가 `laravel-ai-<AgentClass>` 이름의 기본 trace를 자동 생성하는데, 여기엔 session_id·user_id·도메인 메타데이터가 없다(=보강 실패). 요청당 한 번, 여러 에이전트를 쓰면 첫 호출 전에 한 번 열어두면 그 아래로 전부 nest된다.

## 테스트 (Pest)

```php
$langfuse = Langfuse::fake();                     // RecordingEventBatcher
MyAgent::fake(['응답'])->preventStrayPrompts();    // 실제 provider 호출 차단

// ... 엔드포인트/액션 실행 ...

$langfuse->assertTraceCreated('questionnaire-builder');
$body = collect($langfuse->events())
    ->first(fn ($e) => $e->type->value === 'trace-create')
    ->body->toArray();
expect($body['sessionId'])->toBe($conversationId)
    ->and($body['userId'])->toBe((string) $user->id);
```

**중요:** laravel/ai의 `FakeTextGateway`는 이벤트를 dispatch하지 않는다 → 테스트에서 **자동계측 generation/tool span은 검증 불가**. 검증 가능한 것은 `setCurrentTrace`로 직접 연 trace다(`LangfuseTrace` 생성자가 즉시 enqueue하므로 `assertTraceCreated`가 통과). 자동계측 동작 자체는 패키지 책임이므로 우리 보강 코드만 테스트한다.

## 함정 (자주 막히는 지점)

- **실제 trace가 대시보드에 뜨려면** 실제 provider 호출 + 큐 worker가 떠 있어야 한다(`LANGFUSE_QUEUE` 사용 시 `queue:work`/`queue:listen`). 로컬은 `composer run dev`가 worker를 포함하는 경우가 많다. trace가 안 보이면 먼저 worker부터 확인.
- `LANGFUSE_QUEUE`를 비워두면(null) 동기 전송 — 큐 worker 없이도 가게 되지만 요청 종료 시 HTTP 호출이 붙어 약간 지연된다. worker 인프라가 없는 환경이면 이 모드가 더 안전하다(설정한 큐를 worker가 처리하지 않으면 trace가 영영 전송되지 않으니 주의).
- 인증/연결 핑(읽기 전용):
  ```bash
  AUTH=$(printf '%s:%s' "$LANGFUSE_PUBLIC_KEY" "$LANGFUSE_SECRET_KEY" | base64)
  curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Basic $AUTH" \
    "$LANGFUSE_BASE_URL/api/public/traces?limit=1"   # 200 이면 OK
  ```
- usage 매핑은 prompt/completion 토큰만 — cache/reasoning 토큰은 누락되어 비용이 약간 부정확할 수 있다.
- `LANGFUSE_ENABLED=false`면 no-op(NullTrace)로 graceful 비활성 — 코드 변경 없이 끌 수 있다(로컬/CI).
- PII가 프롬프트·메타데이터에 들어가는 도메인이면 trace `input`/`metadata`에서 마스킹·제외한다.
- Langfuse v3(self-hosted)는 비동기 인제스션이라 trace가 몇 초 지연될 수 있다.
