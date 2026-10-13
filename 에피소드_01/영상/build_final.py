#!/usr/bin/env python3
"""사용자 촬영 파일(얼굴 영상 또는 음성 파일)로 최종 영상을 만든다. (DEC-032)

사용: python3 -I build_final.py <영상폴더> <촬영폴더> <작업폴더> <출력폴더>
 촬영폴더 안의 파일 이름 규칙 (확장자: mp4, mov, m4v, mp3, m4a, wav, aac):
  - 방법 A: 01 ~ 15  (장면별 파일)
  - 방법 B: 전체      (한 파일, 장면 사이 2초 쉬기). 01~15 파일이 같이 있으면 그 장면은 그 파일로 교체한다.
  - 방법 C: cuts.json (한 파일 + 사용자가 확인한 장면별 시각표. 쉼이 짧아 자동 분할이 안 될 때, DEC-037)
      {"file": "틱톡영상_01.mp4", "scenes": [{"id": 1, "start": 0.91, "end": 2.79}, ...,
       {"id": 12, "start": 49.46, "end": 53.6, "snap_end": true}, ...]}
      snap_end=true: 다음 장면과 붙어 있는 경계(쉼 없음). 추정 시각 ±0.5초 안에서 소리가 가장 작은 지점(말 사이 틈)으로 맞춘다.
 출력폴더에 만드는 것: ep01.mp4, scenes.json(최종 시간표), ep01_caption.srt, ep01_narration.srt

동작
 1) 촬영 파일에서 말소리 구간을 찾는다(잡음 바닥보다 12dB 이상 큰 소리). 앞 0.15초·뒤 0.30초를 여유로 남긴다.
 2) 장면 시간표를 다시 계산한다: 장면 길이 = max(기획 길이, 말소리 길이). 말이 길면 그 장면을 늘리고 뒤 장면을 민다. 총 60~90초가 아니면 실패.
 3) 얼굴이 있는 파일은 원형(지름 270px)으로 잘라 자막 오른쪽 옆에 넣고, 소리는 그 파일의 소리를 쓴다(입모양 싱크 유지).
 4) 위치 정보 등 메타데이터는 모두 제거한다. 폰 HDR 영상은 SDR로 변환한다.
"""
import json, math, os, subprocess, sys, wave
import numpy as np

vdir, rec, work, out = [os.path.abspath(p) for p in sys.argv[1:5]]
HERE = os.path.dirname(os.path.abspath(__file__))
FPS, PRE, POST, GAP_B = 30, 0.15, 0.30, 1.2
PIP = dict(x=655, y=1120, d=270)           # 자막 오른쪽 옆 (틱톡 버튼 추정 영역 x>930, 하단 y>1536을 피함)
FACE_Y = float(os.environ.get("FACE_Y", "0.35"))   # 세로 영상에서 정사각형으로 자를 때 위쪽 기준 위치(0=맨 위, 0.5=가운데)
MINLEN, MAXLEN = 60.0, 90.0
EXT = (".mp4", ".mov", ".m4v", ".mp3", ".m4a", ".wav", ".aac")
NODE_PATH = os.environ.get("NODE_PATH", "/opt/node-tools/node_modules")
CHROME = os.environ.get("CHROME_PATH", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
base = json.load(open(os.path.join(vdir, "scenes.json"), encoding="utf-8"))
N = len(base["scenes"])
os.makedirs(work, exist_ok=True); os.makedirs(out, exist_ok=True)


def fail(msg, code=3):
    print("FAIL:", msg); sys.exit(code)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("명령 실패:", " ".join(str(c) for c in cmd[:8]), "...\n", r.stderr[-2000:]); sys.exit(5)
    return r


def probe(path):
    return json.loads(run(["ffprobe", "-v", "error", "-of", "json", "-show_format", "-show_streams", path]).stdout)


def to_wav(src, dst):
    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", dst])


def runs(mask):
    res, i, n = [], 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]: j += 1
            res.append([i, j]); i = j
        else: i += 1
    return res


