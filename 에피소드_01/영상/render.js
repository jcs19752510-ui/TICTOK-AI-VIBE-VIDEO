// 3단계(합성) 보조: player.html을 Chromium으로 열어 프레임(JPEG)을 병렬로 캡처한다.
// 사용: NODE_PATH=/opt/node-tools/node_modules node render.js <sample|full|thumb> <출력폴더> [워커수]
const path = require("path");
const fs = require("fs");
const { chromium } = require("playwright");

const mode = process.argv[2], out = process.argv[3], workers = parseInt(process.argv[4] || "4", 10);
const EP = JSON.parse(fs.readFileSync(path.join(__dirname, "scenes.json"), "utf8"));
const url = "file://" + path.join(__dirname, "player.html");
fs.mkdirSync(out, { recursive: true });

async function openPage(browser, query) {
  const ctx = await browser.newContext({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(url + (query || ""));
  await page.evaluate(() => window.fontsReady);
  return page;
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined });
  const t0 = Date.now();
  if (mode === "thumb") {
    const page = await openPage(browser, "?thumb=1");
    await page.screenshot({ path: path.join(out, "thumbnail.png"), type: "png" });
  } else {
    let jobs = [];
    if (mode === "sample") {
      EP.scenes.forEach((s) => { [0.3, s.duration - 0.2].forEach((o, k) => jobs.push({ name: `s${String(s.id).padStart(2, "0")}_${k}`, t: s.start + Math.max(0.05, o) })); });
    } else {
      for (let f = 0; f < EP.frames; f++) jobs.push({ name: `f${String(f).padStart(5, "0")}`, t: f / EP.fps });
    }
    let next = 0, done = 0;
    await Promise.all(Array.from({ length: workers }, async () => {
      const page = await openPage(browser);
      while (true) {
        const j = jobs[next++];
        if (!j) break;
        await page.evaluate((t) => window.renderAt(t), j.t);
        await page.screenshot({ path: path.join(out, j.name + ".jpg"), type: "jpeg", quality: 92 });
        if (++done % 200 === 0) console.log(`progress ${done}/${jobs.length}`);
      }
    }));
    console.log(`captured ${done} frames`);
  }
  console.log(`elapsed ${((Date.now() - t0) / 1000).toFixed(1)}s`);
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
