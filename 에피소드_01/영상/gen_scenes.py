#!/usr/bin/env python3
"""1단계(설계): 에피소드 문서의 장면표를 읽어 scenes.json / scenes.js / SRT 2종을 만든다.
장면표(B)와 1:1로 대응하며, 손으로 고친 값이 없도록 항상 문서에서 생성한다.
사용: python3 -I gen_scenes.py <에피소드.md> <출력폴더>
"""
import json, re, sys, os

md_path, out = sys.argv[1], sys.argv[2]
t = open(md_path, encoding="utf-8").read()
FPS, WIDTH, HEIGHT = 30, 1080, 1920

scenes = []
for line in t.splitlines():
    m = re.match(r"\|\s*(\d+)\s*\|\s*(\d+):(\d+)–(\d+):(\d+)\s*\|(.*)\|(.*)\|(.*)\|(.*)\|\s*$", line)
    if not m:
        continue
    s = int(m[2]) * 60 + int(m[3]); e = int(m[4]) * 60 + int(m[5])
    scenes.append(dict(id=int(m[1]), start=s, end=e, duration=e - s, screen=m[6].strip(),
                       narration=m[7].strip(), caption=m[8].strip(), fx=m[9].strip()))

prompts = dict(re.findall(r"예시 (①|②) \(장면 \d+\): `([^`]+)`", t))
assert len(scenes) == 15, f"장면 수 15 아님: {len(scenes)}"
assert set(prompts) == {"①", "②"}, f"프롬프트 예시 추출 실패: {prompts}"
assert all(scenes[i]["end"] == scenes[i + 1]["start"] for i in range(14)), "타임라인 불연속"

data = dict(width=WIDTH, height=HEIGHT, fps=FPS, total=scenes[-1]["end"],
            frames=scenes[-1]["end"] * FPS, prompts=dict(p1=prompts["①"], p2=prompts["②"]),
            series="1/30", channel="AI바이브생활팁", handle="@ai_vibe_life_tip", scenes=scenes)
os.makedirs(out, exist_ok=True)
json.dump(data, open(os.path.join(out, "scenes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(os.path.join(out, "scenes.js"), "w", encoding="utf-8").write(
    "window.EP = " + json.dumps(data, ensure_ascii=False) + ";\n")


def ts(sec):
    return f"00:{sec // 60:02d}:{sec % 60:02d},000"


for name, key in (("ep01_caption.srt", "caption"), ("ep01_narration.srt", "narration")):
    with open(os.path.join(out, name), "w", encoding="utf-8") as f:
        for sc in scenes:
            f.write(f"{sc['id']}\n{ts(sc['start'])} --> {ts(sc['end'])}\n{sc[key]}\n\n")
print("OK", len(scenes), "scenes,", data["total"], "s,", data["frames"], "frames")
