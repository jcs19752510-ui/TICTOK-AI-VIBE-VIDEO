#!/usr/bin/env python3
"""4단계(검수): 완성된 mp4와 자막·설계 파일을 자동 검사하고 JSON으로 결과를 낸다.
사용: python3 -I verify_video.py <영상폴더> <mp4> <thumbnail.png> <샘플프레임폴더>
"""
import json, os, re, subprocess, sys
import numpy as np
from PIL import Image

vdir, mp4, thumb, tmp = sys.argv[1:5]
EP = json.load(open(os.path.join(vdir, "scenes.json"), encoding="utf-8"))
res = []


def chk(i, name, ok, detail=""):
    res.append(dict(id=i, name=name, result="PASS" if ok else "FAIL", detail=str(detail)))


def probe(path, *args):
    return json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-of", "json", *args, path]))


fmt = probe(mp4, "-show_format", "-show_streams")
vs = [s for s in fmt["streams"] if s["codec_type"] == "video"]
as_ = [s for s in fmt["streams"] if s["codec_type"] == "audio"]
v = vs[0]
dur = float(fmt["format"]["duration"])
chk("V01", "해상도 1080x1920 (9:16 세로)", v["width"] == 1080 and v["height"] == 1920, f'{v["width"]}x{v["height"]}')
chk("V02", "영상 길이 63초 (±0.1초)", abs(dur - EP["total"]) <= 0.1, f"{dur:.3f}초")
num, den = map(int, v["r_frame_rate"].split("/"))
chk("V03", "프레임레이트 30fps", num / den == 30, v["r_frame_rate"])
nb = int(v.get("nb_frames", 0))
chk("V04", "총 프레임 수 1890", nb == EP["frames"], nb)
chk("V05", "코덱 H.264, 픽셀 포맷 yuv420p (틱톡 업로드 호환)", v["codec_name"] == "h264" and v["pix_fmt"] == "yuv420p", f'{v["codec_name"]}/{v["pix_fmt"]}')
chk("V06", "오디오 트랙 존재 (AAC, 48kHz)", len(as_) == 1 and as_[0]["codec_name"] == "aac" and as_[0]["sample_rate"] == "48000", [(a["codec_name"], a["sample_rate"]) for a in as_])
adur = float(as_[0]["duration"]) if as_ else -1
chk("V07", "오디오·영상 길이 차이 0.1초 이하 (싱크)", abs(adur - dur) <= 0.1, f"영상 {dur:.3f} / 오디오 {adur:.3f}")
size = os.path.getsize(mp4)
chk("V08", "파일 크기 50MB 이하", size <= 50 * 2**20, f"{size / 2**20:.2f}MB")
tags = fmt["format"].get("tags", {})
chk("V09", "컨테이너 메타데이터에 개인정보 없음 (이메일·경로 패턴 검사)", not re.search(r"@|/home/|/root/", json.dumps(tags, ensure_ascii=False)), json.dumps(tags, ensure_ascii=False))


# ---- 음성 검수 ----
def run(*a):
    return subprocess.run(a, capture_output=True, text=True)

vol = run("ffmpeg", "-hide_banner", "-i", mp4, "-af", "volumedetect", "-vn", "-f", "null", "-").stderr
mean = float(re.search(r"mean_volume: (-?[\d.]+) dB", vol).group(1)); peak = float(re.search(r"max_volume: (-?[\d.]+) dB", vol).group(1))
chk("V18", "음성이 들어 있음: 평균 음량 −35dB 초과(무음 −91dB 아님)", mean > -35, f"평균 {mean}dB")
chk("V19", "음량 적정: 최대 피크 −1dB 이하(클리핑 없음), 평균 −26dB 이상", peak <= -1 and mean >= -26, f"피크 {peak}dB, 평균 {mean}dB")
sd = run("ffmpeg", "-hide_banner", "-i", mp4, "-af", "silencedetect=noise=-40dB:d=0.25", "-vn", "-f", "null", "-").stderr
starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", sd)]
ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", sd)]
# 음성 구간 = 무음 구간 사이. 무음 끝(silence_end)이 음성 시작
speech_starts = [0.0 if (not starts or starts[0] > 0.05) else None] + ends
speech_starts = [s for s in speech_starts if s is not None]
chk("V20", "음성 시작이 15장면 각각 [장면 시작, 장면 시작+0.9초] 안에 있음(싱크)", len(speech_starts) >= 15 and all(any(sc["start"] <= s <= sc["start"] + 0.9 for s in speech_starts) for sc in EP["scenes"]),
    [(sc["id"], next((round(s, 2) for s in speech_starts if sc["start"] <= s <= sc["start"] + 0.9), None)) for sc in EP["scenes"]])
