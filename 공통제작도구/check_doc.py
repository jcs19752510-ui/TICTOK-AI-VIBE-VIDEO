#!/usr/bin/env python3
"""에피소드 문서(A~H) 자동 검증. 사용: python3 -I check_doc.py <에피소드.md>  (실패가 있으면 종료코드 1)"""
import re, sys
t = open(sys.argv[1], encoding="utf-8").read()
res = []
def chk(n, ok, msg): res.append((n, ok, msg)); print(("PASS" if ok else "FAIL"), n, msg)
sec = lambda s: int(s.split(":")[0]) * 60 + int(s.split(":")[1])
epn = int(re.search(r"# 에피소드 (\d+)/30", t).group(1))
kw = re.search(r"댓글 키워드: \*\*(.+?)\*\*", t).group(1)
rows = [[x.strip() for x in r.strip("|").split("|")] for r in t.split("\n") if re.match(r"\| \d+ \| \d:\d\d", r)]
chk("T01", len(rows) == 16, f"장면 {len(rows)}개")
prev = 0; bad = []
for c in rows:
    a, b = c[1].replace("–", "-").split("-"); d = sec(b) - sec(a)
    n = len(re.findall("[가-힣0-9]", c[3]))
    if sec(a) != prev or not 2 <= d <= 5 or n > d * 5.5 or c[4] != f"{n}/{int(d * 5.5)}": bad.append((c[0], d, n, c[4]))
    prev = sec(b)
chk("T02", not bad, f"장면 연속·길이 2~5초·음절 ≤ 초×5.5·표기 일치, 위반 {bad}")
chk("T03", 60 <= prev <= 90, f"총 길이 {prev}초")
longcap = [c[0] for c in rows if len(c[5]) > 22]
chk("T04", not longcap, f"화면 자막 22자 이내(2줄), 초과 장면 {longcap}")
cs = re.search(r"## C\..*?\n\n(.*?)\n## D", t, re.S).group(1)
cl = [re.sub(r"^\d+\. ", "", x) for x in cs.split("\n") if re.match(r"\d+\. ", x)]
bn = [c[3] if c[3][-1] in "?." else c[3] + "." for c in rows]
chk("T05", cl == bn, "C 대본과 B 나레이션 일치")
d = re.search(r"\*\*설명글\*\*.*?\n\n(.*?)\n\n\*\*해시", t, re.S).group(1)
chk("T06", len(d) <= 500, f"설명글 {len(d)}자")
chk("T07", "?" in d[:60] or d.split(".")[0].endswith("?"), "설명글 첫 줄 질문·반전")
chk("T08", d.strip().endswith("재현 화면입니다."), "설명글 끝에 재현 화면 표기")
tags = re.findall(r"#\S+", t.split("**해시태그")[1].split("## E")[0])
chk("T09", len(tags) == 10 and len(set(tags)) == 10, f"해시태그 {len(tags)}개(중복 없음)")
body = t.split("## H.")[0]
vid = "\n".join(c[3] + " " + c[5] for c in rows) + "\n" + cs + "\n" + d  # 영상·설명글에 실제로 나가는 문장
bans = ["제가 직접", "저도", "해봤", "해 봤", "헤맸", "무조건", "100%", "누구나", "1분 만에", "클릭 한 번", "구독자", "조회수"]
hit = {w: vid.count(w) for w in bans if vid.count(w)}
chk("T10", not hit, f"금지 표현 0건 {hit}")
chk("T11", not re.search("해요|줘요|볼게요", cs), "C 대본에 ~해요/~줘요/~볼게요 없음")
chk("T12", len(re.findall(r"^- 예시 [①②③④]", t, re.M)) >= 2, "입력 프롬프트 예시 2개 이상")
chk("T13", all(f"{k}단계" in cs for k in "123"), "대본에 1·2·3단계")
chk("T14", kw in cs and "프롬프트 템플릿을 드리겠습니다" in cs and kw in rows[14][3], f"댓글 CTA('{kw}')가 장면 15")
chk("T15", "다음 편" in rows[15][3] or f"{epn + 1}편" in rows[15][3], f"장면 16 다음 편({epn + 1}편) 예고")
chk("T16", "편" in rows[1][3], "장면 2에 앞 편 연결 문장")
chk("T17", "AI 음성" not in re.sub(r"AI 음성 ?(은|없)[^\n]*", "", body), "본문에 AI 음성 사용 표기 없음")
chk("T18", "```" in t.split("## G.")[1].split("## H.")[0], "G 템플릿 본문 있음")
chk("T19", not re.search(r"sk-[A-Za-z0-9]{10,}|[\w.]+@[\w.]+\.\w+|\d{2,3}-\d{3,4}-\d{4}", t), "키·이메일·전화번호 패턴 없음")
chk("T20", any("개인정보" in c[3] or "비밀번호" in c[3] for c in rows), "개인정보·비밀번호 주의 한 줄(대사)")
print(f"\n{sum(o for _, o, _ in res)}/{len(res)} 통과"); sys.exit(0 if all(o for _, o, _ in res) else 1)
