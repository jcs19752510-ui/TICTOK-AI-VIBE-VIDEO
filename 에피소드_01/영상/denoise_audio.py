#!/usr/bin/env python3
"""마이크 없이 녹음한 소리의 노이즈를 줄인다(말소리는 보존). (DEC-042)
사용: .harness-tmp/asr/venv/bin/python denoise_audio.py <입력 wav(48kHz mono)> <출력 wav> [모델 onnx] [WET 0~1]
 모델: DPDFNet2 48kHz (sherpa-onnx 릴리스 speech-enhancement-models, fetch_denoise.sh로 받는다)

처리(말하는 구간과 쉬는 구간을 따로 다룬다)
 1) 딥러닝 잡음 제거(DPDFNet2, 48kHz 전대역)로 깨끗한 소리 W를 만든다.
 2) 말소리 구간(잡음 바닥+12dB, 앞 0.08초·뒤 0.18초 여유, 0.25초 미만 틈은 메움)을 찾아 부드러운 마스크 m(0~1, 40ms 전환)을 만든다.
    (여유를 길게(0.15/0.30) 하면 말 앞뒤 노이즈가 덜 지워지고, 너무 짧으면 말 시작·끝이 깎인다. 시험: 0.08/0.18초가 노이즈 감소 8.3dB, 음성 인식 일치율 0.726(원본 0.775)으로 가장 균형이 좋았다)
 3) 말하는 구간: WET*W + (1-WET)*원본  (기본 WET=0.70, 딥러닝이 자음을 깎는 부작용을 원본으로 보완. 값이 클수록 노이즈는 더 줄고 말소리 변형 위험이 커진다)
    쉬는 구간: PAUSE_KEEP*원본  (PAUSE_KEEP=0.08=-22dB, 노이즈를 강하게 줄이되 완전한 무음(어색함)은 피한다)
    결과 = m*말하는구간 + (1-m)*쉬는구간
"""
import os, sys, wave
import numpy as np

WET, PAUSE_KEEP, PRE, POST, XFADE = 0.70, 0.08, 0.08, 0.18, 0.04
WET, PAUSE_KEEP, PRE, POST, XFADE = [float(os.environ.get(k, v)) for k, v in (('DN_WET', WET), ('DN_KEEP', PAUSE_KEEP), ('DN_PRE', PRE), ('DN_POST', POST), ('DN_XFADE', XFADE))]   # 시험용 조정(환경 변수)
inp, outp = sys.argv[1], sys.argv[2]
if len(sys.argv) > 4: WET = float(sys.argv[4])
model = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".harness-tmp", "dn", "dpdfnet2_48khz_hr.onnx")
import sherpa_onnx as s

w = wave.open(inp); sr = w.getframerate()
x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
if sr != 48000: sys.exit(f"FAIL: 입력은 48kHz여야 합니다({sr}).")
mc = s.OfflineSpeechDenoiserModelConfig(num_threads=4)
mc.dpdfnet = s.OfflineSpeechDenoiserDpdfNetModelConfig(model=model)
r = s.OfflineSpeechDenoiser(s.OfflineSpeechDenoiserConfig(model=mc))(x, sr)
if r.sample_rate != 48000: sys.exit(f"FAIL: 모델 출력이 48kHz가 아닙니다({r.sample_rate}). 48kHz 모델을 쓰세요.")
W = np.asarray(r.samples, dtype=np.float32)
n = min(len(x), len(W)); x, W = x[:n], W[:n]

win = int(sr * 0.02); k = n // win
db = 20 * np.log10(np.sqrt(np.mean(x[:k * win].reshape(k, win) ** 2, axis=1)) + 1e-9)
thr = max(float(np.percentile(db, 10)) + 12.0, -50.0)
iv, i = [], 0
while i < k:
    if db[i] > thr:
        j = i
        while j < k and db[j] > thr: j += 1
        if iv and (i - iv[-1][1]) * 0.02 < 0.25: iv[-1][1] = j
        else: iv.append([i, j])
        i = j
    else: i += 1
m = np.zeros(n, dtype=np.float32)
for a, b in iv:
    if (b - a) * 0.02 < 0.12: continue
    m[max(0, int((a * 0.02 - PRE) * sr)):min(n, int((b * 0.02 + POST) * sr))] = 1.0
kern = np.hanning(int(sr * XFADE) * 2 + 1).astype(np.float32); kern /= kern.sum()
m = np.clip(np.convolve(m, kern, mode="same"), 0, 1)
y = m * (WET * W + (1 - WET) * x) + (1 - m) * (PAUSE_KEEP * x)
o = wave.open(outp, "wb"); o.setnchannels(1); o.setsampwidth(2); o.setframerate(sr)
o.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes()); o.close()
print(f"완료: 말하는 구간 {sum((b - a) * 0.02 for a, b in iv):.1f}초 / 전체 {n / sr:.1f}초, 잡음 바닥 기준 {thr:.1f}dB")
