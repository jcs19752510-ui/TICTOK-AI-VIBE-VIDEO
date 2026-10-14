#!/usr/bin/env python3
"""에피소드 데이터(spec.json)에서 A~H 문서, 장면 시간표(scenes.json/js), 자막 SRT를 만든다.
사용: python3 -I build_episode.py <에피소드폴더>   (폴더 안에 spec.json 필요)
출력: <폴더>/<NN>_<slug>.md, <폴더>/영상/scenes.json, scenes.js, epNN_caption.srt, epNN_narration.srt
규칙 검사(음절 수, 장면 수, 설명글 글자 수 등)는 같은 폴더의 검증스크립트가 아니라 공통제작도구/check_doc.py 가 한다."""
import json, os, re, sys

folder = sys.argv[1]
S = json.load(open(os.path.join(folder, "spec.json"), encoding="utf-8"))
EPN = S["ep"]; NN = f"{EPN:02d}"
sc = S["scenes"]
assert len(sc) == 16, f"장면 16개 아님: {len(sc)}"
syl = lambda s: len(re.findall("[가-힣0-9]", s))
mmss = lambda t: f"{t // 60}:{t % 60:02d}"
t = 0; rows = []
for i, s in enumerate(sc, 1):
    s["id"] = i; s["start"] = t; t += s["d"]; s["end"] = t; s["duration"] = s["d"]
    s["syl"] = syl(s["narr"]); s["max"] = int(s["d"] * 5.5)
total = t

L = []
w = L.append
w(f"# 에피소드 {EPN}/30 — {S['topic']}\n")
w("- 채널: AI바이브생활팁 (@ai_vibe_life_tip)")
w(f"- 후킹 패턴: **{S['pattern']}** ({S['pattern_note']})")
w(f"- 댓글 키워드: **{S['keyword']}**")
w("- 이번 주 인기 키워드·사운드: 없음 (사용자 확인 없음. 트렌드를 지어내지 않음. H 체크리스트에서 확인)")
w(f"- 데모: {S['demo']}")
w("- 제작 방식: 목업 애니메이션(재현 화면) + 큰 자막 + **사용자가 직접 촬영한 얼굴(오른쪽 아래 원형)과 본인 목소리**. AI 음성 없음. 영상 우상단 \"재현 화면\" 배지는 쓰지 않고(사용자 지시, DEC-041) 설명글에 재현 화면임을 밝힌다.")
w(f"- 길이: {total}초 (60~90초 규격 안), 9:16, 장면 16개")
w("- 작성일: 2026-10-14. **상태: 초안. 사용자 확인 전** (주제 위치는 `시리즈기획/시리즈_30편_기획.md`)\n\n---\n")
w("## A. 제목 후보 3개\n")
for i, x in enumerate(S["titles"], 1):
    w(f"{i}. {x['t']}\n   - 검색 키워드: {x['kw']}")
w(f"\n선택 이유: {S['title_why']}\n")
w("## B. 장면별 표\n")
w("대사 음절 수는 한글 글자와 숫자 개수이고, 기준은 \"장면 길이(초) × 5.5\"이다. 효과음은 쓰지 않는다.\n")
w("| 장면 | 시간 | 화면에 보일 것 | 나레이션 | 음절 | 화면 자막 | 효과·전환 |\n|---|---|---|---|---|---|---|")
for s in sc:
    w(f"| {s['id']} | {mmss(s['start'])}–{mmss(s['end'])} | {s['screen']} | {s['narr']} | {s['syl']}/{s['max']} | {s['cap']} | {s['fx']} |")
w("\n**화면에 보여줄 실제 입력 프롬프트 예시** (재현 화면에 그대로 타이핑하는 문장)\n")
circ = "①②③④"
for i, p in enumerate(S["prompts"]):
    w(f"- 예시 {circ[i]} (장면 {p['scene']}, {p['step']}): `{p['text']}`")
