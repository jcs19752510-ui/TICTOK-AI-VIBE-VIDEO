#!/usr/bin/env python3
"""음성(나레이션) 합성: scenes.json의 장면별 나레이션을 TTS로 만들고, 각 장면 시작 시각에 맞춰 63초 트랙 하나로 합친다.
사용: python3 -I make_voice.py <영상폴더> <google|espeak> <작업폴더> <출력.wav>
- google: translate.googleapis.com/translate_tts (비공식 주소, 이용약관 확인 필요 — 결정 기록 DEC-017 참조)
- espeak: espeak-ng(오픈소스, GPL). 한국어 품질은 낮음
각 장면 음성은 장면 시작(+0.15초) 이후, 앞 음성이 끝난 뒤에 시작한다. 장면 끝을 SPILL(0.6초)까지 넘길 수 있고, 기본 1.12배속으로 말하고, 그래도 부족하면 atempo로 더 빠르게 맞추며(최대 1.35배) 그래도 넘으면 실패로 처리한다.
"""
import json, os, subprocess, sys, time, urllib.parse, urllib.request

vdir, engine, work, out = sys.argv[1:5]
EP = json.load(open(os.path.join(vdir, "scenes.json"), encoding="utf-8"))
os.makedirs(work, exist_ok=True)
LEAD, GAP, SPILL, BASE, MAXTEMPO = 0.15, 0.12, 0.6, 1.12, 1.35


def speak_text(s):  # 발음 보정: 영문 약어를 한국어 발음으로
    return s.replace("AI", "에이아이").replace("API", "에이피아이")


def dur(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).decode())


clips, cursor = [], 0.0
for sc in EP["scenes"]:
    txt = speak_text(sc["narration"])
    base = os.path.join(work, f"s{sc['id']:02d}")
    if engine == "google":
        url = "https://translate.googleapis.com/translate_tts?" + urllib.parse.urlencode({"ie": "UTF-8", "client": "gtx", "tl": "ko", "q": txt})
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        path = base + ".mp3"
        for attempt in range(3):
            try:
                open(path, "wb").write(urllib.request.urlopen(req, timeout=30).read()); break
            except Exception as e:
                if attempt == 2: raise
                time.sleep(1.5)
        time.sleep(0.3)
    else:
        path = base + ".wav"
        subprocess.check_call(["espeak-ng", "-v", "ko", "-s", "150", "-w", path, txt])
    d = dur(path)
    begin = max(sc["start"] + LEAD, cursor)
    room = sc["end"] + SPILL - begin
    tempo = max(BASE, d / room)
    if tempo > MAXTEMPO:
        print(f"FAIL scene {sc['id']}: 음성 {d:.2f}s, 가능 {room:.2f}s x{MAXTEMPO}"); sys.exit(2)
    end = begin + d / tempo
    if end > EP["total"] - 0.2:
        print(f"FAIL scene {sc['id']}: 음성이 영상 끝({EP['total']}s) 0.2초 전까지 끝나지 않음: {end:.2f}s"); sys.exit(2)
    cursor = end + GAP
    clips.append((sc, path, d, tempo, begin, end))

args, filt, mix = ["ffmpeg", "-loglevel", "error", "-y"], [], []
for i, (sc, path, d, tempo, begin, end) in enumerate(clips):
    args += ["-i", path]
    ms = int(begin * 1000)
    filt.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=mono,atempo={tempo:.4f},adelay={ms}:all=1[a{i}]")
    mix.append(f"[a{i}]")
filt.append("".join(mix) + f"amix=inputs={len(clips)}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,apad=whole_dur={EP['total']},atrim=0:{EP['total']}[o]")
subprocess.check_call(args + ["-filter_complex", ";".join(filt), "-map", "[o]", "-ar", "48000", "-ac", "1", out])
# 2차 처리: 끝에 무음을 채워 정확히 total초로 맞춘다(loudnorm 뒤 길이 오차 보정)
_tmp = out + ".pad.wav"
subprocess.check_call(["ffmpeg", "-loglevel", "error", "-y", "-i", out, "-af", f"apad=whole_dur={EP['total']}", "-t", str(EP["total"]), _tmp])
os.replace(_tmp, out)
print("OK", engine, "total", f"{dur(out):.2f}s")
for sc, path, d, tempo, begin, end in clips:
    print(f"scene {sc['id']:2d} 장면 {sc['start']:2d}~{sc['end']:2d}s  음성 {begin:5.2f}~{end:5.2f}s  속도 x{tempo:.2f}  장면 끝 초과 {max(0, end - sc['end']):.2f}s")
