#!/usr/bin/env python3
"""촬영본의 말소리를 한국어 음성 인식(sherpa-onnx)으로 대본 15줄에 맞춰 시각표(cuts.json)와 화면 신호(cues)를 만든다. (DEC-039)

사용: python3 align_speech.py <인식결과.json> <촬영본 16kHz mono wav> <영상폴더(scenes.json)> <출력 cuts.json> <촬영 파일명>
 인식결과.json: {"tokens": [...], "timestamps": [...]} (sherpa-onnx OnlineRecognizer.get_result_all, 같은 폴더의 asr_run.py 참조)

동작
 1) 에너지로 말소리 구간을 찾는다(잡음 바닥+12dB, 0.25초 미만 틈은 메움).
 2) 인식된 글자열과 대본 15줄을 이어 붙인 글자열을 글자 단위로 정렬(difflib)해, 대본의 모든 글자에 말한 시각을 붙인다(인식 오류는 앞뒤 시각 사이로 보간).
 3) 줄 시작·끝 = 그 줄 글자들의 시각에 가장 가까운 말소리 구간의 시작·끝. 줄은 순서대로 15개여야 하며 겹치면 실패한다.
 4) 장면별 cues = 대본의 구절(영상폴더의 cues.json)이 시작되는 시각(장면 시작 기준이 아니라 촬영본 시각, 합성기가 장면 기준으로 바꾼다).
 5) 줄별 대본 일치율을 출력한다. 낮으면 사용자가 대본과 다르게 읽은 것이므로 알려야 한다(인식기는 오류가 있다).
"""
import json, re, sys, wave, difflib
import numpy as np

asr_p, wav_p, vdir, out_p, fname = sys.argv[1:6]
asr = json.load(open(asr_p, encoding="utf-8"))
base = json.load(open(vdir.rstrip("/") + "/scenes.json", encoding="utf-8"))
scenes = base["scenes"]; N = len(scenes)
cue_cfg = json.load(open(vdir.rstrip("/") + "/cues.json", encoding="utf-8"))   # 장면 번호 -> {신호 이름: 대본 구절}
norm = lambda s: re.sub(r"[^가-힣0-9A-Za-z]", "", s)

# 1) 말소리 구간
w = wave.open(wav_p); a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
n = int(w.getframerate() * 0.02); k = len(a) // n
db = 20 * np.log10(np.sqrt(np.mean(a[:k * n].reshape(k, n) ** 2, axis=1)) + 1e-9)
thr = max(float(np.percentile(db, 10)) + 12.0, -50.0)
iv, i = [], 0
while i < k:
    if db[i] > thr:
        j = i
        while j < k and db[j] > thr: j += 1
        if iv and (i - iv[-1][1]) * 0.02 < 0.25: iv[-1][1] = j
        else: iv.append([i, j])
        i = j
    else: i += 1
iv = [(x * 0.02, y * 0.02) for x, y in iv if (y - x) * 0.02 >= 0.12]

# 2) 인식 글자 -> 시각 (토큰 안의 글자는 다음 토큰 시각 사이로 나눠 가짐)
hyp, hyp_t = [], []
toks, ts = asr["tokens"], asr["timestamps"]
for ti, (t, tt) in enumerate(zip(toks, ts)):
    chars = [c for c in t if re.match(r"[가-힣0-9A-Za-z]", c)]
    nxt = ts[ti + 1] if ti + 1 < len(ts) else tt + 0.3
    for ci, c in enumerate(chars):
        hyp.append(c); hyp_t.append(tt + (min(nxt, tt + 0.5) - tt) * ci / max(1, len(chars)))
hyp_s = "".join(hyp)
ref, ref_line = [], []
for si, s in enumerate(scenes):
    for c in norm(s["narration"]):
        ref.append(c); ref_line.append(si)
ref_s = "".join(ref)
sm = difflib.SequenceMatcher(None, ref_s, hyp_s, autojunk=False)
ref_t = [None] * len(ref_s)
for blk in sm.get_matching_blocks():
    for d in range(blk.size): ref_t[blk.a + d] = hyp_t[blk.b + d]
