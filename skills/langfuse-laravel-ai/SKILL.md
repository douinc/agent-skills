---
name: langfuse-laravel-ai
description: "Use when adding Langfuse tracing/observability to a Laravel app that uses the laravel/ai SDK (Laravel\\Ai\\ namespace, Agent classes, ->prompt()/->stream(), tools, conversations). Activate when the user wants to trace LLM/agent calls, token usage, or tool invocations to Langfuse in a Laravel project, pairs Langfuse with laravel/ai, or asks why traces aren't showing up. Laravel/PHP-specific: laravel/ai has no OpenTelemetry support and there is no first-party PHP Langfuse SDK, so the integration path is non-obvious."
metadata:
  author: initred
  email: initred@dou.so
  version: "2.0.0"
---

# Langfuse × laravel/ai

`laravel/ai` SDK(`Laravel\Ai\`)를 쓰는 Laravel 앱의 LLM/에이전트 호출을 Langfuse로 트레이싱한다.

## 핵심 전제 (먼저 알아야 할 것)

- laravel/ai는 **OpenTelemetry를 지원하지 않고**, 공식 PHP Langfuse SDK도 없다. 직접 OTLP 클라이언트를 짜기 전에 **`initred/laravel-langfuse`를 먼저 채택한다.** laravel/ai를 **코드 변경 없이 자동계측**하고, trace를 Langfuse OTLP 엔드포인트(`/api/public/otel/v1/traces`)로 배칭 전송한다.
- 요구사항: **PHP 8.5+, Laravel 13**, laravel/ai **1.4+ 권장**(패키지 문서 기준. Composer가 강제하지는 않는다). Langfuse는 Cloud(v3·v4) 또는 self-hosted **3.22.0+**.
- 패키지 비교(채택 전 근거):

| 패키지 | laravel/ai 자동계측 | 전송 | 주의 |
| --- | --- | --- | --- |
| `initred/laravel-langfuse` ✅ | O | OTLP (trace), 인제스션 API (score) | laravel/ai 1.x usage(캐시 토큰 포함)에 맞춰져 있음 |
| `tracefast/laravel-ai-observability` | O | OTLP 경유 | `laravel/ai ^0.7`을 **강제** → 낮은 버전과 충돌 위험 |
| `dropsolid/` · `dij-digital/` · `janzaba/` | X (수동 trace API만) | Langfuse | 결국 이벤트 후킹은 직접 해야 함 |

## 설치 & 설정

1. `composer require initred/laravel-langfuse`
   - 프로젝트의 `post-update-cmd` 스크립트(`composer bump`, `bun update` 등)가 다른 패키지까지 올릴 수 있다. 설치 후 `composer.json`·`package.json`·lock 파일 diff를 확인하고 의도치 않은 변경은 되돌린다.
2. `php artisan vendor:publish --tag=langfuse-config`
3. `.env` (env 키가 표준이라 기존 `LANGFUSE_*` 값을 그대로 재사용):
   ```env
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_BASE_URL=https://cloud.langfuse.com   # self-hosted면 그 URL
   LANGFUSE_LARAVEL_AI_ENABLED=true               # ← 자동계측 ON (필수)
   LANGFUSE_QUEUE=langfuse                         # 큐 worker로 비동기 전송 (worker가 이 큐를 처리해야 함)
   LANGFUSE_TRACING_ENVIRONMENT=production         # Langfuse의 environment 필터
   ```
4. 등록 확인: `php artisan config:clear && php artisan event:list | grep LaravelAiSubscriber`
   → laravel/ai 6개 이벤트에 붙어야 정상.

## 자동계측이 잡는 것

`Initred\Langfuse\LaravelAi\LaravelAiSubscriber`가 후킹한다:

| laravel/ai 이벤트 | Langfuse 관측치 |
| --- | --- |
| `PromptingAgent` / `StreamingAgent` | trace 생성(열린 trace가 없을 때만) + 시작 시각 |
| `AgentPrompted` / `AgentStreamed` | generation(이름=모델명, model, input, output, token usage) |
| `InvokingTool` / `ToolInvoked` | tool span (arguments, result) |

- baseline(model·토큰·input/output·observation 타입·span 계층)은 **코드 변경 없이** 채워진다.
- **userId·sessionId도 자동이다.** `RemembersConversations`를 쓰는 에이전트의 대화 id가 sessionId가 되고, `forUser()`/`continue()`/`continueLastConversation()`에 넘긴 참여자가 userId가 된다(큐에서 돌아도 동일). 참여자가 없으면 인증 사용자로 대체된다. 끄려면 `LANGFUSE_SESSION_TRACING=false` / `LANGFUSE_USER_TRACING=false`.
- usage: `input`은 캐시되지 않은 입력 토큰만 담고, 캐시 읽기/쓰기 토큰은 `input_cached_tokens`/`input_cache_creation_tokens`로 분리된다(중복 과금 방지). reasoning 토큰은 `output`에 포함된다.

**자동계측이 못 잡는 것:** 실패한 실행(`AgentFailed`), 음성 인식(`GeneratingTranscription` 등), 시스템 지시문·첨부 이미지(input은 텍스트 프롬프트만 기록). 이게 필요하면 laravel/ai 이벤트를 직접 구독해 `currentTrace()->generation(...)`으로 기록한다. 이때 자동계측은 끄고(`LANGFUSE_LARAVEL_AI_ENABLED=false`) 한 곳에서만 기록해야 generation이 중복되지 않는다.

## 핵심 패턴 — trace 컨텍스트 보강

자동계측만으로는 **도메인 메타데이터·태그·업무 단위 이름이 없다.** 또 대화형 에이전트가 아니면 sessionId도 없다. subscriber의 `resolveTrace()`는 **이미 설정된 `currentTrace()`가 있으면 그걸 재사용**한다. 따라서 에이전트 호출 직전에 trace를 미리 열어두면 generation·tool span이 그 아래로 nest된다.

```php
use Initred\Langfuse\Dto\TraceBody;
use Initred\Langfuse\LangfuseFacade as Langfuse;

// 에이전트를 prompt()/stream() 하기 전에:
$trace = Langfuse::trace(new TraceBody(
    name: 'questionnaire-builder',
    userId: (string) $user->id,
    sessionId: $conversationId,           // 멀티턴 대화 그룹핑
    metadata: ['questionnaire_id' => $q->id, 'team_id' => $team->id],
    tags: ['questionnaire-builder'],
));
Langfuse::setCurrentTrace($trace);

$response = (new MyAgent(...))
    ->continue($conversationId, as: $user)
    ->prompt($prompt);

$trace->end(output: $response->text);   // 직접 연 trace는 직접 끝낸다
```

**순서가 중요하다.** `setCurrentTrace`를 **에이전트 호출보다 먼저** 해야 한다. 빠뜨리면 `resolveTrace()`가 `laravel-ai-<AgentClass>` 이름의 trace를 새로 만들고 호출이 끝나면 닫는다. 그러면 호출마다 trace가 따로 생기고 도메인 메타데이터도 붙지 않는다. 요청당 한 번, 여러 에이전트를 쓰면 첫 호출 전에 한 번 열어두면 그 아래로 전부 nest된다. HTTP 요청 단위로 묶기만 하면 되면 라우트에 `Initred\Langfuse\Http\Middleware\LangfuseMiddleware`를 거는 것으로 충분하다.

### trace 수명주기 (v4: 끝난 관측치만 전송된다)

- 자동계측이 **직접 만든** trace는 호출이 끝나면 자동으로 닫힌다. `setCurrentTrace`로 **넘겨받은** trace는 절대 닫지 않는다. 연 쪽이 닫아야 한다.
- HTTP 요청은 앱 종료(terminating) 훅이 열린 관측치를 모두 닫고 flush한다. **큐 worker·CLI 명령은 잡 사이에 종료되지 않으므로** 작업 단위가 끝날 때 `Langfuse::shutdown()`을 직접 호출한다. 안 하면 trace가 다음 잡까지 열려 있거나 전송되지 않는다.

```php
use Initred\Langfuse\Objects\NullLangfuseTrace;

Langfuse::setCurrentTrace(Langfuse::trace(new TraceBody(name: 'nightly-report', ...)));

try {
    $agent->prompt($prompt);
} finally {
    Langfuse::shutdown();                                // 열린 관측치 종료 + flush
    Langfuse::setCurrentTrace(new NullLangfuseTrace);   // 다음 작업이 재사용하지 않게
}
```

## 테스트 (Pest)

```php
use Initred\Langfuse\LangfuseFacade as Langfuse;
use Initred\Langfuse\LaravelAi\LaravelAiSubscriber;
use Initred\Langfuse\Tracing\CompletedObservation;

$langfuse = Langfuse::fake();
app()->forgetInstance(LaravelAiSubscriber::class);   // ← 필수 (아래 설명)
MyAgent::fake(['응답'])->preventStrayPrompts();      // 실제 provider 호출 차단

// ... 엔드포인트/액션 실행 ...

$langfuse->assertTraceEnded('questionnaire-builder')
    ->assertGenerationEnded()
    ->assertObservationHas('questionnaire-builder', fn (CompletedObservation $trace): bool =>
        $trace->context->body()->sessionId === $conversationId
        && $trace->context->body()->userId === (string) $user->id);
```

- **`forgetInstance`가 필요한 이유:** subscriber는 앱 부팅 때 `Event::subscribe()`로 만들어지면서 실제 Langfuse 클라이언트를 주입받는다. 그 뒤에 `Langfuse::fake()`를 호출해도 subscriber는 여전히 실제 클라이언트에 기록하므로, fake에는 generation이 하나도 남지 않는다. fake 직후 인스턴스를 버리면 다음 이벤트에서 fake를 주입받아 다시 만들어진다.
- 테스트 환경(`phpunit.xml`)에도 `LANGFUSE_LARAVEL_AI_ENABLED=true`가 있어야 subscriber가 등록된다(부팅 때 읽는다). 전송은 fake가 막으므로 `LANGFUSE_ENABLED=false`와 함께 써도 된다.
- `MyAgent::fake()`(laravel/ai의 fake gateway)도 `PromptingAgent`/`AgentPrompted` 이벤트를 발생시킨다. 따라서 자동계측 generation까지 검증할 수 있다. 자동계측 generation의 이름은 모델명이니 `assertGenerationEnded()`는 이름 없이 쓰거나 모델명을 넘긴다.
- `assertTraceEnded`/`assertObservationHas`는 **끝난** 관측치만 본다. 생성 여부만 보려면 `assertTraceCreated`. 직접 실행한 액션이 trace를 닫지 않으면 테스트에서 `Langfuse::shutdown()`을 호출한 뒤 검증한다.
- 기록된 내용은 `$langfuse->traces()`/`generations()`/`observations()`로 직접 꺼내 볼 수 있다.

## 함정 (자주 막히는 지점)

- **실제 trace가 대시보드에 뜨려면** 실제 provider 호출 + `LANGFUSE_QUEUE`의 큐를 처리하는 worker가 떠 있어야 한다(`queue:work --queue=langfuse,default` 등). 로컬은 `composer run dev`가 worker를 포함하는 경우가 많다. trace가 안 보이면 먼저 worker가 그 큐 이름을 처리하는지 확인.
- `LANGFUSE_QUEUE`를 비워두면(null) 동기 전송 — 큐 worker 없이도 가게 되지만 요청 종료 시 HTTP 호출이 붙어 약간 지연된다. worker 인프라가 없는 환경이면 이 모드가 더 안전하다(설정한 큐를 worker가 처리하지 않으면 trace가 영영 전송되지 않으니 주의).
- 큐 잡에서 trace가 안 뜨거나 다음 잡의 trace에 섞이면 `Langfuse::shutdown()` 누락을 의심한다(위 수명주기 참고).
- 인증/연결 핑(읽기 전용):
  ```bash
  AUTH=$(printf '%s:%s' "$LANGFUSE_PUBLIC_KEY" "$LANGFUSE_SECRET_KEY" | base64)
  curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Basic $AUTH" \
    "$LANGFUSE_BASE_URL/api/public/traces?limit=1"   # 200 이면 OK
  ```
- self-hosted가 3.22.0보다 낮으면 OTLP 엔드포인트가 없어 trace 전송이 실패한다. 버전부터 확인한다.
- OTLP 요청은 4MB 단위로 나눠 보내지만, 관측치 하나가 그보다 크면 경고 로그(`Langfuse observation exceeds the OTLP request limit`)만 남기고 그대로 보낸다. base64 이미지 등을 통째로 넣으면 Langfuse의 요청 한도(5MB)에 걸려 버려질 수 있으니, 큰 첨부는 요약 문자열로 대체한다.
- `LANGFUSE_ENABLED=false`면 no-op으로 graceful 비활성 — 코드 변경 없이 끌 수 있다(로컬/CI).
- PII가 프롬프트·메타데이터에 들어가는 도메인이면 trace `input`/`metadata`에서 마스킹·제외한다.
- Langfuse 인제스션은 비동기라 trace가 대시보드에 몇 초 늦게 뜰 수 있다.