w(f"\n**3단계 구성 점검**: {S['steps_note']}\n")
w("## C. 전체 나레이션 대본\n")
w("소리 내어 읽는 대로 적었다. **장면 사이에 2초씩 쉬고 읽어 주세요.**\n")
for s in sc:
    n = s["narr"]; w(f"{s['id']}. {n if n[-1] in '.?' else n + '.'}")
w("\n## D. 설명글 + 해시태그\n")
desc = S["desc"].rstrip() + "\n\n" if False else S["desc"].strip() + " " + S["repro_note"].strip()
w("**설명글** (500자 이내)\n"); w(desc + "\n")
h = S["hashtags"]
w("**해시태그 10개** (분류는 추정이며 틱톡 검색창에서 확인 필요. 이 환경에서 틱톡에 접속할 수 없어 조회수를 확인하지 못했다)\n")
w("- 대형 3: " + " ".join(h["large"])); w("- 중형 4: " + " ".join(h["mid"])); w("- 소형 3: " + " ".join(h["small"]))
w("\n## E. 썸네일 문구 + 디자인 지시\n")
T = S["thumb"]
w(f"- 문구: **{T['l1']} {T['l2']}** (작은 글씨: {EPN}/30). 5어절 이내, 결과가 한눈에 보이는 문구.")
w(f"- 배경: {T['bg']}")
w("- 글자: 굵은 고딕, 흰 글자에 진한 테두리, 화면 위쪽 1/3에 배치. 포인트색은 민트(#0b8a80 계열) 하나.")
w("- 틱톡 하단 UI와 오른쪽 버튼 영역(x 930 이후)을 피해 아래 20%와 오른쪽 가장자리를 비운다.")
w("- 이전 편과 같은 배치(문구 위, 화면 아래)를 유지해 시리즈로 보이게 한다.")
w("- **문구는 실제 영상 내용과 맞아야 한다.** " + T["match"] + "\n")
w("## F. 촬영·편집 가이드\n")
w(f"- **재현 화면 구간**: 장면 {S['mock_scenes']}은 화면 녹화가 아니라 `공통제작도구/player.html`로 그린 목업이다. 영상 우상단 \"재현 화면\" 배지는 쓰지 않는다. 설명글(D) 마지막 줄로 표기한다.")
w(f"- **확대할 부분**: {S['zoom']}")
w("- **자막 스타일**: 한 화면 두 줄 이내, 굵은 고딕, 핵심 단어만 민트색. 모든 나레이션을 자막화한다. 자막 폭 590px, 오른쪽 옆에 얼굴 원(지름 270px)을 둔다.")
w("- **편집 속도**: 장면 2~5초, 컷 전환 빠르게. 1·2·3단계는 큰 숫자 슬라이드로 구분한다.")
w("- **음성·소리**: 사용자 본인 목소리. 배경음악 없음. 효과음 없음. 말 속도는 임의로 바꾸지 않고, 말이 길면 그 장면 시간을 늘린다(총 60~90초 확인).")
w("- **녹음 팁(1편 경험 반영, DEC-037·042)**: ① 장면 사이 2초 쉬기 ② 마이크 또는 이어폰 마이크를 입에 가깝게 ③ 방 소음(에어컨, 냉장고)을 끄기 ④ 틀리면 파일 안에서 다시 읽지 말고 그 장면만 따로 녹음.")
w("- **얼굴 촬영 시 주의점**: 폰 세로 촬영, 얼굴을 화면 위쪽 1/3에 두면 원 안에서 잘림이 적다. 촬영 설정에서 위치 정보(GPS)를 끈다. 배경에 우편물·간판·가족 얼굴·명찰이 보이지 않게 한다. 의상의 글자가 보이면 공개 영상이므로 확인한다.")
for x in S.get("filming_extra", []): w("- " + x)
w("\n## G. 댓글 유도용 프롬프트 템플릿 본문\n")
w("```"); w("\n".join(S["template"]).rstrip()); w("```\n")
w("## H. 제작 전 확인 체크리스트\n")
w("- [ ] **Claude 메뉴명·요금제·기능**: 이번 영상 대사와 자막에는 특정 메뉴명·요금제를 쓰지 않았다(\"AI 대화창\"으로만 표현). 1편에서 2026-10-13에 공식 도움말(support.claude.com/ko/articles/17153992)과 가격 페이지(claude.com/pricing)로 확인한 내용이 있으나 **이번 편에서는 다시 조회하지 않았다**(대사에 쓰지 않아 영향 없음). 화면에 실제 Claude 화면을 쓰게 되면 그날 다시 확인한다.")
w("- [ ] **틱톡 크리에이티브 센터·검색창 추천어**에서 오늘 인기 키워드·사운드 확인 (이 환경에서 접속 불가)")
w("- [ ] **해시태그 분류**(대형/중형/소형)를 틱톡 검색창에서 확인")
w("- [x] **AI 생성물 표시**: AI 음성은 쓰지 않는다(본인 목소리). 재현 화면은 설명글 마지막 줄에 표기했다. 틱톡 앱의 \"AI 생성 콘텐츠\" 라벨 설정은 업로드할 때 사용자가 확인한다(**확인 필요**).")
w("- [x] **이전 편과 겹치는 표현 점검**: " + S["overlap"])
w("- [x] **경험 단정 표현 점검**: \"제가 직접\", \"저도\", \"해봤더니\", \"헤맸\" 등이 대사·자막·설명글에 없다(자동 검증).")
w("- [x] **과장 표현 점검**: \"무조건\", \"100%\", \"누구나\", \"1분\", \"클릭 한 번\" 없음(자동 검증).")
w("- [x] **개인정보·키**: " + S["privacy"])
w("- [ ] **시연 재현 가능성 점검** (같은 시연을 영상에서 실제로 재현할 수 있는지)\n")
w("  | 시연 | 재현 방법 | 점검 결과 |\n  |---|---|---|")
for r in S["repro"]: w(f"  | {r[0]} | {r[1]} | {r[2]} |")
w("\n- [x] **대사 문체**: \"~됩니다/~합니다/~보겠습니다\" 중심. \"~해요/~줘요/~볼게요\" 반복 없음(자동 검증). 소리 내어 읽어 보고 어색하면 알려 달라(귀로 확인할 수 없다).")
w("- [ ] 댓글 템플릿 전달은 사용자가 직접 처리 (본문은 G)")

