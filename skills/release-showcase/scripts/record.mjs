/**
 * 클릭 흐름 녹화 — 띄워 둔 앱(URL)을 Playwright로 열어 clips.json의 단계대로 누르고 치며 WebM으로 남긴다.
 * 헤드리스 화면에는 포인터가 없으므로 가짜 커서를 그려 누르는 자리를 보여 주고, 단계별 시작 시각을
 * `<id>.chapters.json`으로 함께 남겨 문서가 영상 옆 챕터 목록을 그린다.
 *
 * 보통은 `showcase.py build --record`가 태그 worktree에서 앱을 띄운 뒤 부른다.
 *   node record.mjs --spec clips.json --out <dir> --base-url <url> [--settings <json>] [--only <id>]
 * playwright는 SHOWCASE_PLAYWRIGHT_DIR(그 폴더의 node_modules)에서 찾는다.
 */
import { spawnSync } from 'node:child_process'
import { mkdir, readFile, rename, rm, writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import path from 'node:path'

const require = createRequire(path.join(process.env.SHOWCASE_PLAYWRIGHT_DIR ?? process.cwd(), 'package.json'))
const { chromium } = require('playwright')

function arg(name) {
  const i = process.argv.indexOf(name)
  return i === -1 ? undefined : process.argv[i + 1]
}

const CURSOR_SCRIPT = `
  window.addEventListener('DOMContentLoaded', () => {
    const c = document.createElement('div')
    c.id = '__clip-cursor'
    c.style.cssText = 'position:fixed;left:50%;top:70%;width:18px;height:18px;margin:-9px 0 0 -9px;' +
      'border-radius:50%;background:rgba(22,87,185,.35);border:2px solid rgba(22,87,185,.9);' +
      'z-index:2147483647;pointer-events:none;transition:left .45s ease,top .45s ease,transform .12s;'
    document.documentElement.appendChild(c)
  })
`

async function moveCursor(page, locator) {
  const box = await locator.boundingBox()
  if (box === null) return
  await page.evaluate(
    ({ x, y }) => {
      const c = document.getElementById('__clip-cursor')
      if (c) {
        c.style.left = `${x}px`
        c.style.top = `${y}px`
      }
    },
    { x: box.x + box.width / 2, y: box.y + box.height / 2 }
  )
  await page.waitForTimeout(500)
}

async function pressCursor(page) {
  await page.evaluate(() => {
    const c = document.getElementById('__clip-cursor')
    if (!c) return
    c.style.transform = 'scale(.7)'
    setTimeout(() => (c.style.transform = 'scale(1)'), 140)
  })
}

/** 단계 대상 찾기 — 텍스트 정확 일치, role+접근 이름, 또는 CSS 선택자 */
function locate(page, step) {
  if ('text' in step) return page.getByText(step.text, { exact: step.exact ?? true }).first()
  if ('selector' in step) return page.locator(step.selector).first()
  const scope =
    step.dialog === undefined
      ? page
      : step.dialog === true
        ? page.getByRole('dialog').last()
        : page.getByRole('dialog', { name: step.dialog, exact: true }).last()
  return scope
    .getByRole(step.role, step.name === undefined ? {} : { name: step.name, exact: step.exact ?? true })
    .first()
}

async function runStep(page, step, { outDir, specDir }) {
  if ('wait' in step) return page.waitForTimeout(step.wait)
  if ('press' in step) return page.keyboard.press(step.press)
  // 문서에 실을 정지 화면 — `.media/<이름>.png`, story에서 `local`로 쓴다
  if ('screenshot' in step) {
    // 정지 화면에는 가짜 커서를 싣지 않는다
    const cursor = page.locator('#__clip-cursor')
    await cursor.evaluate((c) => (c.style.visibility = 'hidden')).catch(() => {})
    await page.screenshot({ path: path.join(outDir, `${step.screenshot}.png`) })
    return cursor.evaluate((c) => (c.style.visibility = 'visible')).catch(() => {})
  }
  if ('upload' in step) {
    // 파일 선택 창 대신 입력에 바로 넣는다 — 경로는 clips.json 기준
    const input = page.locator(step.selector ?? 'input[type="file"]').first()
    return input.setInputFiles(step.upload.map((f) => path.resolve(specDir, f)))
  }
  const locator = locate(page, step)
  await locator.waitFor({ state: 'visible', timeout: 10_000 })
  if (step.action === 'scroll') return locator.scrollIntoViewIfNeeded()
  await moveCursor(page, locator)
  await pressCursor(page)
  if (step.action === 'hover') return locator.hover()
  await locator.click()
  if (step.action === 'fill') return locator.fill(step.value ?? '')
  if (step.action === 'type') {
    // 입력창의 Enter는 보내기인 경우가 많아 줄바꿈은 Shift+Enter로 친다
    const lines = (step.value ?? '').split('\n')
    for (const [i, line] of lines.entries()) {
      if (i > 0) await locator.press('Shift+Enter')
      await locator.pressSequentially(line, { delay: 55 })
    }
  }
}

/**
 * 화면을 장치 픽셀 그대로 프레임으로 받는다(CDP screencast). Playwright의 recordVideo는
 * deviceScaleFactor를 무시하고 CSS 픽셀 크기로 찍어, 크기를 키우면 제품 화면이 영상 왼쪽 위
 * 4분의 1에만 그려진다. 프레임은 화면이 바뀔 때만 오므로 시각(timestamp)으로 길이를 맞춰 잇는다.
 */
async function startScreencast(context, page, size, frameDir) {
  const cdp = await context.newCDPSession(page)
  const frames = []
  const writes = []
  cdp.on('Page.screencastFrame', ({ data, metadata, sessionId }) => {
    const file = path.join(frameDir, `f${String(frames.length).padStart(5, '0')}.jpg`)
    frames.push({ file, ts: metadata.timestamp })
    writes.push(writeFile(file, Buffer.from(data, 'base64')))
    cdp.send('Page.screencastFrameAck', { sessionId }).catch(() => {})
  })
  await cdp.send('Page.startScreencast', {
    format: 'jpeg',
    quality: 92,
    maxWidth: size.width,
    maxHeight: size.height,
    everyNthFrame: 1,
  })
  return {
    frames,
    async stop() {
      await cdp.send('Page.stopScreencast').catch(() => {})
      await Promise.all(writes)
    },
  }
}

function encodeFrames(frames, endTs, frameDir, out) {
  if (frames.length === 0) throw new Error('녹화 프레임이 없어요')
  const lines = []
  for (const [i, f] of frames.entries()) {
    const next = i + 1 < frames.length ? frames[i + 1].ts : endTs
    lines.push(`file '${f.file}'`, `duration ${Math.max(0.001, next - f.ts).toFixed(3)}`)
  }
  lines.push(`file '${frames[frames.length - 1].file}'`) // concat은 마지막 길이를 쓰려면 한 번 더 적어야 한다
  const list = path.join(frameDir, 'frames.txt')
  return writeFile(list, lines.join('\n')).then(() => {
    const r = spawnSync(
      'ffmpeg',
      [
        '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', list,
        '-vf', 'fps=30,scale=trunc(iw/2)*2:trunc(ih/2)*2', '-c:v', 'libvpx-vp9', '-crf', '32', '-b:v', '0',
        '-row-mt', '1', '-pix_fmt', 'yuv420p', '-an', out,
      ],
      { stdio: 'inherit' }
    )
    if (r.status !== 0) throw new Error(`ffmpeg 인코딩 실패 (exit ${r.status})`)
  })
}

function hasFfmpeg() {
  return spawnSync('ffmpeg', ['-version'], { stdio: 'ignore' }).status === 0
}

/** clip이 고른 목 응답·데이터를 페이지 스크립트보다 먼저 심는다 */
async function initScripts(context, spec, specDir) {
  if (spec.initData) {
    const data = JSON.parse(await readFile(path.resolve(specDir, spec.initData), 'utf8'))
    await context.addInitScript((d) => {
      window.__SHOWCASE_DATA__ = d
    }, data)
  }
  if (spec.initScript) await context.addInitScript({ path: path.resolve(specDir, spec.initScript) })
}

async function recordClip(baseUrl, settings, spec, outDir, specDir) {
  const viewport = settings.viewport ?? { width: 1280, height: 800 }
  const scale = settings.scale ?? 1
  const tmpDir = path.join(outDir, `.tmp-${spec.id}`)
  await rm(tmpDir, { recursive: true, force: true })
  await mkdir(tmpDir, { recursive: true })
  const screencast = hasFfmpeg()
  const browser = await chromium.launch({
    executablePath: process.env.SHOWCASE_CHROMIUM,
    // screencast 프레임은 컨텍스트의 deviceScaleFactor가 아니라 이 플래그를 따른다(없으면 CSS 픽셀)
    args: [...(settings.browserArgs ?? []), ...(screencast && scale !== 1 ? [`--force-device-scale-factor=${scale}`] : [])],
  })
  const chapters = []
  try {
    const context = await browser.newContext({
      viewport,
      deviceScaleFactor: scale,
      // ffmpeg가 없을 때만 Playwright 녹화로 — 그때는 CSS 픽셀 크기(흐릿함)로 찍는다
      ...(screencast ? {} : { recordVideo: { dir: tmpDir, size: viewport } }),
    })
    await context.addInitScript(CURSOR_SCRIPT)
    await initScripts(context, spec, specDir)
    const page = await context.newPage()
    const started = Date.now()
    const url = new URL(spec.path ?? '', baseUrl)
    for (const [k, v] of Object.entries(spec.query ?? {})) url.searchParams.set(k, v)
    await page.goto(url.href, { waitUntil: 'load' })
    await page.evaluate(() => document.fonts.ready)
    const ready = spec.ready ?? settings.ready
    if (ready) await page.locator(ready).first().waitFor({ state: 'visible', timeout: 30_000 })
    // 첫 로딩의 빈 화면은 싣지 않는다 — screencast는 지금부터 받고, Playwright 녹화는 그 길이를 잘라낸다
    const cast = screencast
      ? await startScreencast(context, page, { width: viewport.width * scale, height: viewport.height * scale }, tmpDir)
      : null
    const t0 = Date.now()
    const lead = cast ? 0 : (t0 - started) / 1000
    const now = () => (Date.now() - t0) / 1000
    if (spec.introCaption) chapters.push({ t: 0, caption: spec.introCaption })
    await page.waitForTimeout(spec.intro ?? 1200)
    for (const [index, step] of spec.steps.entries()) {
      if (step.caption) chapters.push({ t: now(), caption: step.caption })
      try {
        await runStep(page, step, { outDir, specDir })
      } catch (error) {
        // 단계 이름이 화면과 어긋난 자리를 바로 보게 실패 직전 화면을 남긴다
        const shot = path.join(outDir, `${spec.id}.fail.png`)
        await page.screenshot({ path: shot })
        throw new Error(`${spec.id} 단계 ${index + 1} 실패 (${JSON.stringify(step)}) — 화면: ${shot}`, { cause: error })
      }
      await page.waitForTimeout(step.pause ?? 900)
    }
    const raw = path.join(outDir, `${spec.id}.raw.webm`)
    if (cast) {
      await cast.stop()
      // 프레임 시각은 브라우저 시계라 첫 프레임을 0초로 맞추고, 챕터는 녹화 시작 시각 기준이다
      const endTs = cast.frames.length ? cast.frames[0].ts + now() : 0
      await encodeFrames(cast.frames, endTs, tmpDir, raw)
      await context.close()
    } else {
      const video = page.video()
      await context.close()
      if (video === null) throw new Error('녹화 파일이 없어요')
      await rename(await video.path(), raw)
    }
    await writeFile(
      path.join(outDir, `${spec.id}.chapters.json`),
      JSON.stringify({ lead: Math.max(0, lead - 0.1), encoded: Boolean(cast), chapters }, null, 2)
    )
    console.log(`✓ ${spec.id} (챕터 ${chapters.length}개, ${cast ? `${viewport.width * scale}×${viewport.height * scale}` : 'CSS 픽셀'})`)
  } finally {
    await browser.close()
    await rm(tmpDir, { recursive: true, force: true })
  }
}

async function main() {
  const specPath = arg('--spec')
  const outDir = arg('--out')
  const baseUrl = arg('--base-url')
  if (!specPath || !outDir || !baseUrl) {
    throw new Error('사용: node record.mjs --spec <clips.json> --out <dir> --base-url <url> [--settings <json>]')
  }
  const settings = JSON.parse(arg('--settings') ?? '{}')
  const only = arg('--only')
  const specs = JSON.parse(await readFile(specPath, 'utf8')).filter((s) => only === undefined || s.id === only)
  await mkdir(outDir, { recursive: true })

  // 영상이 여럿이면 하나씩 별도 프로세스로 찍는다 — 한 프로세스에서 녹화를 이어 하면 두 번째 페이지가
  // 입력·스크린샷에서 멈추는 일이 있었다(브라우저를 새로 띄워도 재현). 프로세스를 나누면 서로 영향이 없다.
  if (only === undefined && specs.length > 1) {
    for (const spec of specs) {
      const child = spawnSync(process.execPath, [...process.argv.slice(1), '--only', spec.id], { stdio: 'inherit' })
      if (child.status !== 0) throw new Error(`${spec.id} 녹화 실패 (exit ${child.status})`)
    }
    return
  }
  for (const spec of specs) await recordClip(baseUrl, settings, spec, path.resolve(outDir), path.dirname(path.resolve(specPath)))
}

try {
  await main()
  process.exit(0)
} catch (error) {
  console.error(error)
  process.exit(1)
}
