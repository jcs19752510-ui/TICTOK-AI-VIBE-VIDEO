#!/usr/bin/env python3
"""에피소드 5 문구 문서(`05_문구_20년차기준.md`)를 생성 코드와 별개로 읽어서 규칙을 점검한다. 사용: python3 -I 에피소드_05/문구_검증.py [<문구 md> <녹음_대사만.md>] (인자 없으면 이 파일 옆의 기본 파일, 설명글 최종본도 함께 대조)"""
import json, os, re, sys
D = os.path.dirname(os.path.abspath(__file__))
P1 = sys.argv[1] if len(sys.argv) > 2 else os.path.join(D, "05_문구_20년차기준.md"); P2 = sys.argv[2] if len(sys.argv) > 2 else os.path.join(D, "녹음_대사만.md")
t = open(P1, encoding="utf-8").read(); rec = open(P2, encoding="utf-8").read()
res = []
def chk(i, name, ok, detail=""): res.append(dict(id=i, name=name, result="PASS" if ok else "FAIL", detail=str(detail)))
rows = lambda pre: [l.strip().strip("|").split("|") for l in t.splitlines() if re.match(rf"\|\s*{pre}\d+\s*\|", l)]
titles = [(r[0].strip(), r[1].strip()) for r in rows("T")]
desc = re.search(r"```설명글\n(.*?)\n```", t, re.S).group(1)
hooks = [(r[0].strip(), r[1].strip(), r[2].strip()) for r in rows("H")]
thumbs = [(r[0].strip(), r[1].strip()) for r in rows("B")]
tags_block = {r[0].strip(): re.findall(r"#\S+", r[1]) for r in [l.strip().strip("|").split("|") for l in t.splitlines() if re.match(r"\|\s*(대형|중형|소형)\s*\|", l)]}
pri = re.findall(r"#\S+", re.search(r"우선 5개:(.*)", t).group(1))
alltags = [x for v in tags_block.values() for x in v]
KW = ("앱", "꾸미", "코딩", "바이브")
chk("C01", "제목 5개, 각 40자 이하", len(titles) == 5 and all(len(x) <= 40 for _, x in titles), [(i, len(x)) for i, x in titles])
chk("C02", "제목마다 핵심 키워드(앱·꾸미·코딩·바이브)가 앞 20자 안에 있음", all(any(k in x[:20] for k in KW) for _, x in titles), [i for i, x in titles if not any(k in x[:20] for k in KW)] or "모두 포함")
chk("C03", "설명글 전체 2,200자 이내(안전 한도), 목표 600자 이내", len(desc) <= 2200 and len(desc) <= 600, f"{len(desc)}자")
first = desc.splitlines()[0]
chk("C04", "설명글 첫 줄이 제목 T1과 같고(+시리즈 표기), 앞 100자 안에 핵심 키워드 2개 이상", first.startswith(titles[0][1]) and sum(k in desc[:100] for k in KW) >= 2, f"첫 줄 {len(first)}자")
need = {"CTA 키워드 '앱꾸미기'(따옴표 포함, 해시태그와 구분)": "'앱꾸미기'" in desc and "댓글에" in desc, "프롬프트 템플릿": "프롬프트 템플릿" in desc, "개인정보·비밀번호 안전 문구": "개인정보" in desc and "비밀번호" in desc, "재현 화면 표기": "재현 화면" in desc, "AI 음성 미사용 표기": "AI 음성" in desc, "다음 편 예고": "다음 편" in desc, "3단계 구성": all(f"{n}단계" in desc for n in (1, 2, 3))}
chk("C05", "설명글 필수 요소(CTA·템플릿·안전·재현 화면·AI 음성 표기·예고·3단계)", all(need.values()), [k for k, v in need.items() if not v] or "모두 포함")
chk("C06", "해시태그 10개(대형3/중형4/소형3), 중복 없음", [len(tags_block.get(k, [])) for k in ("대형", "중형", "소형")] == [3, 4, 3] and len(set(alltags)) == 10, {k: len(v) for k, v in tags_block.items()})
dtags = re.findall(r"#\S+", desc.splitlines()[-1])
chk("C07", "우선 5개가 10개의 부분집합이고 설명글 태그 줄에서 앞 5개", len(pri) == 5 and set(pri) <= set(alltags) and dtags[:5] == pri and set(dtags) == set(alltags), {"우선": pri, "설명글 앞 5": dtags[:5]})
h0 = next((x for x in hooks if x[0] == "H0"), None); l1 = re.search(r"^## 1\s*\n\s*\*\*(.+?)\*\*", rec, re.M)
chk("C08", "후킹 대사 4개(결과 선공개·질문·반전·공감), H0가 촬영된 1번 줄과 같음", len(hooks) == 4 and [h[1] for h in hooks] == ["결과 선공개형", "질문형", "반전형", "공감형"] and bool(h0 and l1 and h0[2] == l1.group(1).strip()), [h[0] for h in hooks])
eo = lambda s: len(re.findall(r"\S+", s))
chk("C09", "썸네일 문구 4개, 각 5어절 이하", len(thumbs) == 4 and all(eo(x) <= 5 for _, x in thumbs), [(i, eo(x)) for i, x in thumbs])
copy = "\n".join([x for _, x in titles] + [desc] + [h[2] for h in hooks[1:]] + [x for _, x in thumbs])   # 새로 만든 문구(촬영된 H0 인용 제외)
scan = "\n".join(l for l in t.splitlines() if "말로 꾸밀 수 있습니다" not in l)   # 촬영된 H0 대사의 인용만 제외하고 문서 전체를 검사
bad = [w for w in ("무조건", "100%", "누구나", "1분 만에", "클릭 한 번", "반드시 성공", "완벽", "대박", "충격") if w in scan]
chk("C10", "과장·낚시 표현 없음(문서 전체, 촬영된 H0 인용만 제외)", not bad, bad or "없음")
exp = [w for w in ("제가 직접", "저도", "해봤더니", "헤맸", "막혔어요", "넣었습니다", "만들었습니다", "꾸며 봤", "바꿔 봤") if w in copy]
chk("C11", "경험 단정 표현 없음", not exp, exp or "없음")
chk("C12", "가격·모델명·구독자·조회수 수치 없음", not re.search(r"\d+\s*(원|달러|\$)|Opus|Sonnet|Haiku|GPT|\d+\s*만\s*(회|명)|구독자|조회수\s*\d", copy), "새 문구 전체 검사")
urls = re.findall(r"https?://[^\s)]+", t.split("## 6.")[1])
chk("C13", "근거 자료 링크 8개 이상, 근거 문서의 한계(제3자·공식 아님·확인 필요) 명시", len(urls) >= 8 and "공식 자료가 아니다" in t and "확인 필요" in t and "찾지 못했다" in t, f"링크 {len(urls)}개")
chk("C14", "미치환 변수({{…}}, [[…]])·TODO 없음(링크 제목의 [ ] 글자는 변수가 아님)", not re.search(r"\{\{|\[\[[^\]]*\]\]|TODO", t))
tl = [l for l in t.splitlines() if re.match(r"\|\s*T\d+\s*\|", l)]
cnt_ok = all(len(c[1].strip()) == int(re.search(r"(\d+)자", c[2]).group(1)) for c in (l.strip().strip("|").split("|") for l in tl))
chk("C15", "제목 표의 '글자 수' 칸이 실제 글자 수와 같음", cnt_ok, [(l.strip().strip("|").split("|")[0].strip(), len(l.strip().strip("|").split("|")[1].strip())) for l in tl])
ev = re.findall(r"^## 16\s*\n\s*\*\*(.+?)\*\*", rec, re.M); last = ev[0] if ev else ""
chk("C16", "설명글 다음 편 예고가 영상 마지막 대사(16번 줄)·6/30과 일치", "되돌리기" in last and "다음 편 6/30: 망가졌을 때 되돌리기" in desc and "망가졌을 때 되돌리기" in last, last)
st = {"앞 편 연결(4편 저장)": "4편에서 저장" in desc, "1단계 느낌": re.search(r"1단계 느낌", desc) is not None, "2단계 색과 크기 구체적": re.search(r"2단계 색과 크기를 구체적으로", desc) is not None, "3단계 잘 보이는지·기능 그대로": re.search(r"3단계 잘 보이는지.*기능이 그대로", desc) is not None, "AI 답 매번 다름": "AI의 답은 매번 달라질 수 있습니다" in desc, "직접 촬영·녹음": "직접 촬영·녹음" in desc}
chk("C17", "설명글이 5편 고유 요소(앞 편 연결, 1·2·3단계 내용, AI 답 매번 다름, 직접 촬영)를 담음", all(st.values()), [k for k, v in st.items() if not v] or "모두 포함")
fp = os.path.join(D, "05_설명글_최종.md"); fin = re.search(r"```설명글\n(.*?)\n```", open(fp, encoding="utf-8").read(), re.S).group(1) if os.path.exists(fp) else None
chk("C18", "설명글 최종 파일의 본문이 문구 문서 2절과 글자 그대로 같음", fin == desc, "일치" if fin == desc else "불일치 또는 파일 없음")
unk = [w for w in ("파란색으로 바뀝", "확실히", "보장", "배 커집", "px로", "% 커") if w in copy]
chk("C19", "시험하지 못한 AI 결과의 모양(색 이름·배율)을 문구에서 단정하지 않음", not unk, unk or "없음")
print(json.dumps(res, ensure_ascii=False, indent=1)); print("TOTAL", len(res), "PASS", sum(r["result"] == "PASS" for r in res), "FAIL", sum(r["result"] == "FAIL" for r in res))
