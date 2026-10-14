#!/usr/bin/env python3
"""합성한 영상의 소리를 Whisper(한국어)로 장면마다 인식해, 그 장면의 대본과 가장 닮았는지(이웃 장면 대본보다) 확인한다. (DEC-055)
사용: <fetch_asr.sh로 만든 venv>/python verify_speech.py <epNN.mp4> <scenes_final.json> <whisper 폴더(small-*.onnx가 있는 곳)> <출력 json>
 - 장면 구간은 scenes_final.json의 clips(speech_t0~speech_t1) 기준. 장면마다 대본 일치율(자기)과 이웃 두 장면 중 큰 값(이웃)을 낸다. 자기 < 이웃인 장면이 있으면 소리와 자막이 어긋난 것이다.
 - Whisper도 일부 음절을 놓친다. 일치율은 0.7~1.0이 보통이며 절대값보다 "자기 > 이웃"을 본다.
"""
import difflib, json, re, subprocess, sys, tempfile, os, wave
import numpy as np, sherpa_onnx as s

mp4, sj, wdir, outp = sys.argv[1:5]
d = json.load(open(sj, encoding="utf-8")); sc = d["scenes"]; cl = d["clips"]
wav = os.path.join(tempfile.mkdtemp(), "a.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-vn", "-ac", "1", "-ar", "16000", wav], check=True)
w = wave.open(wav); a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
size = "small" if os.path.exists(os.path.join(wdir, "small-encoder.int8.onnx")) else "base"
rec = s.OfflineRecognizer.from_whisper(encoder=os.path.join(wdir, f"{size}-encoder.int8.onnx"), decoder=os.path.join(wdir, f"{size}-decoder.int8.onnx"), tokens=os.path.join(wdir, f"{size}-tokens.txt"), language="ko", task="transcribe", num_threads=4)
norm = lambda x: re.sub(r"[^가-힣0-9A-Za-z]", "", x)
heard = []
for c in cl:
    x = a[int(max(0, c["speech_t0"] - 0.4) * 16000):int((c["speech_t1"] + 0.4) * 16000)] * 0.35   # 음량을 낮춰 인식기 입력 범위에 맞춤
    st = rec.create_stream(); st.accept_waveform(16000, x); rec.decode_stream(st); heard.append(st.result.text.strip())
rows = []
for i, (c, t) in enumerate(zip(cl, heard)):
    r = lambda j: difflib.SequenceMatcher(None, norm(sc[j]["narration"]), norm(t)).ratio() if 0 <= j < len(sc) else 0.0
    rows.append(dict(scene=c["scene"], own=round(r(i), 2), neighbor=round(max(r(i - 1), r(i + 1)), 2), heard=t, script=sc[i]["narration"]))
json.dump(rows, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
bad = [r["scene"] for r in rows if r["own"] < r["neighbor"]]
print(f"모델 {size} | 장면 {len(rows)}개 | 평균 자기 일치 {np.mean([r['own'] for r in rows]):.2f} | 자기<이웃 장면: {bad or '없음'}")
