#!/bin/sh
# 렌더링용 폰트(Noto Sans KR 500·900)를 임시 폴더로 내려받는다. 저장소에는 커밋하지 않는다(.harness-tmp/ 는 .gitignore 처리).
# 라이선스: SIL OFL 1.1로 알려져 있으나 https://fonts.google.com/noto/specimen/Noto+Sans+KR 에서 재확인할 것.
set -e
D="$(dirname "$0")/../../.harness-tmp/fonts"; mkdir -p "$D"
curl -sS -o "$D/NotoSansKR-500.woff" 'https://fonts.gstatic.com/s/notosanskr/v40/PbyxFmXiEBPT4ITbgNA5Cgms3VYcOA-vvnIzztgyeLc.woff'
curl -sS -o "$D/NotoSansKR-900.woff" 'https://fonts.gstatic.com/s/notosanskr/v40/PbyxFmXiEBPT4ITbgNA5Cgms3VYcOA-vvnIzzkM1eLc.woff'