matched = [t is not None for t in ref_t]      # 인식기가 실제로 들은 글자(보간한 글자와 구분)
# 인식 못 한 글자: 앞뒤 시각 사이를 보간
known = [i for i, t in enumerate(ref_t) if t is not None]
if not known: sys.exit("FAIL: 대본과 맞는 인식 글자가 없습니다.")
xs = np.array(known, dtype=float); ys = np.array([ref_t[i] for i in known])
ref_t = [float(np.interp(i, xs, ys)) for i in range(len(ref_s))]

def near_idx(t):
    """시각 t가 속한(또는 가장 가까운) 말소리 구간의 번호."""
    return min(range(len(iv)), key=lambda j: 0 if iv[j][0] - 0.15 <= t <= iv[j][1] + 0.15 else min(abs(t - iv[j][0]), abs(t - iv[j][1])))

raw = []
for si in range(N):
    idx = [i for i, l in enumerate(ref_line) if l == si and matched[i]]   # 줄의 처음·끝은 실제로 들은 글자 기준(대사 끝을 못 알아들어도 다음 줄로 번지지 않게)
    if not idx: sys.exit(f"FAIL: 줄 {scenes[si]['id']}에서 대본과 맞는 인식 글자가 없습니다.")
    raw.append([near_idx(ref_t[idx[0]]), near_idx(ref_t[idx[-1]]), ref_t[idx[0]], ref_t[idx[-1]]])
GAP = 0.5   # 줄 안의 쉼은 0.56초 이하, 줄 사이 쉼은 0.58초 이상(이 촬영본 실측). 앞뒤 구간을 이웃 줄에 닿지 않는 범위에서 이어 붙인다
lines = []
for si in range(N):
    a, b = raw[si][0], raw[si][1]
    lo = raw[si - 1][1] + 1 if si else 0
    hi = raw[si + 1][0] - 1 if si + 1 < N else len(iv) - 1
    while a - 1 >= lo and iv[a][0] - iv[a - 1][1] < GAP: a -= 1
    while b + 1 <= hi and iv[b + 1][0] - iv[b][1] < GAP: b += 1
    lines.append(dict(id=scenes[si]["id"], start=round(iv[a][0], 3), end=round(iv[b][1], 3), t_first=round(raw[si][2], 2), t_last=round(raw[si][3], 2)))
for p, q in zip(lines, lines[1:]):
    if p["end"] > q["start"] + 1e-6:
        sys.exit(f"FAIL: 줄 {p['id']}과 {q['id']}의 구간이 겹칩니다({p['end']} > {q['start']}). 대본과 다르게 읽었거나 순서가 바뀌었을 수 있습니다.")

# 5) 줄별 일치율(인식기 오류 포함이므로 참고용)
rows = []
for si, ln in enumerate(lines):
    got = "".join(h for h, t in zip(hyp, hyp_t) if ln["start"] - 0.4 <= t <= ln["end"] + 0.15)
    exp = norm(scenes[si]["narration"])
    ln["match"] = round(difflib.SequenceMatcher(None, exp, got).ratio(), 2); ln["heard"] = got

# 4) 구절 시각(cues)
cues = {}
for si, s in enumerate(scenes):
    for name, phrase in (cue_cfg.get(str(s["id"])) or {}).items():
        full = norm(s["narration"]); pn = norm(phrase); pos = full.find(pn)
        if pos < 0: sys.exit(f"FAIL: 장면 {s['id']}의 구절 '{phrase}'가 대본에 없습니다.")
        first = [i for i, l in enumerate(ref_line) if l == si][0]
        cues.setdefault(s["id"], {})[name] = round(ref_t[first + pos], 3)

out = dict(file=fname, memo="음성 인식과 대본 정렬로 만든 시각표(align_speech.py, DEC-039). start/end=말소리 구간, cues=구절이 시작되는 촬영본 시각",
           scenes=[dict(id=l["id"], start=l["start"], end=l["end"], **({"cues": cues[l["id"]]} if l["id"] in cues else {})) for l in lines])
json.dump(out, open(out_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("줄 | 구간 | 일치율 | 인식된 말")
for l in lines: print(f"{l['id']:>2} | {l['start']:6.2f}~{l['end']:6.2f} | {l['match']:.2f} | {l['heard']}")
print("완료:", out_p)