def speech_intervals(wavpath, win=0.02):
    w = wave.open(wavpath); sr = w.getframerate()
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    n = int(sr * win); k = len(a) // n
    if k == 0: return []
    db = 20 * np.log10(np.sqrt(np.mean(a[:k * n].reshape(k, n) ** 2, axis=1)) + 1e-9)
    thr = max(float(np.percentile(db, 10)) + 12.0, -50.0)   # 잡음 바닥 + 12dB, 절대 하한 -50dBFS
    merged = []
    for s, e in runs(db > thr):
        if merged and (s - merged[-1][1]) * win < 0.25: merged[-1][1] = e   # 0.25초 미만 구멍은 메운다
        else: merged.append([s, e])
    return [(s * win, e * win) for s, e in merged if (e - s) * win >= 0.12]


def energy_db(wavpath, win=0.02):
    w = wave.open(wavpath)
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    n = int(w.getframerate() * win); k = len(a) // n
    return 20 * np.log10(np.sqrt(np.mean(a[:k * n].reshape(k, n) ** 2, axis=1)) + 1e-9)


def snap_to_gap(db, t, win=0.02, span=0.5):
    """추정 경계 t 주변 ±span초에서 소리가 가장 작은 지점(60ms 평균)을 찾는다. 말 사이 틈에 경계를 맞추기 위함."""
    sm = np.convolve(db, np.ones(3) / 3, mode="same")
    lo, hi = max(0, int((t - span) / win)), min(len(sm), int((t + span) / win))
    i = lo + int(np.argmin(sm[lo:hi]))
    return round((i + 0.5) * win, 3), float(sm[i])


def clip_info(scene, path, ss0=None, se0=None, dur=None, pre=PRE, post=POST):
    info = probe(path)
    vs = [s for s in info["streams"] if s["codec_type"] == "video"]
    if not [s for s in info["streams"] if s["codec_type"] == "audio"]:
        fail(f"장면 {scene:02d}: {os.path.basename(path)}에 오디오 트랙이 없습니다.")
    total = float(info["format"]["duration"])
    if ss0 is None:
        wav = os.path.join(work, f"a_{scene:02d}.wav"); to_wav(path, wav)
        iv = speech_intervals(wav)
        if not iv: fail(f"장면 {scene:02d}: {os.path.basename(path)}에서 말소리를 찾지 못했습니다(너무 작거나 무음).")
        ss0, se0 = iv[0][0], iv[-1][1]
    hdr = bool(vs) and vs[0].get("color_transfer") in ("smpte2084", "arib-std-b67")
    return dict(scene=scene, src=path, ss=max(0.0, ss0 - pre), ee=min(total, se0 + post), speech_start=ss0, speech_end=se0,
                has_video=bool(vs), hdr=hdr, mode_file=os.path.basename(path))


# ---------- 1) 촬영 파일 찾기와 말소리 구간 분석 ----------
files = {}
for f in sorted(os.listdir(rec)):
    n, e = os.path.splitext(f)
    if e.lower() in EXT: files[n] = os.path.join(rec, f)
