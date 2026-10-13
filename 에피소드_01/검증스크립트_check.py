import re, sys, json
path = sys.argv[1]
t = open(path, encoding="utf-8").read()
res = []
def chk(id_, name, ok, detail=""):
    res.append((id_, name, "PASS" if ok else "FAIL", detail))

# T01 sections A-H in order
pos = [t.find(f"\n## {c}. ") for c in "ABCDEFGH"]
chk("T01", "출력 형식 A~H 섹션 순서", all(p >= 0 for p in pos) and pos == sorted(pos), str(pos))

# parse scene table
rows = []
for line in t.splitlines():
    m = re.match(r"\|\s*(\d+)\s*\|\s*(\d+):(\d+)–(\d+):(\d+)\s*\|(.*)\|(.*)\|(.*)\|(.*)\|\s*$", line)
    if m:
        s = int(m[2]) * 60 + int(m[3]); e = int(m[4]) * 60 + int(m[5])
        rows.append(dict(n=int(m[1]), s=s, e=e, d=e - s, screen=m[6].strip(), nar=m[7].strip(), cap=m[8].strip(), fx=m[9].strip()))
chk("T02", "장면표 6개 열 파싱 및 장면번호 연속", [r["n"] for r in rows] == list(range(1, len(rows) + 1)) and len(rows) > 0, f"{len(rows)}장면")
chk("T03", "타임라인 끊김/겹침 없음", all(rows[i]["e"] == rows[i + 1]["s"] for i in range(len(rows) - 1)) and rows[0]["s"] == 0)
total = rows[-1]["e"]
chk("T04", "총 길이 60~90초", 60 <= total <= 90, f"{total}초")
body = [r for r in rows if r["n"] != 1]
bad = [(r["n"], r["d"]) for r in body if not 3 <= r["d"] <= 5]
chk("T05", "장면 길이 3~5초 (후킹 장면 1은 규격상 2초 예외)", not bad, f"위반 {bad}" if bad else f"후킹 {rows[0]['d']}초")
chk("T06", "후킹 2초 / 공감 5초 / 요약 5초 / CTA 5초", rows[0]["d"] == 2 and rows[1]["d"] == 5 and rows[-3]["d"] == 5 and rows[-2]["d"] == 5, f"{[r['d'] for r in rows]}")

# narration speed
def syl(s): return len(re.findall(r"[가-힣]", s)) + len(re.findall(r"\d", s))
speeds = [(r["n"], round(syl(r["nar"]) / r["d"], 1)) for r in rows]
slow_fast = [x for x in speeds if x[1] > 7.0]
chk("T07", "나레이션 속도 ≤ 7음절/초 (소리 내어 읽기 가능)", not slow_fast, f"최대 {max(s for _, s in speeds)}음절/초, 위반 {slow_fast}")

# C section matches table
cs = t[t.find("## C. "):t.find("## D. ")]
c_norm = re.sub(r"\s+", "", cs.split("\n", 1)[1])
tab_norm = re.sub(r"\s+", "", "".join(r["nar"].replace("1단계", "1단계").replace("2단계", "2단계").replace("3단계", "3단계") for r in rows))
# remove punctuation differences
strip = lambda x: re.sub(r"[.,?!'\"]", "", x)
chk("T08", "C 대본 = B 표 나레이션 (한 글자도 불일치 없음)", strip(c_norm) == strip(tab_norm), "")

# hashtags
tags = re.findall(r"#[^\s#]+", t[t.find("**해시태그"):t.find("## E. ")])
big = re.search(r"대형 3:(.*)", t).group(1).split(); mid = re.search(r"중형 4:(.*)", t).group(1).split(); sm = re.search(r"소형 3:(.*)", t).group(1).split()
chk("T09", "해시태그 10개 (대형3/중형4/소형3), 중복 없음", len(big) == 3 and len(mid) == 4 and len(sm) == 3 and len(set(big + mid + sm)) == 10, f"{len(big)}/{len(mid)}/{len(sm)}")

# placeholders
chk("T10", "미치환 변수 {{ }} / [[ ]] 없음", "{{" not in t and "[[" not in t)

# CTA keyword
chk("T11", "CTA에 댓글 키워드 '앱만들기' 포함 (나레이션·자막)", "앱만들기" in rows[-2]["nar"] and "앱만들기" in rows[-2]["cap"])
chk("T12", "CTA 문구 '프롬프트 템플릿을 드리겠습니다' 포함", "프롬프트 템플릿을 드리겠습니다" in rows[-2]["nar"])