md = os.path.join(folder, f"{NN}_{S['slug']}.md")
open(md, "w", encoding="utf-8").write("\n".join(L) + "\n")
out = os.path.join(folder, "영상"); os.makedirs(out, exist_ok=True)
data = dict(width=1080, height=1920, fps=30, total=total, frames=total * 30, series=f"{EPN}/30", channel="AI바이브생활팁",
            handle="@ai_vibe_life_tip", voice="user", mock_badge=False, thumb=dict(l1=S["thumb"]["l1"], l2=S["thumb"]["l2"], v=S["thumb"].get("v")),
            scenes=[dict(id=s["id"], start=s["start"], end=s["end"], duration=s["d"], screen=s["screen"], narration=s["narr"], caption=s["cap"], fx=s["fx"], v=s["v"]) for s in sc])
json.dump(data, open(os.path.join(out, "scenes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(os.path.join(out, "scenes.js"), "w", encoding="utf-8").write("window.EP = " + json.dumps(data, ensure_ascii=False) + ";\n")
ts = lambda x: f"00:{x // 60:02d}:{x % 60:02d},000"
for name, key in ((f"ep{NN}_caption.srt", "cap"), (f"ep{NN}_narration.srt", "narr")):
    with open(os.path.join(out, name), "w", encoding="utf-8") as f:
        for s in sc: f.write(f"{s['id']}\n{ts(s['start'])} --> {ts(s['end'])}\n{s[key]}\n\n")
print("OK", md, total, "초")