clips, mode = [], None
CUTS = os.path.join(rec, "cuts.json")
if os.path.exists(CUTS):
    mode = "C"
    cj = json.load(open(CUTS, encoding="utf-8"))
    src = os.path.join(rec, cj["file"])
    if not os.path.exists(src): fail(f"cuts.json의 파일 '{cj['file']}'이 촬영 폴더에 없습니다.")
    cs = sorted(cj["scenes"], key=lambda c: c["id"])
    DENOISE = cj.get("denoise")   # {"wet": 0.8}: 마이크 없이 녹음한 노이즈를 줄인다(denoise_audio.py, DEC-042). 없으면 원본 소리
    MOCK_BADGE = cj.get("mock_badge", True)   # false면 영상의 "재현 화면" 배지를 그리지 않는다(사용자 결정, DEC-041)
    if [c["id"] for c in cs] != list(range(1, N + 1)): fail(f"cuts.json의 장면 번호가 1~{N}이 아닙니다.")
    wav = os.path.join(work, "a_all.wav"); to_wav(src, wav); db = energy_db(wav)
    den_wav = None
    if DENOISE:
        den_wav = os.path.join(work, "a_denoised.wav")
        vpy = os.path.join(HERE, "..", "..", ".harness-tmp", "asr", "venv", "bin", "python")
        r_ = subprocess.run([vpy, os.path.join(HERE, "denoise_audio.py"), wav, den_wav, os.path.join(HERE, "..", "..", ".harness-tmp", "dn", "dpdfnet2_48khz_hr.onnx"), str(DENOISE.get("wet", 0.70))], capture_output=True, text=True)
        if r_.returncode != 0 or not os.path.exists(den_wav): print(r_.stdout[-500:], r_.stderr[-800:]); fail("노이즈 제거에 실패했습니다. fetch_asr.sh와 fetch_denoise.sh로 도구를 설치했는지 확인하세요.", 5)
        print("노이즈 제거:", r_.stdout.strip())
    total_src = float(probe(src)["format"]["duration"])
    st, en = [float(c["start"]) for c in cs], [float(c["end"]) for c in cs]
    cut_log = []
    for i, c in enumerate(cs):
        if c.get("snap_end") and i + 1 < N:
            b, lvl = snap_to_gap(db, en[i]); cut_log.append((c["id"], en[i], b, round(lvl, 1)))
            en[i] = st[i + 1] = b
    for i in range(N):
        if not (0 <= st[i] < en[i] <= total_src + 1e-6): fail(f"cuts.json 장면 {i + 1}: 시작·끝 시각이 올바르지 않습니다({st[i]}~{en[i]}).")
        if i + 1 < N and en[i] > st[i + 1] + 1e-6: fail(f"cuts.json 장면 {i + 1}과 {i + 2}가 겹칩니다({en[i]} > {st[i + 1]}).")
    for i in range(N):
        gb = (st[i] - en[i - 1]) if i else st[i]
        ga = (st[i + 1] - en[i]) if i + 1 < N else total_src - en[i]
        # 앞뒤 여유는 이웃 장면과의 간격의 절반을 넘기지 않는다(붙어 있는 장면은 0). 이웃 대사 조각이 섞이지 않게 하기 위함
        c = clip_info(i + 1, src, st[i], en[i], pre=min(PRE, max(0.0, gb) / 2), post=min(POST, max(0.0, ga) / 2))
        if den_wav: c["audio_src"] = den_wav     # 소리는 노이즈를 줄인 파일에서, 화면(얼굴)은 원본 영상에서
        c["cues_src"] = cs[i].get("cues")     # 구절 시각(촬영본 기준 초). 아래에서 장면 기준으로 바꾼다
        c["contig_prev"] = bool(i) and abs(st[i] - en[i - 1]) < 1e-6
        c["contig_next"] = i + 1 < N and abs(st[i + 1] - en[i]) < 1e-6
        clips.append(c)
    for x in cut_log: print(f"경계 맞춤: 장면 {x[0]} 끝 추정 {x[1]:.2f}s → {x[2]:.2f}s (그 지점 음량 {x[3]}dB)")
elif "전체" in files:
    mode = "B"
    wav = os.path.join(work, "a_all.wav"); to_wav(files["전체"], wav)
    segs = []
    for s, e in speech_intervals(wav):
        if segs and s - segs[-1][1] < GAP_B: segs[-1][1] = e
        else: segs.append([s, e])
    over = {i for i in range(1, N + 1) if f"{i:02d}" in files}
    if len(segs) != N and len(over) != N:
        fail(f"'전체' 파일에서 장면 {len(segs)}개를 찾았습니다(기대 {N}개). 장면 사이를 2초 이상 쉬었는지 확인해 주세요. 찾은 구간(초): " +
             ", ".join(f"{s:.1f}~{e:.1f}" for s, e in segs))
    whole_total = float(probe(files["전체"])["format"]["duration"])
    for i in range(1, N + 1):
        if i in over: clips.append(clip_info(i, files[f"{i:02d}"]))
        else:
            s, e = segs[i - 1]
            c = clip_info(i, files["전체"], s, e); clips.append(c)
else:
    missing = [f"{i:02d}" for i in range(1, N + 1) if f"{i:02d}" not in files]
    if missing: fail("장면별 파일이 부족합니다. 없는 번호: " + ", ".join(missing) + " (한 파일로 녹음했다면 '전체' 이름으로 두세요)")
    mode = "A"
    for i in range(1, N + 1): clips.append(clip_info(i, files[f"{i:02d}"]))

