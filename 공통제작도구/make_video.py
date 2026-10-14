#!/usr/bin/env python3
"""에피소드 폴더의 영상/scenes.json 으로 재현 화면 무음 시안 mp4를 만들고 검수한다.
사용: python3 -I make_video.py <에피소드폴더> [--sheets-only]
순서: 폰트 확인 → 샘플 프레임 + 확인용 시트 → (전체 렌더 2,100프레임 병렬) → 인코딩 → 썸네일 → 검수 → 재생 확인 → 정지 화면 검사
임시 파일은 .harness-tmp/ 아래에만 만든다(규칙 K)."""
import json, os, subprocess, sys, shutil, time
here = os.path.dirname(os.path.abspath(__file__)); root = os.path.dirname(here)
folder = os.path.abspath(sys.argv[1]); sheets_only = "--sheets-only" in sys.argv
NN = os.path.basename(folder).split("_")[1]
EP = json.load(open(os.path.join(folder, "영상", "scenes.json"), encoding="utf-8"))
tmp = os.path.join(root, ".harness-tmp", f"ep{NN}"); os.makedirs(tmp, exist_ok=True)
env = dict(os.environ, NODE_PATH="/opt/node-tools/node_modules", SCENES_JSON=os.path.join(folder, "영상", "scenes.json"), SCENES_JS=os.path.join(folder, "영상", "scenes.js"))
def run(*a, **k): return subprocess.run(a, capture_output=True, text=True, env=env, **k)
def step(n): print(f"[{time.strftime('%H:%M:%S')}] {n}", flush=True)
if not os.path.exists(os.path.join(root, ".harness-tmp", "fonts", "NotoSansKR-900.woff")):
    step("폰트 내려받기"); subprocess.run(["sh", os.path.join(here, "fetch_fonts.sh")], check=True)
step("샘플 프레임")
smp = os.path.join(tmp, "smp"); shutil.rmtree(smp, ignore_errors=True)
r = run("node", os.path.join(here, "render.js"), "sample", smp, "4"); print(r.stdout.strip().splitlines()[-1:], r.stderr[-300:])
from PIL import Image
import glob
def sheet(files, name, cols=8, w=270):
    h = int(w * 16 / 9); rows = (len(files) + cols - 1) // cols
    im = Image.new("RGB", (cols * w, rows * h))
    for i, f in enumerate(files): im.paste(Image.open(f).resize((w, h)), ((i % cols) * w, (i // cols) * h))
    im.save(name)
sheet(sorted(glob.glob(smp + "/s*_0.jpg")), os.path.join(tmp, "sheet_a.jpg")); sheet(sorted(glob.glob(smp + "/s*_1.jpg")), os.path.join(tmp, "sheet_b.jpg"))
if sheets_only: step("시트만 만들고 종료: " + tmp); sys.exit(0)
step("전체 렌더"); fr = os.path.join(tmp, "full"); shutil.rmtree(fr, ignore_errors=True)
r = run("node", os.path.join(here, "render.js"), "full", fr, "4"); print(r.stdout.strip().splitlines()[-2:], r.stderr[-300:])
out = os.path.join(folder, "최종영상"); os.makedirs(out, exist_ok=True)
mp4 = os.path.join(out, f"ep{NN}_재현화면_무음시안.mp4")
step("인코딩")
r = run("ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i", fr + "/f%05d.jpg", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", "30", "-map_metadata", "-1", "-movflags", "+faststart", mp4); print(r.stderr[-300:])
if EP.get("thumb"):
    r = run("node", os.path.join(here, "render.js"), "thumb", tmp + "/thumb"); shutil.copy(tmp + "/thumb/thumbnail.png", os.path.join(out, f"ep{NN}_thumbnail.png"))
for f in ("scenes.json", f"ep{NN}_caption.srt", f"ep{NN}_narration.srt"): shutil.copy(os.path.join(folder, "영상", f), out)
step("검수"); v = run("python3", "-I", os.path.join(here, "verify_silent.py"), mp4, os.path.join(out, "scenes.json")); print(v.stdout)
step("재생 확인(VP9 사본)")
webm = os.path.join(tmp, "p.webm"); run("ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-c:v", "libvpx-vp9", "-b:v", "1M", "-deadline", "realtime", "-cpu-used", "8", "-an", webm)
p = run("node", os.path.join(here, "play_check.js"), webm, "4"); print(p.stdout.strip()[-400:])
fz = run("ffmpeg", "-v", "error", "-i", mp4, "-vf", "freezedetect=n=-60dB:d=2.5", "-f", "null", "-"); n = (fz.stderr + fz.stdout).count("freeze_start"); print("정지 화면 2.5초 이상:", n, "건")
# 확인용 프레임 시트(전환 구간): 장면 경계 직후 0.1초
ts = [s["start"] + 0.1 for s in EP["scenes"]]; fs = []
for i, t in enumerate(ts):
    f = os.path.join(tmp, f"b{i:02d}.png"); run("ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", mp4, "-frames:v", "1", f); fs.append(f)
sheet(fs, os.path.join(tmp, "sheet_start.jpg"))
ok = v.returncode == 0 and '"ended":true' in p.stdout.replace(" ", "") and '"errors":[]' in p.stdout.replace(" ", "") and n == 0
json.dump(dict(ok=ok, verify=v.stdout.strip().splitlines()[-1], play=p.stdout.strip(), freeze=n, size=os.path.getsize(mp4)), open(os.path.join(tmp, "result.json"), "w", encoding="utf-8"), ensure_ascii=False)
step("완료 " + ("합격" if ok else "불합격")); sys.exit(0 if ok else 1)
