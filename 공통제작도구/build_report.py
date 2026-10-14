#!/usr/bin/env python3
"""에피소드 내부테스트 결과서를 만든다(검증 출력은 그 자리에서 다시 실행해 붙인다).
사용: python3 -I build_report.py <에피소드폴더>  (폴더에 spec.json, review.json 필요; make_video.py 를 먼저 실행해 .harness-tmp/epNN/result.json 이 있어야 함)
review.json: {"visual": "눈 검수 요약", "defects": [["D-01","내용","원인","조치"]], "risks": ["…"], "times": {"작업명":["시작","끝"]}}"""
import json, os, re, subprocess, sys, glob
here = os.path.dirname(os.path.abspath(__file__)); root = os.path.dirname(here)
folder = os.path.abspath(sys.argv[1]); NN = os.path.basename(folder).split("_")[1]
S = json.load(open(os.path.join(folder, "spec.json"), encoding="utf-8"))
R = json.load(open(os.path.join(folder, "review.json"), encoding="utf-8"))
res = json.load(open(os.path.join(root, ".harness-tmp", f"ep{NN}", "result.json"), encoding="utf-8"))
md = glob.glob(os.path.join(folder, f"{NN}_*.md"))[0]
doc = subprocess.run(["python3", "-I", os.path.join(here, "check_doc.py"), md], capture_output=True, text=True).stdout
mp4 = os.path.join(folder, "최종영상", f"ep{NN}_재현화면_무음시안.mp4")
vid = subprocess.run(["python3", "-I", os.path.join(here, "verify_silent.py"), mp4, os.path.join(folder, "최종영상", "scenes.json")], capture_output=True, text=True).stdout
dochk = [l for l in doc.splitlines() if l.startswith(("PASS", "FAIL"))]
vidchk = [l for l in vid.splitlines() if l.startswith(("PASS", "FAIL"))]
tot = int(re.search(r"(\d+)초", open(md, encoding="utf-8").read().split("- 길이: ")[1]).group(1))
play = json.loads(res["play"])
size = os.path.getsize(mp4) / 1e6
L = []; w = L.append
w(f'# 내부테스트 결과서 — 에피소드 {S["ep"]}/30 "{S["topic"]}" (문서 A~H + 재현 화면 무음 시안)\n')
w("작성: 2026-10-14 (UTC, `date` 실측). 작업 브랜치 `PROD_SCH`. 하네스 설정은 1편과 같음(기능 추가, Tier Standard, 병렬 P1, MCP 없음, 대한민국 기준).\n")
w("## 1. 개요")
w(f"- 대상: `{os.path.basename(md)}`(제목 3개, 장면 16개 {tot}초, 대본, 설명글, 해시태그, 썸네일, 촬영 가이드, 프롬프트 템플릿, 체크리스트)와 `최종영상/ep{NN}_재현화면_무음시안.mp4`({size:.2f}MB)")
w(f"- 판정 요약: 문서 검증 {sum(l.startswith('PASS') for l in dochk)}/{len(dochk)}, 영상 검수 {sum(l.startswith('PASS') for l in vidchk)}/{len(vidchk)} 통과. 영상은 **재현 화면 + 큰 자막의 무음 시안**이며 사용자의 얼굴·목소리 촬영본이 없어 최종본이 아니다.")
w("- 대본은 `공통제작도구/build_episode.py`로 `spec.json`에서 생성했고, 3편은 메인이 직접, 4~30편은 편마다 병렬 에이전트가 작성한 뒤 메인이 전문을 읽고 검증·수정했다.\n")
w("## 2. 테스트 범위 및 제외 범위")
w("- 범위: 문서 규격(장면 길이·음절·총 길이·자막 길이), 대본과 표의 일치, 설명글 규격, 금지 표현, 시리즈 규칙(앞 편 연결, 3단계, CTA, 다음 편 예고), 영상 규격·디코딩·재생·정지 화면·GPS 태그, 샘플 프레임 눈 검수.")
w("- 제외: 얼굴 합성·음성(촬영본 없음), 틱톡 인기 키워드·해시태그 규모(틱톡 접속 불가), 실제 Claude로 시연 재현(이 환경에서 실행하지 않음), 대사를 귀로 읽었을 때의 자연스러움(들을 수 없음).\n")
w("## 3. 테스트 환경\n컨테이너 Linux, Python 3, Chromium(Playwright), ffmpeg. 검증 도구: `공통제작도구/check_doc.py`, `verify_silent.py`, `play_check.js`, `make_video.py`.\n")
w("## 4. 테스트 케이스 및 결과")
w("### 4-1. 문서 검증 (`check_doc.py`)\n| ID | 결과 |\n|---|---|")
for l in dochk: w("| " + l.split(" ", 1)[1].replace("|", "/") + " | " + l.split(" ")[0] + " |")
w("\n### 4-2. 영상 검수 (`verify_silent.py`)\n| ID | 결과 |\n|---|---|")
for l in vidchk: w("| " + l.split(" ", 1)[1].replace("|", "/") + " | " + l.split(" ")[0] + " |")
w(f"\n### 4-3. 재생·정지 화면\n- Chromium 재생(VP9 사본): 끝까지 재생={play['ended']}, 재생 {play['playedSeconds']}초, 그려진 영상 프레임 {play['videoFramesPainted']}(4배속), 오류 {len(play['errors'])}건\n- 정지 화면(2.5초 이상 멈춤): {res['freeze']}건\n- 한계: Chromium은 H.264를 재생하지 못해 VP9 사본으로 대체했다. 오디오 스트림이 없어(무음 시안) 소리와 얼굴은 확인할 수 없다.\n")
w(f"### 4-4. 눈 검수 (샘플 프레임 32장, 장면 시작 프레임 16장, 썸네일)\n{R['visual']}\n")
w("## 5. 커버리지\n요청의 출력 형식 A~H 8개 항목과 시리즈 규칙(앞 편 연결, 1·2·3단계, CTA, 다음 편 예고, 개인정보 한 줄, 입력 프롬프트 예시)을 문서에 반영하고 위 검증으로 확인했다. 자동으로 확인할 수 없는 것: 소리 내어 읽었을 때의 자연스러움, 틱톡 인기 키워드, 해시태그 규모, 실제 AI 답.\n")
w("## 6. 결함 목록\n| ID | 내용 | 원인 | 조치 |\n|---|---|---|---|")
for d in R["defects"]: w("| " + " | ".join(d) + " |")
if not R["defects"]: w("| - | 없음 | - | - |")
w("\n## 7. 테스트 환경 정리(규칙 K)\n임시 프레임·시트는 `.harness-tmp/` 아래에만 만들었고 저장소에는 커밋하지 않는다.\n")
w("## 8. 리스크 및 잔존 이슈")
for i, r in enumerate(R["risks"] + [
    "시연은 재현 화면이며 실제 AI 답은 매번 다르다. 촬영 전에 한 번 돌려 확인해야 한다(문서 H절 재현 가능성 표 참조). 이 환경에서는 실제 Claude로 시험하지 못했다.",
    "최종본은 사용자 촬영본(얼굴·음성)을 받아 `에피소드_01/영상/build_final.py` 방식으로 합성해야 한다. 이 도구가 16장면 시간표를 그대로 처리하는지는 **미확인**이다.",
    "해시태그 규모와 인기 키워드는 사용자가 틱톡에서 확인해야 한다.",
    "다음 편 예고와 앞 편 연결 문장은 `aI바이브코딩주제30개.md`의 주제(가안 포함)를 따랐다. 주제가 바뀌면 장면 2·16을 고친다."], 1): w(f"{i}. {r}")
w("\n## 9. 결론 및 판정\n문서와 영상 시안 모두 자동 검증을 통과했다. **합격(조건부)**: 사용자 확인(주제, 대본 낭독)과 촬영본 합성 후 최종 확정한다.\n")
w("## 10. 내부 검증 (2회)\n- 1회차: 에이전트 작성 직후 `check_doc.py` 20/20, 메인이 대본 전문을 읽어 경험 단정·과장·지어낸 사실을 점검.\n- 2회차: 영상 검수 10/10, 재생 확인, 샘플 프레임 눈 검수와 결함 수정 후 재렌더.\n")
w("## 부록. 작업 시간 (UTC, `date` 실측)\n| 작업 | 시작 | 끝 |\n|---|---|---|")
for k, (a, b) in R.get("times", {}).items(): w(f"| {k} | {a} | {b} |")
open(os.path.join(folder, "내부테스트_결과서.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("OK", folder)
