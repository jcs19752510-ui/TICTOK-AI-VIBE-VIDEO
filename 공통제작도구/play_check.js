// 재생 확인: Chromium의 <video> 요소로 mp4를 실제로 끝까지 재생(배속)하고 결과를 JSON으로 출력한다.
// 사용: NODE_PATH=/opt/node-tools/node_modules CHROME_PATH=... node play_check.js <mp4 경로> [배속=4]
// 확인하는 것: 재생 가능 여부, 끝까지 재생(ended), 재생한 길이, 실제로 그려진 영상 프레임 수, 디코딩된 오디오 바이트.
// 한계: 헤드리스 환경이라 소리를 귀로 들을 수는 없다. 오디오는 디코딩된 바이트 수와 ffmpeg 음량 측정으로 대신 확인한다.
const path = require("path");
const { chromium } = require("playwright");
const file = path.resolve(process.argv[2]);
const rate = parseFloat(process.argv[3] || "4");
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined, args: ["--autoplay-policy=no-user-gesture-required"] });
  const page = await browser.newPage({ viewport: { width: 540, height: 960 } });
  await page.goto("file://" + file);
  const res = await page.evaluate(async (rate) => {
    const v = document.querySelector("video");
    const out = { canPlayH264: v.canPlayType('video/mp4; codecs="avc1.640028"'), canPlayAAC: v.canPlayType('audio/mp4; codecs="mp4a.40.2"') };
    await new Promise((r) => (v.readyState >= 1 ? r() : v.addEventListener("loadedmetadata", r, { once: true })));
    out.duration = v.duration; out.videoWidth = v.videoWidth; out.videoHeight = v.videoHeight;
    let frames = 0; const cb = () => { frames++; v.requestVideoFrameCallback(cb); }; v.requestVideoFrameCallback(cb);
    v.muted = false; v.playbackRate = rate;
    const errors = []; v.addEventListener("error", () => errors.push(v.error && v.error.message));
    const t0 = performance.now();
    await v.play();
    await new Promise((r) => v.addEventListener("ended", r, { once: true }));
    out.ended = v.ended; out.playedSeconds = v.currentTime; out.wallSeconds = (performance.now() - t0) / 1000;
    out.videoFramesPainted = frames; out.audioDecodedBytes = v.webkitAudioDecodedByteCount; out.videoDecodedBytes = v.webkitVideoDecodedByteCount;
    out.errors = errors; return out;
  }, rate).catch((e) => ({ error: String(e) }));
  console.log(JSON.stringify(res));
  await browser.close();
})();
