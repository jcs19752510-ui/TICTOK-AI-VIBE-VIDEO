#!/usr/bin/env python3
"""한국어 음성 인식으로 글자(토큰)별 시각을 뽑는다. fetch_asr.sh로 설치한 .harness-tmp/asr/venv 파이썬으로 실행한다.
사용: .harness-tmp/asr/venv/bin/python asr_run.py <16kHz mono wav> <출력 json>   (ffmpeg -i 영상 -vn -ac 1 -ar 16000 out.wav 로 만든다)
출력 json: {"text", "tokens", "timestamps"}. 소형 모델이라 인식 오류가 있다(대본과 같은 글자를 못 알아듣는 경우). 시각은 말소리 구간과 98% 일치했다(DEC-039).
"""
import json, os, sys, wave
import numpy as np, sherpa_onnx

HERE = os.path.dirname(os.path.abspath(__file__))
M = os.environ.get("ASR_MODEL_DIR", os.path.join(HERE, "..", "..", ".harness-tmp", "asr", "sherpa-onnx-streaming-zipformer-korean-2024-06-16")) + "/"
rec = sherpa_onnx.OnlineRecognizer.from_transducer(tokens=M + "tokens.txt", encoder=M + "encoder-epoch-99-avg-1.int8.onnx", decoder=M + "decoder-epoch-99-avg-1.onnx",
                                                   joiner=M + "joiner-epoch-99-avg-1.int8.onnx", num_threads=4, sample_rate=16000, feature_dim=80, decoding_method="greedy_search")
w = wave.open(sys.argv[1]); a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
s = rec.create_stream(); s.accept_waveform(16000, a); s.accept_waveform(16000, np.zeros(int(0.8 * 16000), dtype=np.float32)); s.input_finished()
while rec.is_ready(s): rec.decode_stream(s)
r = rec.get_result_all(s)
json.dump({"text": r.text, "tokens": list(r.tokens), "timestamps": [float(x) for x in r.timestamps]}, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
print(r.text)
