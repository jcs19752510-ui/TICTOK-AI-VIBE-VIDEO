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
chk("V02", "영상 길이가 시간표(scenes.json)와 일치 (±0.1초)", abs(dur - EP["total"]) <= 0.1, f"{dur:.3f}초")
num, den = map(int, v["r_frame_rate"].split("/"))
chk("V03", "프레임레이트 30fps", num / den == 30, v["r_frame_rate"])
nb = int(v.get("nb_frames", 0))
chk("V04", "총 프레임 수가 시간표(scenes.json)와 일치", nb == EP["frames"], nb)
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
if EP.get("voice") == "user":
    # 본인 음성(방 소음이 깔려 있어 쉼이 완전 무음이 아님): 잡음 바닥보다 12dB 큰 구간을 말소리로 본다(합성기와 같은 기준, 20ms 창, 0.25초 미만 틈은 메움)
    import wave
    tmpw = os.path.join(tmp if os.path.isdir(tmp) else "/tmp", "v_audio16k.wav"); os.makedirs(os.path.dirname(tmpw), exist_ok=True)
    subprocess.check_call(["ffmpeg", "-loglevel", "error", "-y", "-i", mp4, "-vn", "-ac", "1", "-ar", "16000", tmpw])
    _w = wave.open(tmpw); _a = np.frombuffer(_w.readframes(_w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    _n = int(16000 * 0.02); _k = len(_a) // _n
    _db = 20 * np.log10(np.sqrt(np.mean(_a[:_k * _n].reshape(_k, _n) ** 2, axis=1)) + 1e-9)
    _thr = max(float(np.percentile(_db, 10)) + 12.0, -50.0)
    _iv = []
    _i = 0
    while _i < _k:
        if _db[_i] > _thr:
            _j = _i
            while _j < _k and _db[_j] > _thr: _j += 1
            if _iv and (_i - _iv[-1][1]) * 0.02 < 0.25: _iv[-1][1] = _j
            else: _iv.append([_i, _j])
            _i = _j
        else: _i += 1
    _iv = [(a * 0.02, b * 0.02) for a, b in _iv if (b - a) * 0.02 >= 0.12]
    speech_starts = [a for a, _ in _iv]
    chk("V20", "음성 시작이 15장면 각각 [장면 시작, 장면 시작+0.9초] 안에 있음(싱크, 본인 음성: 잡음 바닥+12dB 기준)", all(any(sc["start"] <= x <= sc["start"] + 0.9 for x in speech_starts) for sc in EP["scenes"]),
        [(sc["id"], next((round(x, 2) for x in speech_starts if sc["start"] <= x <= sc["start"] + 0.9), None)) for sc in EP["scenes"]])
    last_end = _iv[-1][1] if _iv else 0.0
    chk("V21", "마지막 음성이 영상 끝 0.2초 전에 끝남(잘림 없음, 본인 음성 기준)", bool(_iv) and last_end <= dur - 0.2, f"마지막 음성 끝 {last_end:.2f}s / 영상 {dur:.2f}s, 잡음 바닥+12dB={_thr:.1f}dB")
else:
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


# ---- 얼굴 합성·최종 시간표 검수 (최종 영상에만 해당: scenes.json에 pip·clips가 있을 때) ----
if EP.get("pip"):
    os.makedirs(tmp, exist_ok=True)
    from PIL import Image
    P = EP["pip"]
    chk("V24", "얼굴 위치가 안전 영역 안: 오른쪽 가장자리 x≤930(틱톡 버튼 추정 영역 밖), 아래쪽 y≤1500", P["x"] + P["d"] <= 930 and P["y"] + P["d"] <= 1500, f"x {P['x']}~{P['x'] + P['d']}, y {P['y']}~{P['y'] + P['d']}")
    chk("V25", "총 길이가 규격 60~90초 안", 60 <= EP["total"] <= 90, f"{EP['total']}초")
    bad, seen = [], 0
    for cl in EP.get("clips", []):
        if not cl.get("has_video"): continue
        seen += 1
        tm = (cl["speech_t0"] + cl["speech_t1"]) / 2
        fp = os.path.join(tmp, f"face_{cl['scene']:02d}.png")
        subprocess.check_call(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{tm:.3f}", "-i", mp4, "-frames:v", "1", fp])
        a = np.asarray(Image.open(fp).convert("L"), dtype=np.float32)[P["y"]:P["y"] + P["d"], P["x"]:P["x"] + P["d"]]
        yy, xx = np.mgrid[0:P["d"], 0:P["d"]]; inside = ((xx - P["d"] / 2) ** 2 + (yy - P["d"] / 2) ** 2) <= (P["d"] / 2 - 30) ** 2
        if float(a[inside].std()) < 12: bad.append(cl["scene"])
    chk("V23", "얼굴이 있는 장면마다 말하는 동안 원형 얼굴 영역에 영상이 보임(밝기 분산 ≥12)", not bad and seen > 0, f"얼굴 장면 {seen}개, 이상 {bad}")
    probe_all = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", mp4], capture_output=True, text=True).stdout
    # 태그 이름(location, com.apple.quicktime.location.ISO6709, gps)과 좌표 형식(+37.5665+126.9780/)만 찾는다. chroma_location 같은 색상 정보는 위치정보가 아니다.
    tag_lines = [l for l in probe_all.splitlines() if l.startswith("TAG:")]
    geo = [l for l in tag_lines if re.search(r"location|ISO6709|gps", l, re.I)] + re.findall(r"[+-]\d{1,3}\.\d{2,}[+-]\d{1,3}\.\d{2,}/?", probe_all)
    chk("V26", "위치 정보(GPS 등) 메타데이터가 최종 파일에 없음(태그 이름·좌표 형식 검사)", not geo, f"태그 {len(tag_lines)}개 검사, 발견 {geo[:3]}")

# 자막
caps = [s["caption"] for s in EP["scenes"]]
chk("V10", "화면 자막 모든 장면 존재, 20자 이내", all(c and len(c) <= 20 for c in caps), [len(c) for c in caps])
for name, key in (("ep01_caption.srt", "caption"), ("ep01_narration.srt", "narration")):
    t = open(os.path.join(vdir, name), encoding="utf-8").read()
    blocks = [b for b in t.strip().split("\n\n")]
    ok = len(blocks) == 15
    for b, sc in zip(blocks, EP["scenes"]):
        l = b.split("\n")
        def _ts(x):
            ms = int(round(x * 1000)); h, ms = divmod(ms, 3600000); mi, ms = divmod(ms, 60000); s_, ms = divmod(ms, 1000)
            return f"{h:02d}:{mi:02d}:{s_:02d},{ms:03d}"
        exp = f"{_ts(sc['start'])} --> {_ts(sc['end'])}"
        ok = ok and l[1] == exp and l[2] == sc[key]
    chk("V11" if key == "caption" else "V12", f"{name}: 15개, 시간·문구가 scenes.json과 일치", ok)

# 프레임 샘플 (1초 간격 + 장면 경계 직후): 안전 영역과 대비
os.makedirs(tmp, exist_ok=True)
subprocess.check_call(["ffmpeg", "-loglevel", "error", "-y", "-i", mp4, "-vf", "fps=1", os.path.join(tmp, "v%03d.png")])
files = sorted(f for f in os.listdir(tmp) if f.startswith("v") and f.endswith(".png"))
chk("V13", "1초 간격 샘플 프레임 추출(총 길이 ±1장)", abs(len(files) - EP["total"]) <= 1, f"{len(files)}장 / {EP['total']}초")
bottom_bad, top_bad, lum_min = [], [], 255
for f in files:
    a = np.asarray(Image.open(os.path.join(tmp, f)).convert("L"), dtype=np.int16)
    if (a[1536:] > 70).any(): bottom_bad.append(f)           # 하단 20%: 밝은(글자·그래픽) 픽셀이 없어야 함
    if (a[1500:1536] > 70).any(): bottom_bad.append(f + "(1500~1536)")  # 캡션은 1500 안에서 끝나야 함
chk("V14", "하단 20%(y≥1536)와 그 직전 완충(1500~1536)에 글자·그래픽 없음", not bottom_bad, bottom_bad[:5] or f"{len(files)}장 검사")
# 자막 영역 대비: 장면이 바뀐 직후 0.5초는 자막이 서서히 나타나는 연출 구간이라 제외한다(표본이 우연히 걸려도 결함이 아님)
def _scene_lt(t):
    for sc in EP["scenes"]:
        if sc["start"] <= t < sc["end"]: return t - sc["start"]
    return 99.0
bad_c, skipped = [], 0
for f in files:
    tt = int(f[1:4]) - 0.5   # fps=1 표본의 대략적 시각(번호 n은 n-0.5초 부근)
    if _scene_lt(tt) < 0.5: skipped += 1; continue
    a = np.asarray(Image.open(os.path.join(tmp, f)).convert("L"), dtype=np.float32)[1090:1290]
    if a.max() < 200 or np.percentile(a, 20) > 60: bad_c.append(f)
chk("V15", "큰 자막 영역에 밝은 글자와 어두운 배경 대비 확보 (밝기 상위≥200, 배경 하위 20%≤60; 장면 시작 0.5초 전환 구간 제외)", not bad_c, bad_c[:5] or f"{len(files) - skipped}장 충족, 전환 구간 {skipped}장 제외")

# 썸네일
im = Image.open(thumb)
chk("V16", "썸네일 1080x1920 PNG", im.size == (1080, 1920) and im.format == "PNG", f"{im.size} {im.format}")
ta = np.asarray(im.convert("L"), dtype=np.int16)
chk("V17", "썸네일 하단 20% 비움", not (ta[1536:] > 70).any())
print(json.dumps(res, ensure_ascii=False, indent=1))
print("TOTAL", len(res), "PASS", sum(r["result"] == "PASS" for r in res), "FAIL", sum(r["result"] == "FAIL" for r in res))