last_end = starts[-1] if starts else dur
chk("V21", "마지막 음성이 영상 끝 0.2초 전에 끝남(잘림 없음)", last_end <= dur - 0.2, f"마지막 음성 끝 {last_end:.2f}s / 영상 {dur:.2f}s")
dec = run("ffmpeg", "-v", "error", "-i", mp4, "-f", "null", "-")
chk("V22", "ffmpeg 전체 디코딩(영상+오디오) 오류 0건", dec.returncode == 0 and dec.stderr.strip() == "", dec.stderr.strip()[:200] or "오류 없음")

# 자막
caps = [s["caption"] for s in EP["scenes"]]
chk("V10", "화면 자막 모든 장면 존재, 20자 이내", all(c and len(c) <= 20 for c in caps), [len(c) for c in caps])
for name, key in (("ep01_caption.srt", "caption"), ("ep01_narration.srt", "narration")):
    t = open(os.path.join(vdir, name), encoding="utf-8").read()
    blocks = [b for b in t.strip().split("\n\n")]
    ok = len(blocks) == 15
    for b, sc in zip(blocks, EP["scenes"]):
        l = b.split("\n")
        exp = f"00:{sc['start'] // 60:02d}:{sc['start'] % 60:02d},000 --> 00:{sc['end'] // 60:02d}:{sc['end'] % 60:02d},000"
        ok = ok and l[1] == exp and l[2] == sc[key]
    chk("V11" if key == "caption" else "V12", f"{name}: 15개, 시간·문구가 scenes.json과 일치", ok)

# 프레임 샘플 (1초 간격 + 장면 경계 직후): 안전 영역과 대비
os.makedirs(tmp, exist_ok=True)
subprocess.check_call(["ffmpeg", "-loglevel", "error", "-y", "-i", mp4, "-vf", "fps=1", os.path.join(tmp, "v%03d.png")])
files = sorted(f for f in os.listdir(tmp) if f.startswith("v") and f.endswith(".png"))
chk("V13", "1초 간격 샘플 프레임 63장 추출", len(files) == EP["total"], len(files))
bottom_bad, top_bad, lum_min = [], [], 255
for f in files:
    a = np.asarray(Image.open(os.path.join(tmp, f)).convert("L"), dtype=np.int16)
    if (a[1536:] > 70).any(): bottom_bad.append(f)           # 하단 20%: 밝은(글자·그래픽) 픽셀이 없어야 함
    if (a[1500:1536] > 70).any(): bottom_bad.append(f + "(1500~1536)")  # 캡션은 1500 안에서 끝나야 함
chk("V14", "하단 20%(y≥1536)와 그 직전 완충(1500~1536)에 글자·그래픽 없음", not bottom_bad, bottom_bad[:5] or f"{len(files)}장 검사")
# 자막 영역 대비: 캡션 줄(y 1090~1290) 글자색 대비 (밝은 글자 vs 어두운 배경)
bad_c = []
for f in files:
    a = np.asarray(Image.open(os.path.join(tmp, f)).convert("L"), dtype=np.float32)[1090:1290]
    if a.max() < 200 or np.percentile(a, 20) > 60: bad_c.append(f)
chk("V15", "큰 자막 영역에 밝은 글자와 어두운 배경 대비 확보 (밝기 상위≥200, 배경 하위 20%≤60)", not bad_c, bad_c[:5] or "63장 모두 충족")

# 썸네일
im = Image.open(thumb)
chk("V16", "썸네일 1080x1920 PNG", im.size == (1080, 1920) and im.format == "PNG", f"{im.size} {im.format}")
ta = np.asarray(im.convert("L"), dtype=np.int16)
chk("V17", "썸네일 하단 20% 비움", not (ta[1536:] > 70).any())
print(json.dumps(res, ensure_ascii=False, indent=1))
print("TOTAL", len(res), "PASS", sum(r["result"] == "PASS" for r in res), "FAIL", sum(r["result"] == "FAIL" for r in res))