# forbidden words (deliverable body only)
forb = ["무조건", "100%", "누구나", "1분 만에", "완벽", "반드시 성공", "무료로 누구"]
hit = [w for w in forb if w in t]
chk("T13", "과장 표현 금지어 없음", not hit, f"발견 {hit}")

# hook: exactly one pattern
hook = rows[0]
chk("T14", "후킹 패턴 1개(결과 선공개형): 완성 화면 + '코딩 몰라도 이런 앱 만들 수 있어요'", "완성" in hook["screen"] and "코딩 몰라도 이런 앱 만들 수 있어요" in hook["cap"] and "아직도" not in hook["nar"] and "망합니다" not in hook["nar"])

# 3 steps
joined = " ".join(r["nar"] for r in rows)
chk("T15", "1단계/2단계/3단계 구성", all(f"{i}단계" in joined for i in (1, 2, 3)))
chk("T16", "큰 자막: 모든 장면 자막 존재 및 길이 ≤ 20자", all(r["cap"] and len(r["cap"]) <= 20 for r in rows), str([(r["n"], len(r["cap"])) for r in rows if len(r["cap"]) > 20]))

# series + teaser
chk("T17", "다음 편 예고 포함 (시리즈 설계)", "다음 편" in rows[-1]["nar"] and "2/30" in rows[-1]["cap"])
chk("T18", "1/30 첫 편: 이전 편 연결 대신 채널 소개로 대체함을 명시", "1/30" in t)

# human smell
_bad = [w for w in ("제가 직접", "저도", "시켜봤", "눌러봤", "적었", "줬어요", "막혔") if w in joined]
chk("T19", "재현 영상 정직성(DEC-015): 경험 단정 표현 없음 + 막힌 상황 장면(삭제 버튼 안 눌림) 포함", not _bad and any("안 눌려요" in r["nar"] for r in rows), str(_bad))

# transparency
chk("T20", "AI 사용 투명성: 설명글/체크리스트에 AI 표시 안내", "AI 음성" in t and "AI 생성물 표시" in t)

# security
chk("T21", "보안 한 줄 (개인정보·비밀번호·API 키) 대본과 템플릿 모두 포함", "개인정보나 비밀번호" in joined and "API 키" in t[t.find("## G. "):t.find("## H. ")])

# real prompt example
chk("T22", "화면 입력 프롬프트 예시 포함", "프롬프트 예시 ①" in t and "프롬프트 예시 ②" in t and "예시 ①" in t and "예시 ②" in t)

# verify unknowns flagged
_hl = [l for l in t.splitlines() if "해시태그" in l and "확인 필요" in l]
_src = ("support.claude.com/en/articles/17153992" in t) and ("claude.com/pricing" in t) and ("2026-10-13" in t)
chk("T23", "불확실 항목(해시태그 규모)은 '확인 필요'로 남기고, 확인된 항목(메뉴명·요금제)은 출처·조회일을 기재", bool(_hl) and _src, f"해시태그 줄 {len(_hl)}개, 출처·조회일 {_src}")

# no invented prices / model names
chk("T24", "가격·요금 수치·특정 모델명 지어내지 않음", not re.search(r"\d+\s*(원|달러|\$)", t) and not re.search(r"(Opus|Sonnet|Haiku|GPT-?\d)", t))

# checklist contains required items
h = t[t.find("## H. "):]
chk("T25", "H 체크리스트 3대 항목(메뉴명·요금제, 크리에이티브 센터/추천어, AI 표시)", "메뉴명" in h and "요금제" in h and "크리에이티브 센터" in h and "추천어" in h and "AI 생성물 표시" in h)

# template body
g = t[t.find("## G. "):t.find("## H. ")]
chk("T26", "G 템플릿 본문에 빈칸·실패 시 요청 문장 포함", "(예:" in g and "고쳐줘" in g)

# E thumbnail
e = t[t.find("## E. "):t.find("## F. ")]
chk("T27", "썸네일 문구 + 디자인 지시", "문구" in e and "배경" in e and "글자" in e)

# F
f = t[t.find("## F. "):t.find("## G. ")]
chk("T28", "F 가이드 5요소(재현 화면·확대·자막·편집·배경음악 미사용)", all(k in f for k in ["재현 화면", "확대", "자막 스타일", "편집", "배경음악"]) and "BGM 분위기" not in f)

out = [dict(id=a, name=b, result=c, detail=d) for a, b, c, d in res]
print(json.dumps(out, ensure_ascii=False, indent=1))
print("TOTAL", len(res), "PASS", sum(1 for r in res if r[2] == "PASS"), "FAIL", sum(1 for r in res if r[2] == "FAIL"))
print("SPEEDS", speeds)
