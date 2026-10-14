#!/usr/bin/env python3
"""얼굴·본인 목소리 합성본(epNN.mp4) 검수. 사용: python3 -I verify_final.py <mp4> <작업폴더의 scenes_final.json>  (실패 시 종료코드 1)
확인: 규격, 길이(60~90초), 디코딩 오류 0건, 위치정보 태그 없음, 음량(-16±1.5 LUFS, 피크 ≤ -1 dBFS), 장면별 말 구간이 시간표와 일치하고 자기 장면 안에 있는지,
      재현 화면·AI 음성 배지 설정, 얼굴 합성 장면 수. 소리를 귀로 듣는 확인은 하지 못한다(사람이 해야 함)."""
import json, re, subprocess, sys, wave
import numpy as np
mp4, sj = sys.argv[1], sys.argv[2]
F = json.load(open(sj, encoding="utf-8")); res = []
def chk(n, ok, msg): res.append(ok); print(("PASS" if ok else "FAIL"), n, msg)
def run(*a): return subprocess.run(a, capture_output=True, text=True)
pr = json.loads(run("ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", mp4).stdout)
vs = [s for s in pr["streams"] if s["codec_type"] == "video"][0]; au = [s for s in pr["streams"] if s["codec_type"] == "audio"]
dur = float(pr["format"]["duration"])
chk("F01", (vs["width"], vs["height"]) == (1080, 1920) and vs["codec_name"] == "h264" and vs["pix_fmt"] == "yuv420p" and vs["r_frame_rate"] == "30/1", f'규격 {vs["width"]}x{vs["height"]} {vs["codec_name"]} {vs["pix_fmt"]} {vs["r_frame_rate"]}')
chk("F02", 60 <= dur <= 90 and abs(dur - F["total"]) < 0.1, f"길이 {dur:.2f}초(시간표 {F['total']}초, 규격 60~90초)")
chk("F03", int(vs["nb_read_frames"]) == F["frames"], f'프레임 수 {vs["nb_read_frames"]} (기대 {F["frames"]})')
chk("F04", run("ffmpeg", "-v", "error", "-i", mp4, "-f", "null", "-").stderr.strip() == "", "전체 디코딩 오류 0건")
tags = json.dumps(pr["format"].get("tags", {})) + "".join(json.dumps(s.get("tags", {})) for s in pr["streams"])
chk("F05", not re.search(r"location|gps|iso6709|latitude|longitude", tags, re.I), "위치정보(GPS) 태그 없음")
chk("F06", len(au) == 1 and au[0]["codec_name"] == "aac", "오디오 트랙 1개(aac)")
eb = run("ffmpeg", "-nostats", "-i", mp4, "-af", "ebur128=peak=true", "-f", "null", "-").stderr
lufs = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", eb)[-1]); peak = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", eb)[-1])
chk("F07", abs(lufs + 16) <= 1.5 and peak <= -1.0, f"음량 {lufs} LUFS(목표 -16±1.5), 피크 {peak} dBFS(≤ -1)")
import tempfile, os
vf = os.path.join(tempfile.mkdtemp(), "vf.wav")   # 병렬로 여러 개를 검수해도 서로 덮어쓰지 않게 실행마다 따로 만든다(DEC-055)
run("ffmpeg", "-v", "error", "-y", "-i", mp4, "-vn", "-ac", "1", "-ar", "16000", vf)
w = wave.open(vf); a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
win = int(w.getframerate() * 0.02); k = len(a) // win
db = 20 * np.log10(np.sqrt(np.mean(a[:k * win].reshape(k, win) ** 2, axis=1)) + 1e-9)
m = db > max(np.percentile(db, 10) + 12, -50); iv = []; i = 0
while i < k:
    if m[i]:
        j = i
        while j < k and m[j]: j += 1
        iv.append([i * 0.02, j * 0.02]); i = j
    else: i += 1
mg = []
for s, e in iv:
    if mg and s - mg[-1][1] < 0.25: mg[-1][1] = e
    else: mg.append([s, e])
mg = [x for x in mg if x[1] - x[0] >= 0.12]
clips = F["clips"]
# 사람이 읽으면 한 줄 안에도 0.4~0.9초 쉼이 있어 말 구간 수가 장면 수보다 많다. 구간을 각 장면의 말 시간표(speech_t0~t1 ± 0.3초)에 배정해서 확인한다(DEC-055)
asg = {i: [] for i in range(len(clips))}; stray = []
for s_, e_ in mg:
    hit = [i for i, c in enumerate(clips) if s_ < c["speech_t1"] + 0.3 and e_ > c["speech_t0"] - 0.3]
    if len(hit) == 1: asg[hit[0]].append((s_, e_))
    else: stray.append((round(s_, 2), round(e_, 2), hit))
empty = [clips[i]["scene"] for i, v in asg.items() if not v]
chk("F08", not empty and not stray, f"말 구간 {len(mg)}개를 {len(clips)}장면에 빠짐없이 배정(소리 없는 장면 {empty or '없음'}, 어느 장면에도 안 맞거나 두 장면에 걸친 소리 {stray or '없음'})")
if not empty and not stray:
    dif = [d_ for c, v in zip(clips, asg.values()) for d_ in (abs(v[0][0] - c["speech_t0"]), abs(v[-1][1] - c["speech_t1"]))]
    mx, md = max(dif), float(np.median(dif))
    # 아주 작은 말 시작·끝(감지 기준 −50dB 근처)은 최종 소리에서 0.2초쯤 다르게 잡힐 수 있어 최대는 0.25초까지 허용하고, 소리 전체가 밀린 경우를 잡기 위해 중앙값은 0.05초로 엄격히 본다(DEC-055: 2편 16번 장면에서 +0.203초 관찰)
    chk("F09", mx <= 0.25 and md <= 0.05, f"말 시작·끝이 시간표와 최대 {mx:.3f}초(허용 0.25), 중앙값 {md:.3f}초(허용 0.05) 차이")
    out = [c["scene"] for c, v, sc in zip(clips, asg.values(), F["scenes"]) if not (sc["start"] - 0.05 <= v[0][0] and v[-1][1] <= sc["end"] + 0.05)]
    chk("F10", not out, f"말이 자기 장면 시간 밖으로 나간 장면: {out or '없음'}")
chk("F11", F.get("voice") == "user" and F.get("mock_badge") is False, f'본인 음성 표기 voice={F.get("voice")}, 영상 배지 mock_badge={F.get("mock_badge")}')
face = sum(1 for c in clips if c["has_video"])
chk("F12", face == len(clips), f"얼굴 합성 장면 {face}/{len(clips)}(오디오만 있는 장면은 얼굴 없이 나옴)")
print(f"{sum(res)}/{len(res)} 통과"); sys.exit(0 if all(res) else 1)
