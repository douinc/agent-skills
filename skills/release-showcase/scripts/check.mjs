/**
 * 릴리스 쇼케이스 화면 검수 — build.py가 만든 HTML을 데스크톱·모바일 폭으로 열어 사람이 눈으로 볼 것을
 * 기계로 먼저 거른다. 가로 넘침, 빈 이미지, 재생되지 않는 영상, 챕터가 영상 길이를 넘는 것, 눌러도
 * 반응하지 않는 비교·단계·탭·챕터, 콘솔 오류를 오류로 본다. 하이라이트마다 화면을 남겨 검수자가
 * 그림을 직접 열어 보게 한다.
 *
 * 사용: `node check.mjs --html <문서.html> --out <화면 폴더>`
 * (보통은 `showcase.py build --verify`나 `showcase.py verify`가 부른다)
 * playwright는 SHOWCASE_PLAYWRIGHT_DIR(그 폴더의 node_modules)에서 찾는다.
 */
import { mkdir, rm } from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { createRequire } from 'node:module'

const VIEWPORTS = [
  { name: 'desktop', width: 1280, height: 900 },
  { name: 'mobile', width: 400, height: 860 },
]

const require = createRequire(path.join(process.env.SHOWCASE_PLAYWRIGHT_DIR ?? process.cwd(), 'package.json'))
const { chromium } = require('playwright')
const CHROMIUM_PATH = process.env.SHOWCASE_CHROMIUM

function arg(name) {
  const i = process.argv.indexOf(name)
  return i === -1 ? undefined : process.argv[i + 1]
}

/** 끝까지 천천히 내려 지연 동작(영상 자동 재생·목차 표시)을 모두 깨운다 */
async function scrollThrough(page) {
  const height = await page.evaluate(() => document.documentElement.scrollHeight)
  for (let y = 0; y < height; y += 600) {
    await page.evaluate((top) => window.scrollTo(0, top), y)
    await page.waitForTimeout(60)
  }
  await page.evaluate(() => window.scrollTo(0, 0))
}

async function layoutProblems(page) {
  return page.evaluate(() => {
    const out = []
    const vw = document.documentElement.clientWidth
    if (document.documentElement.scrollWidth > vw + 1) {
      // 넘친 요소 중 가장 바깥 몇 개만 — 자식까지 다 적으면 원인이 묻힌다
      const wide = [...document.querySelectorAll('body *')]
        .filter((el) => el.getBoundingClientRect().right > vw + 1)
        // 가로 스크롤 상자(목차·단계 점) 안의 요소는 넘쳐도 페이지를 밀지 않는다
        .filter((el) => {
          for (let p = el.parentElement; p; p = p.parentElement) {
            if (/(auto|scroll|hidden)/.test(getComputedStyle(p).overflowX)) return false
          }
          return true
        })
        .filter(
          (el) => !(el.parentElement && el.parentElement.getBoundingClientRect().right > vw + 1)
        )
        .slice(0, 4)
        .map((el) => [el.tagName.toLowerCase(), ...el.classList].join('.'))
      out.push(`가로 넘침 ${document.documentElement.scrollWidth}px > ${vw}px (${wide.join(', ')})`)
    }
    for (const img of document.querySelectorAll('img[data-zoom], .hero img')) {
      if (!img.complete || img.naturalWidth === 0)
        out.push(`빈 이미지: ${img.alt || img.src.slice(0, 40)}`)
    }
    for (const section of document.querySelectorAll('section.hl')) {
      const media = section.querySelector('.hl-media')
      const box = media?.getBoundingClientRect()
      if (!box || box.height < 40) out.push(`#${section.id}: 시각 자료가 보이지 않아요`)
    }
    return out
  })
}

async function videoProblems(page) {
  const out = []
  const count = await page.locator('[data-video] video').count()
  for (let i = 0; i < count; i++) {
    const video = page.locator('[data-video] video').nth(i)
    const state = await video.evaluate(
      (v) =>
        new Promise((resolve) => {
          const done = () =>
            resolve({ duration: v.duration, error: v.error ? `code ${v.error.code}` : null })
          if (v.readyState >= 1 || v.error) done()
          else {
            v.addEventListener('loadedmetadata', done, { once: true })
            v.addEventListener('error', done, { once: true })
            v.load()
            setTimeout(done, 8000)
          }
        })
    )
    if (state.error !== null || !Number.isFinite(state.duration) || state.duration <= 0) {
      out.push(`영상 ${i + 1}: 재생할 수 없어요 (${state.error ?? `길이 ${state.duration}`})`)
      continue
    }
    const chapters = await page
      .locator('[data-video]')
      .nth(i)
      .locator('.chapters button')
      .evaluateAll((bs) => bs.map((b) => Number(b.dataset.t)))
    const over = chapters.filter((t) => t > state.duration)
    if (over.length > 0)
      out.push(
        `영상 ${i + 1}: 챕터 ${over.join(', ')}초가 영상 길이(${state.duration.toFixed(1)}초)를 넘어요`
      )
  }
  return out
}

