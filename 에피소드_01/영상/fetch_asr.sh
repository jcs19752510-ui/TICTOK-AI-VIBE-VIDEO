#!/bin/sh
# 한국어 음성 인식(sherpa-onnx, 스트리밍 zipformer 한국어 모델)을 임시 폴더(.harness-tmp/asr)에 설치한다. 저장소에는 커밋하지 않는다(규칙 K).
# 모델은 GitHub 릴리스(k2-fsa/sherpa-onnx, asr-models)에서 받는다(약 418MB). 허깅페이스는 이 환경에서 막혀 있다. 모델 라이선스는 릴리스 페이지에서 확인 필요.
set -e
D="$(dirname "$0")/../../.harness-tmp/asr"; mkdir -p "$D"; cd "$D"
python3 -m venv venv
./venv/bin/pip install -q sherpa-onnx numpy
curl -sS -L -o ko.tar.bz2 "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-korean-2024-06-16.tar.bz2"
tar xjf ko.tar.bz2
echo "설치 완료: $D (실행: $D/venv/bin/python 에피소드_01/영상/asr_run.py <16kHz mono wav> <출력 json>)"