# ---------- 2) 장면 시간표 다시 계산 ----------
scenes, cursor, rows = [], 0.0, []
for sc, c in zip(base["scenes"], clips):
    L = c["ee"] - c["ss"]
    d = max(float(sc["duration"]), math.ceil(L * FPS) / FPS)
    scenes.append(dict(sc, start=round(cursor, 4), end=round(cursor + d, 4), duration=round(d, 4), base_duration=sc["duration"]))
    c["start"] = round(cursor, 4); c["len"] = round(L, 4)
    c.setdefault("contig_prev", False); c.setdefault("contig_next", False)
    if c.get("cues_src"):   # 촬영본 시각 -> 장면 안 시각(장면은 clip 시작 ss부터 소리가 나오므로 t - ss)
        scenes[-1]["cues"] = {k: round(v - c["ss"], 3) for k, v in c["cues_src"].items()}
    c["speech_t0"] = round(cursor + (c["speech_start"] - c["ss"]), 3); c["speech_t1"] = round(cursor + (c["speech_end"] - c["ss"]), 3)
    rows.append((sc["id"], sc["duration"], round(L, 2), round(d, 2)))
    cursor += d
total = round(cursor, 4)
if not (MINLEN <= total <= MAXLEN):
    fail(f"총 길이 {total:.1f}초가 규격({MINLEN:.0f}~{MAXLEN:.0f}초)을 벗어납니다. 말을 줄이거나 쉬는 시간을 줄여 주세요.", 4)
frames = int(round(total * FPS))
final = dict(base, total=total, frames=frames, scenes=scenes, pip=PIP, voice="user", mode=mode, mock_badge=globals().get("MOCK_BADGE", True),
             clips=[{k: c[k] for k in ("scene", "mode_file", "ss", "ee", "start", "len", "speech_t0", "speech_t1", "has_video", "hdr", "contig_prev", "contig_next")} for c in clips], denoise=globals().get("DENOISE"))
