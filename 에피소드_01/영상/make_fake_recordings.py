#!/usr/bin/env python3
"""시험 도구: 사용자 촬영 파일을 흉내 낸 가짜 촬영 파일을 만든다(실제 사람 영상이 아니다).
 - 소리: 대사를 AI 음성으로 합성하고 0.9배속으로 느리게 만든다(느리게 읽는 사람을 흉내 내 장면이 늘어나는지 확인).
 - 얼굴: 세로 1080x1920 시험용 색상 영상(testsrc2). 위치 정보 메타데이터를 일부러 넣어 제거되는지 확인한다.
사용: python3 -I make_fake_recordings.py <영상폴더> <출력폴더> <A|B>
 A: 01~15 장면별 파일. 05는 오디오만(m4a), 07은 HDR(HLG, HEVC) 10비트, 09는 가로 1920x1080
 B: 전체.mp4(장면 사이 2초 쉬기) + 03.mp4(틀린 장면을 따로 다시 녹음한 교체 파일)
"""
import json, os, subprocess, sys, time, urllib.parse, urllib.request

vdir, out, mode = sys.argv[1:4]
vdir, out = os.path.abspath(vdir), os.path.abspath(out)
EP = json.load(open(os.path.join(vdir, "scenes.json"), encoding="utf-8"))
os.makedirs(out, exist_ok=True); tmp = os.path.join(out, "_tmp"); os.makedirs(tmp, exist_ok=True)
SLOW = 0.9


def sh(*a):
    r = subprocess.run(a, capture_output=True, text=True)
    if r.returncode: print(r.stderr[-1500:]); sys.exit(5)


def tts(i, text):
    p = os.path.join(tmp, f"tts_{i:02d}.mp3")
    if not os.path.exists(p):
        u = "https://translate.googleapis.com/translate_tts?" + urllib.parse.urlencode({"ie": "UTF-8", "client": "gtx", "tl": "ko", "q": text.replace("AI", "에이아이")})
        open(p, "wb").write(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read()); time.sleep(0.3)
    w = os.path.join(tmp, f"slow_{i:02d}.wav")
    sh("ffmpeg", "-v", "error", "-y", "-i", p, "-af", f"atempo={SLOW},aresample=48000", "-ac", "1", w)
    return w


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).decode())


def silence(sec, name):
    p = os.path.join(tmp, name); sh("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=mono", "-t", str(sec), p); return p


def clip(i, wavs, lead, tail, name, kind="h264", size="1080x1920"):
    """대사 wav 앞뒤에 무음을 붙여 한 장면 파일을 만든다."""
    a = os.path.join(tmp, f"aud_{name}.wav")
    lst = os.path.join(tmp, f"lst_{name}.txt")
    open(lst, "w").write("".join(f"file '{p}'\n" for p in [silence(lead, "lead.wav"), wavs, silence(tail, "tail.wav")]))
    sh("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-ar", "48000", "-ac", "1", a)
    d = dur(a); dst = os.path.join(out, name)
    if kind == "audio":
        sh("ffmpeg", "-v", "error", "-y", "-i", a, "-c:a", "aac", dst); return
    vsrc = f"testsrc2=size={size}:rate=30,format=yuv420p"
    meta = ["-metadata", "location=+37.5665+126.9780/", "-metadata", "com.apple.quicktime.location.ISO6709=+37.5665+126.9780/"]
    if kind == "hdr":
        sh("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", vsrc.replace("format=yuv420p", "format=yuv420p10le"), "-i", a, "-t", str(d), "-c:v", "libx265", "-pix_fmt", "yuv420p10le",
           "-color_primaries", "bt2020", "-color_trc", "arib-std-b67", "-colorspace", "bt2020nc", "-tag:v", "hvc1", "-c:a", "aac", *meta, dst)
    else:
        sh("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", vsrc, "-i", a, "-t", str(d), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", *meta, dst)


kinds = {5: "audio", 7: "hdr", 9: "land"}
if mode == "A":
    for sc in EP["scenes"]:
        i = sc["id"]; w = tts(i, sc["narration"]); k = kinds.get(i, "h264")
        clip(i, w, 1.0, 1.0, f"{i:02d}.m4a" if k == "audio" else f"{i:02d}.mp4", kind=k, size="1920x1080" if k == "land" else "1080x1920")
else:
    parts, gap = [], silence(2.0, "gap2.wav")
    lead = silence(1.0, "lead_all.wav"); parts.append(lead)
    for sc in EP["scenes"]:
        parts += [tts(sc["id"], sc["narration"]), gap]
    lst = os.path.join(tmp, "lst_all.txt"); open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    a = os.path.join(tmp, "aud_all.wav"); sh("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-ar", "48000", "-ac", "1", a)
    sh("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30,format=yuv420p", "-i", a, "-t", str(dur(a)), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
       "-metadata", "location=+37.5665+126.9780/", os.path.join(out, "전체.mp4"))
    clip(3, tts(3, EP["scenes"][2]["narration"]), 1.0, 1.0, "03.mp4")   # 틀린 장면을 따로 다시 녹음한 교체 파일
print("OK", mode, sorted(f for f in os.listdir(out) if not f.startswith("_")))
