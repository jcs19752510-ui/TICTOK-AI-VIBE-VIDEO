#!/usr/bin/env python3
"""에피소드 문서의 C절(전체 나레이션 대본)에서 <에피소드폴더>/녹음_대사만.md 를 만든다(1편 형식).
사용: python3 -I make_recording.py <에피소드폴더>"""
import glob, os, re, sys
folder = os.path.abspath(sys.argv[1]); NN = os.path.basename(folder).split("_")[1]
md = [f for f in sorted(glob.glob(os.path.join(folder, f"{NN}_*.md"))) if "## C." in open(f, encoding="utf-8").read()][0]
t = open(md, encoding="utf-8").read()
epn = int(re.search(r"# 에피소드 (\d+)/30", t).group(1))
c = re.search(r"## C\..*?\n\n(.*?)\n## D", t, re.S).group(1)
lines = [re.sub(r"^\d+\. ", "", x) for x in c.split("\n") if re.match(r"\d+\. ", x)]
lines = [x[:-1] if x.endswith(".") else x for x in lines]
out = [f"# 녹음 대사 — 에피소드 {epn}/30", "", f"읽는 순서대로 {len(lines)}개입니다.", "",
       "- **한 파일로 녹음할 때**(`전체.mp3`): 1번부터 %d번까지 순서대로 읽고 번호 사이에 **2초 쉬세요.** 틀린 장면은 파일 안에서 다시 읽지 말고, 끝난 뒤 그 장면만 번호 이름(`03.mp3`)으로 따로 녹음해 같이 보내 주세요." % len(lines),
       "- **장면별로 녹음할 때**: 번호와 같은 이름의 파일로 녹음하세요(1번 → `01.mp3`).", ""]
for i, x in enumerate(lines, 1): out += [f"## {i}", "", f"**{x}**", ""]
open(os.path.join(folder, "녹음_대사만.md"), "w", encoding="utf-8").write("\n".join(out))
print(NN, len(lines))