fj = os.path.join(work, "scenes_final.json"); fs_ = os.path.join(work, "scenes_final.js")
json.dump(final, open(fj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(fs_, "w", encoding="utf-8").write("window.EP = " + json.dumps(final, ensure_ascii=False) + ";\n")


def ts(sec):
    ms = int(round(sec * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


for name, key in (("ep01_caption.srt", "caption"), ("ep01_narration.srt", "narration")):
    with open(os.path.join(out, name), "w", encoding="utf-8") as f:
        for sc in scenes: f.write(f"{sc['id']}\n{ts(sc['start'])} --> {ts(sc['end'])}\n{sc[key]}\n\n")
json.dump(final, open(os.path.join(out, "scenes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"방법 {mode}, 장면 {N}개, 총 {total:.2f}초({frames}프레임). 장면별 [기획초 / 말 길이 / 최종초]")
for r in rows: print(f"  장면 {r[0]:2d}: {r[1]}s / {r[2]}s / {r[3]}s" + ("  ← 늘림" if r[3] > r[1] + 1e-6 else ""))

# ---------- 3) 화면(프레임) 그리기 ----------
frames_dir = os.path.join(work, "frames"); os.makedirs(frames_dir, exist_ok=True)
env = dict(os.environ, NODE_PATH=NODE_PATH, CHROME_PATH=CHROME, SCENES_JSON=fj, SCENES_JS=fs_)
r = subprocess.run(["node", os.path.join(HERE, "render.js"), "full", frames_dir, "6"], env=env, capture_output=True, text=True)
if r.returncode != 0 or len([x for x in os.listdir(frames_dir) if x.endswith(".jpg")]) != frames:
    print(r.stdout[-500:], r.stderr[-1500:]); fail(f"프레임 {frames}장을 만들지 못했습니다.", 5)

# ---------- 4) 소리 합치기 ----------
args, filt, mixin = ["ffmpeg", "-v", "error", "-y"], [], []
for k, c in enumerate(clips):
    args += ["-ss", f"{c['ss']:.3f}", "-t", f"{c['len']:.3f}", "-i", c.get("audio_src", c["src"])]
    filt.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=mono,highpass=f=70,adelay={int(round(c['start'] * 1000))}:all=1[a{k}]")
    mixin.append(f"[a{k}]")
filt.append("".join(mixin) + f"amix=inputs={len(clips)}:normalize=0:dropout_transition=0,loudnorm=I=-16:TP=-1.5:LRA=11[o]")
wav1 = os.path.join(work, "voice_mix.wav"); wav2 = os.path.join(work, "voice.wav")
run(args + ["-filter_complex", ";".join(filt), "-map", "[o]", "-ar", "48000", "-ac", "1", wav1])
run(["ffmpeg", "-v", "error", "-y", "-i", wav1, "-af", f"apad=whole_dur={total}", "-t", str(total), wav2])

# ---------- 5) 화면 + 얼굴 합성 ----------
from PIL import Image, ImageDraw
D = PIP["d"]
m = Image.new("L", (D * 4, D * 4), 0); ImageDraw.Draw(m).ellipse((0, 0, D * 4 - 1, D * 4 - 1), fill=255); m.resize((D, D), Image.LANCZOS).save(os.path.join(work, "mask.png"))
rg = Image.new("RGBA", (D * 4, D * 4), (0, 0, 0, 0)); ImageDraw.Draw(rg).ellipse((0, 0, D * 4 - 1, D * 4 - 1), outline=(56, 201, 187, 255), width=28); rg.resize((D, D), Image.LANCZOS).save(os.path.join(work, "ring.png"))
vids = [c for c in clips if c["has_video"]]
vargs = ["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(frames_dir, "f%05d.jpg"), "-i", wav2]
vf, last = [], "[0:v]"
if vids:
    vargs += ["-loop", "1", "-i", os.path.join(work, "mask.png"), "-loop", "1", "-i", os.path.join(work, "ring.png")]
    mi, ri = 2, 3
    vf.append(f"[{mi}:v]format=gray,split={len(vids)}" + "".join(f"[m{j}]" for j in range(len(vids))))
    vf.append(f"[{ri}:v]format=rgba,split={len(vids)}" + "".join(f"[r{j}]" for j in range(len(vids))))
    for j, c in enumerate(vids):
        idx = 4 + j
        vargs += ["-ss", f"{c['ss']:.3f}", "-t", f"{c['len']:.3f}", "-i", c["src"]]
        hdr = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,"
               if c["hdr"] else "")
        T, L = c["start"], c["len"]
        vf.append(f"[{idx}:v]fps={FPS},setpts=PTS-STARTPTS,{hdr}crop=w=min(iw\\,ih):h=min(iw\\,ih):x=(iw-min(iw\\,ih))/2:y=(ih-min(iw\\,ih))*{FACE_Y},"
                  f"scale={D}:{D}:flags=lanczos,format=yuv420p[f{j}]")
        vf.append(f"[f{j}][r{j}]overlay=0:0:format=auto,format=yuva420p[g{j}]")
        fin = "" if c["contig_prev"] else ",fade=t=in:st=0:d=0.12:alpha=1"           # 붙어 있는 장면 경계에서는 얼굴이 깜빡이지 않게 페이드를 넣지 않는다
        fout = "" if c["contig_next"] else f",fade=t=out:st={max(0.0, L - 0.12):.3f}:d=0.12:alpha=1"
        vf.append(f"[g{j}][m{j}]alphamerge{fin}{fout},setpts=PTS+{T:.3f}/TB[p{j}]")
        vf.append(f"{last}[p{j}]overlay=x={PIP['x']}:y={PIP['y']}:eof_action=pass:enable='between(t,{T:.3f},{T + L:.3f})'[v{j}]")
        last = f"[v{j}]"
    vf.append(f"{last}format=yuv420p[vout]")
else:
    vf.append("[0:v]format=yuv420p[vout]")
mp4 = os.path.join(out, "ep01.mp4")
run(vargs + ["-filter_complex", ";".join(vf), "-map", "[vout]", "-map", "1:a", "-t", str(total), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart",
             "-map_metadata", "-1", "-map_chapters", "-1", mp4])
print("OK", mp4, f"{os.path.getsize(mp4) / 2**20:.2f}MB", "얼굴 합성", len(vids), "장면 /", len(clips))