/** 컴포넌트를 하나씩 눌러 반응하는지 본다 — 템플릿 스크립트가 깨지면 화면은 멀쩡해 보여도 여기서 걸린다 */
async function interactionProblems(page) {
  const out = []
  const compares = page.locator('[data-compare]')
  for (let i = 0; i < (await compares.count()); i++) {
    const el = compares.nth(i)
    // 작은 카드처럼 토글을 숨긴 비교는 나란히만 보여 주므로 누를 것이 없다
    if (!(await el.locator('button[data-side="after"]').isVisible())) continue
    await el.locator('button[data-side="after"]').click()
    if (!(await el.locator('.compare-stage.only-after').count()))
      out.push(`비교 ${i + 1}: 이후 보기가 안 돼요`)
    await el.locator('button[data-side="split"]').click()
  }
  const steppers = page.locator('[data-stepper]')
  for (let i = 0; i < (await steppers.count()); i++) {
    const el = steppers.nth(i)
    await el.locator('.next').click()
    const on = await el
      .locator('.slide')
      .evaluateAll((s) => s.findIndex((x) => x.classList.contains('on')))
    if (on !== 1) out.push(`단계 ${i + 1}: 다음 단계로 넘어가지 않아요`)
    await el.locator('.prev').click()
  }
  const tabs = page.locator('[data-tabs]')
  for (let i = 0; i < (await tabs.count()); i++) {
    const el = tabs.nth(i)
    const heads = el.locator('.tab-heads button')
    if ((await heads.count()) < 2) continue
    await heads.nth(1).click()
    const on = await el
      .locator('.pane')
      .evaluateAll((p) => p.findIndex((x) => x.classList.contains('on')))
    if (on !== 1) out.push(`탭 ${i + 1}: 두 번째 탭이 열리지 않아요`)
    await heads.nth(0).click()
  }
  const videos = page.locator('[data-video]')
  for (let i = 0; i < (await videos.count()); i++) {
    const el = videos.nth(i)
    const last = el.locator('.chapters button').last()
    if (!(await last.count())) continue
    const t = Number(await last.getAttribute('data-t'))
    await last.click()
    await page.waitForTimeout(300)
    const now = await el.locator('video').evaluate((v) => v.currentTime)
    if (Math.abs(now - t) > 1.5)
      out.push(`영상 ${i + 1}: 챕터를 눌러도 ${t}초로 가지 않아요 (지금 ${now.toFixed(1)}초)`)
    await el.locator('video').evaluate((v) => v.pause())
  }
  const zoom = page.locator('img[data-zoom]').first()
  if (await zoom.count()) {
    await zoom.click()
    if (!(await page.locator('.lightbox.on').count()))
      out.push('그림을 눌러도 크게 보기가 열리지 않아요')
    await page.keyboard.press('Escape')
  }
  return out
}

async function main() {
  const html = arg('--html')
  const outDir = arg('--out')
  if (html === undefined || outDir === undefined) {
    throw new Error(
      '사용: node check.mjs --html <문서.html> --out <화면 폴더>'
    )
  }
  await rm(outDir, { recursive: true, force: true })
  await mkdir(outDir, { recursive: true })
  const browser = await chromium.launch({ executablePath: CHROMIUM_PATH })
  const problems = []
  const shots = []
  try {
    for (const vp of VIEWPORTS) {
      const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } })
      page.setDefaultTimeout(5000)
      const add = (what) => void problems.push({ viewport: vp.name, what })
      page.on('pageerror', (e) => add(`스크립트 오류: ${e.message}`))
      page.on('console', (m) => {
        // 글꼴 CDN이 막힌 곳에서도 문서는 기본 글꼴로 읽히므로 네트워크 실패는 오류로 치지 않는다
        if (m.type() === 'error' && !/Failed to load resource|net::ERR_/.test(m.text()))
          add(`콘솔 오류: ${m.text()}`)
      })
      await page.goto(pathToFileURL(path.resolve(html)).href, { waitUntil: 'load' })
      await scrollThrough(page)
      for (const p of await layoutProblems(page)) add(p)
      for (const p of await videoProblems(page)) add(p)
      if (vp.name === 'desktop') for (const p of await interactionProblems(page)) add(p)

      // 검수자가 열어 볼 화면 — 첫 화면, 하이라이트마다 한 장, 변경 목록
      const prefix = path.join(outDir, vp.name)
      // 고정 목차가 절 그림을 덮지 않게 숨기고, 누른 컴포넌트의 포커스 테두리를 지운다
      await page.addStyleTag({ content: '.toc{visibility:hidden} html{scroll-behavior:auto!important}' })
      await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur())
      await page.evaluate(() => window.scrollTo(0, 0))
      await page.locator('header.hero').screenshot({ path: `${prefix}-00-hero.png` })
      shots.push(`${prefix}-00-hero.png`)
      const ids = await page.locator('section.hl').evaluateAll((s) => s.map((x) => x.id))
      for (const [i, id] of ids.entries()) {
        const file = `${prefix}-${String(i + 1).padStart(2, '0')}-${id}.png`
        await page.locator(`section.hl#${id}`).screenshot({ path: file })
        shots.push(file)
      }
      for (const [name, selector] of [
        ['more', '#more'],
        ['changes', '#changes'],
      ]) {
        if (await page.locator(selector).count()) {
          const file = `${prefix}-99-${name}.png`
          await page.locator(selector).screenshot({ path: file })
          shots.push(file)
        }
      }
      await page.close()
    }
  } finally {
    await browser.close()
  }

  console.log(`화면 ${shots.length}장: ${outDir}`)
  if (problems.length === 0) {
    console.log(
      '✓ 검수 통과 — 넘침·빈 이미지·영상·상호작용·콘솔 오류 없음. 남긴 화면을 열어 눈으로 확인해요'
    )
    return
  }
  console.error(`✗ 검수 문제 ${problems.length}건`)
  for (const p of problems) console.error(`  [${p.viewport}] ${p.what}`)
  process.exitCode = 1
}

try {
  await main()
  process.exit(process.exitCode ?? 0)
} catch (error) {
  console.error(error)
  process.exit(1)
}
