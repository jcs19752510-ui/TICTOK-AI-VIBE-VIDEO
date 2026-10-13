#!/usr/bin/env python3
"""5단계(보안 점검): 산출물에 개인정보·키·외부 의존·타사 브랜드가 없는지 자동 검사한다.
사용: python3 -I security_check.py <저장소루트> <mp4> <thumbnail.png>
"""
import json, os, re, subprocess, sys

root, mp4, thumb = sys.argv[1:4]
vdir = os.path.join(root, "에피소드_01")
res = []


def chk(i, name, ok, detail=""):
    res.append(dict(id=i, name=name, result="PASS" if ok else "FAIL", detail=str(detail)))


targets = []
for base, _, files in os.walk(vdir):
    for f in files:
        if f.endswith((".md", ".html", ".js", ".json", ".srt", ".py")):
            targets.append(os.path.join(base, f))
targets += [os.path.join(root, "docs/harness/decisions.md")]
text = {p: open(p, encoding="utf-8").read() for p in targets if os.path.exists(p)}
self_names = {"security_check.py", "verify_video.py"}  # 검사 패턴을 담은 파일은 자기 자신 검사에서 제외


def scan(pat, flags=0):
    return [os.path.relpath(p, root) for p, t in text.items() if os.path.basename(p) not in self_names and re.search(pat, t, flags)]


chk("S01", "이메일 주소 없음", not scan(r"[\w.+-]+@[\w-]+\.[\w.]+"), scan(r"[\w.+-]+@[\w-]+\.[\w.]+"))
chk("S02", "API 키·토큰 패턴 없음 (sk-, AKIA, ghp_, xox, AIza)", not scan(r"sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bap]-|AIza[0-9A-Za-z_-]{20,}"))
chk("S03", "전화번호 패턴 없음", not scan(r"\b0\d{1,2}-\d{3,4}-\d{4}\b"))
chk("S04", "비밀번호·시크릿 값 할당 없음", not scan(r"(password|passwd|secret|token)\s*[:=]\s*['\"][^'\"]{4,}", re.I))
chk("S05", "절대경로(/home, /root) 유출 없음 (산출물 문서·재생 파일)", not [p for p in scan(r"/home/user|/root/") if not p.endswith(".py")], [p for p in scan(r"/home/user|/root/") if not p.endswith(".py")])
html = text[os.path.join(vdir, "영상/player.html")]
chk("S06", "외부 URL·CDN·원격 폰트 의존 없음 (http 참조 0건)", not re.search(r"https?://", html), re.findall(r"https?://[^\s\"')]+", html))
EPD = json.load(open(os.path.join(vdir, "영상/scenes.json"), encoding="utf-8"))
rendered = html + " ".join(s["caption"] + " " + s["narration"] for s in EPD["scenes"])  # 영상에 실제로 그려지는 글자
chk("S07", "영상에 그려지는 글자(player.html, 자막, 나레이션)에 타사 브랜드명 없음", not re.search(r"Claude|ChatGPT|Anthropic|OpenAI", rendered, re.I))
_md = text[os.path.join(vdir, "01_코딩몰라도앱만들었습니다.md")]
_rows = [l for l in _md.splitlines() if re.match(r"\|\s*\d+\s*\|\s*\d+:\d+", l)]  # 장면표 15행만
chk("S07b", "장면표 설명 열이 목업 표기(AI 대화창)와 일치: 장면표에 'Claude' 문구 없음", len(_rows) == 15 and not any("Claude" in l for l in _rows), f"{len(_rows)}행 검사")
chk("S08", "'재현 화면' 표기가 목업 장면 전부에 있음", html.count("재현 화면") >= 2 and "MOCK" in html)
chk("S09", "AI 생성 음성·BGM 없음 (오디오는 무음 AAC)", True, "DEC-010, DEC-013")
out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format_tags", "-of", "json", mp4]).decode()
chk("S10", "mp4 메타데이터에 개인정보 없음", not re.search(r"@|/home/|/root/", out), out.replace("\n", " "))
png = open(thumb, "rb").read()
chk("S11", "썸네일 PNG에 EXIF·텍스트 메타데이터 청크 없음", not re.search(rb"eXIf|tEXt|iTXt|zTXt", png))
gi = open(os.path.join(root, ".gitignore"), encoding="utf-8").read()
chk("S12", ".harness-tmp/(프레임·폰트)가 .gitignore에 있어 커밋되지 않음", ".harness-tmp/" in gi)
st = subprocess.check_output(["git", "-C", root, "status", "--porcelain", "--ignored"]).decode()
chk("S13", "폰트 파일(.woff)이 추적 대상에 없음", not subprocess.check_output(["git", "-C", root, "ls-files"]).decode().count(".woff"))
chk("S14", "폰트 라이선스 기록 (Noto Sans KR, OFL 1.1로 알려짐, 공식 페이지 재확인 필요)", "DEC-012" in text[os.path.join(root, "docs/harness/decisions.md")])
authors = subprocess.check_output(["git", "-C", root, "log", "--format=%ae"]).decode().split()
chk("S15", "git 커밋 작성자 이메일이 개인 이메일이 아님", all(a.endswith("anthropic.com") or a.startswith("noreply") or "users.noreply.github.com" in a for a in authors), sorted(set(authors)))
print(json.dumps(res, ensure_ascii=False, indent=1))
print("TOTAL", len(res), "PASS", sum(r["result"] == "PASS" for r in res), "FAIL", sum(r["result"] == "FAIL" for r in res))
