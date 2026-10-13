#!/bin/sh
# 노이즈 제거 모델(DPDFNet2 48kHz, 약 10MB)을 임시 폴더(.harness-tmp/dn)에 받는다. 먼저 fetch_asr.sh로 sherpa-onnx를 설치해야 한다. 저장소에는 커밋하지 않는다(규칙 K).
# 모델은 GitHub 릴리스(k2-fsa/sherpa-onnx, speech-enhancement-models)에서 받는다. 모델 라이선스는 릴리스 페이지에서 확인 필요.
set -e
D="$(dirname "$0")/../../.harness-tmp/dn"; mkdir -p "$D"
curl -sS -L -o "$D/dpdfnet2_48khz_hr.onnx" "https://github.com/k2-fsa/sherpa-onnx/releases/download/speech-enhancement-models/dpdfnet2_48khz_hr.onnx"
echo "설치 완료: $D/dpdfnet2_48khz_hr.onnx"
