#!/usr/bin/env python3
"""에피소드 2 장면표(B)를 읽어 scenes.json / scenes.js / SRT 2종을 만든다 (손으로 고친 값이 없도록 항상 문서에서 생성).
사용: python3 -I gen_scenes.py <에피소드.md> <출력폴더>"""
import json, re, sys, os

md_path, out = sys.argv[1], sys.argv[2]
t = open(md_path, encoding="utf-8").read()
FPS = 30
scenes = []
for line in t.splitlines():
    m = re.match(r"\|\s*(\d+)\s*\|\s*(\d+):(\d+)–(\d+):(\d+)\s*\|(.*)\|(.*)\|(.*)\|(.*)\|(.*)\|\s*$", line)
    if not m:
        continue
    s = int(m[2]) * 60 + int(m[3]); e = int(m[4]) * 60 + int(m[5])
    scenes.append(dict(id=int(m[1]), start=s, end=e, duration=e - s, screen=m[6].strip(),
                       narration=m[7].strip(), caption=m[9].strip(), fx=m[10].strip()))
prompts = dict(re.findall(r"예시 (①|②|③) \(장면 \d+, \d단계[^)]*\): `([^`]+)`", t))
assert len(scenes) == 16, f"장면 수 16 아님: {len(scenes)}"
assert set(prompts) == {"①", "②", "③"}, f"프롬프트 추출 실패: {prompts}"
assert all(scenes[i]["end"] == scenes[i + 1]["start"] for i in range(15)), "타임라인 불연속"
data = dict(width=1080, height=1920, fps=FPS, total=scenes[-1]["end"], frames=scenes[-1]["end"] * FPS,
            prompts=dict(p1=prompts["①"], p2=prompts["②"], p3=prompts["③"]),
            series="2/30", channel="AI바이브생활팁", handle="@ai_vibe_life_tip",
            voice="user", mock_badge=False, scenes=scenes)
os.makedirs(out, exist_ok=True)
json.dump(data, open(os.path.join(out, "scenes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(os.path.join(out, "scenes.js"), "w", encoding="utf-8").write("window.EP = " + json.dumps(data, ensure_ascii=False) + ";\n")
ts = lambda s: f"00:{s // 60:02d}:{s % 60:02d},000"
for name, key in (("ep02_caption.srt", "caption"), ("ep02_narration.srt", "narration")):
    with open(os.path.join(out, name), "w", encoding="utf-8") as f:
        for sc in scenes:
            f.write(f"{sc['id']}\n{ts(sc['start'])} --> {ts(sc['end'])}\n{sc[key]}\n\n")
print("OK", len(scenes), "scenes,", data["total"], "s,", data["frames"], "frames")
