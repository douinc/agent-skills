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

async function runStep(page, step) {
  if ('wait' in step) return page.waitForTimeout(step.wait)
  if ('press' in step) return page.keyboard.press(step.press)
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

async function recordClip(baseUrl, settings, spec, outDir) {
  const viewport = settings.viewport ?? { width: 1280, height: 800 }
  const scale = settings.scale ?? 1
  const tmpDir = path.join(outDir, `.tmp-${spec.id}`)
  await rm(tmpDir, { recursive: true, force: true })
  const browser = await chromium.launch({
    executablePath: process.env.SHOWCASE_CHROMIUM,
    args: settings.browserArgs ?? [],
  })
  const chapters = []
  try {
    const context = await browser.newContext({
      viewport,
      deviceScaleFactor: scale,
      recordVideo: { dir: tmpDir, size: { width: viewport.width * scale, height: viewport.height * scale } },
    })
    await context.addInitScript(CURSOR_SCRIPT)
    const page = await context.newPage()
    const started = Date.now()
    const url = new URL(spec.path ?? '', baseUrl)
    for (const [k, v] of Object.entries(spec.query ?? {})) url.searchParams.set(k, v)
    await page.goto(url.href, { waitUntil: 'load' })
    await page.evaluate(() => document.fonts.ready)
    const ready = spec.ready ?? settings.ready
    if (ready) await page.locator(ready).first().waitFor({ state: 'visible', timeout: 30_000 })
    // 녹화는 컨텍스트가 열린 순간부터라 첫 로딩의 빈 화면이 앞에 남는다 — 그 길이를 잘라낼 수 있게 적는다
    const lead = (Date.now() - started) / 1000
    if (spec.introCaption) chapters.push({ t: 0, caption: spec.introCaption })
    await page.waitForTimeout(spec.intro ?? 1200)
    for (const [index, step] of spec.steps.entries()) {
      if (step.caption) chapters.push({ t: (Date.now() - started) / 1000 - lead, caption: step.caption })
      try {
        await runStep(page, step)
      } catch (error) {
        // 단계 이름이 화면과 어긋난 자리를 바로 보게 실패 직전 화면을 남긴다
        const shot = path.join(outDir, `${spec.id}.fail.png`)
        await page.screenshot({ path: shot })
        throw new Error(`${spec.id} 단계 ${index + 1} 실패 (${JSON.stringify(step)}) — 화면: ${shot}`, { cause: error })
      }
      await page.waitForTimeout(step.pause ?? 900)
    }
    const video = page.video()
    await context.close()
    if (video === null) throw new Error('녹화 파일이 없어요')
    await rename(await video.path(), path.join(outDir, `${spec.id}.raw.webm`))
    await writeFile(
      path.join(outDir, `${spec.id}.chapters.json`),
      JSON.stringify({ lead: Math.max(0, lead - 0.1), chapters }, null, 2)
    )
    console.log(`✓ ${spec.id} (챕터 ${chapters.length}개, 앞 ${lead.toFixed(1)}초 자름)`)
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
  for (const spec of specs) await recordClip(baseUrl, settings, spec, path.resolve(outDir))
}

try {
  await main()
  process.exit(0)
} catch (error) {
  console.error(error)
  process.exit(1)
}
