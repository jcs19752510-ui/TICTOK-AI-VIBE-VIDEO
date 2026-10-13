#!/usr/bin/env python3
"""녹음 스크립트 생성: scenes.json의 나레이션을 그대로 뽑아 사용자가 폰으로 녹음할 대본 문서를 만든다.
대사는 영상 자막·합성 스크립트와 같은 원본(scenes.json)에서 나오므로 어긋나지 않는다.
사용: python3 -I make_recording_script.py <영상폴더> <출력.md>
"""
import json, os, re, sys

vdir, out = sys.argv[1:3]
EP = json.load(open(os.path.join(vdir, "scenes.json"), encoding="utf-8"))
SPILL_OK = 0.5  # 장면 길이보다 이만큼까지는 길어져도 된다(합성 허용치 0.6초보다 여유 있게)


def syllables(s):
    s = s.replace("AI", "에이아이").replace("API", "에이피아이")
    return len(re.findall(r"[가-힣]", s)) + len(re.findall(r"\d", s))


def pace(rate):
    if rate <= 4.6: return "평소 속도로 읽으면 시간이 남아요"
    if rate <= 5.4: return "평소 속도로 읽으세요(너무 천천히 읽으면 시간을 넘겨요)"
    return "평소보다 조금 빠르게, 또박또박"


def pron(text):
    notes = []
    if "AI" in text: notes.append("`AI`는 **에이아이**")
    m = re.findall(r"(\d)단계", text)
    names = {"1": "일", "2": "이", "3": "삼"}
    for d in dict.fromkeys(m): notes.append(f"`{d}단계`는 **{names[d]}단계**")
    if "앱만들기" in text: notes.append("`앱만들기`는 **앱 만들기**를 붙여서 한 단어처럼")
    return notes


L = []
L.append("# 녹음 스크립트 — 에피소드 1/30 \"코딩 몰라도 앱 만들었습니다\"\n")
L.append("> 이 대본은 영상 자막(`영상/ep01_narration.srt`)과 **같은 원본에서 자동으로 만들었습니다.** 글자를 바꾸지 말고 그대로 읽어 주세요. 문장을 고치고 싶으면 먼저 알려 주세요(영상 자막과 시간도 함께 바뀝니다).\n")
L.append("## 1. 녹음 전에 (5가지)\n")
L.append("1. **조용한 방**에서 녹음하세요. 에어컨·선풍기·TV·음악을 끄세요.")
L.append("2. 폰 마이크를 입에서 **15~20cm** 떨어뜨려 고정하세요(책상 위에 세워 두면 좋습니다).")
L.append("3. 기본 **음성 녹음 앱**이면 충분합니다. 파일은 mp3가 좋지만 **m4a, wav도 받을 수 있습니다.**")
L.append("4. 말은 **평소 친구에게 설명하듯** 친근하게 하세요. 너무 크게 외치거나 속삭이지 마세요.")
L.append("5. 틀리면 그 장면만 **처음부터 다시** 읽으세요. 이어 붙이려고 애쓰지 않아도 됩니다.\n")
L.append("## 2. 꼭 지켜야 할 것 (저작권·개인정보)\n")
L.append("- 아래 대본에 **없는 말을 하지 마세요**(인사, 노래, 다른 사람의 글, 인용구).")
L.append("- **배경음악, TV·영상 소리, 다른 사람 목소리**가 섞이지 않게 하세요.")
L.append("- 다른 사람 목소리를 흉내 내거나 **음성 변조·복제 앱**을 쓰지 마세요.")
L.append("- 이름·주소·전화번호 등 **개인정보를 말하지 마세요.** 실수로 말했다면 그 녹음은 보내지 말고 다시 하세요.\n")
L.append("## 3. 녹음 방법 (둘 중 하나 선택)\n")
L.append("### 방법 A (추천): 장면별 15개 파일\n")
L.append("- 장면마다 따로 녹음합니다. 싱크가 가장 정확하고, 틀려도 그 장면만 다시 하면 됩니다.")
L.append("- 각 녹음은 **1초 조용히 → 대사 → 1초 조용히** 순서로 하세요. (녹음 시작 버튼을 누르고 속으로 \"하나\" 센 뒤 읽기 시작)")
L.append("- 파일 이름: `01.mp3`, `02.mp3`, … `15.mp3` (장면 번호 두 자리). 한 장면을 여러 번 녹음했다면 **가장 마음에 드는 것 하나만** 보내 주세요.\n")
L.append("### 방법 B: 한 번에 읽기 (파일 1개)\n")
L.append("- 장면 1부터 15까지 **순서대로** 읽습니다. 장면 사이에 **2초 쉬세요**(말하지 말고 속으로 \"하나, 둘\").")
L.append("- 중간에 틀리면 **그 장면을 처음부터 다시** 읽으세요(틀린 부분은 제가 잘라 냅니다). 파일 이름: `전체.mp3`")
L.append("- 쉬는 구간이 뚜렷해야 장면을 나눌 수 있으니, 방법 B는 숨을 고르는 구간을 확실히 두세요.\n")
L.append("## 4. 대본 (장면 1~15)\n")
L.append("> **목표 시간**은 영상의 장면 길이입니다. 이보다 0.5초 넘게 길어지면 영상과 어긋나므로 조금 더 빠르게 읽거나 알려 주세요. 평소 말 속도는 초당 5~6음절입니다.\n")
tot = 0
for sc in EP["scenes"]:
    n = syllables(sc["narration"]); d = sc["duration"]; rate = n / (d + SPILL_OK)
    tot += n
    L.append(f"### 장면 {sc['id']}  ·  파일 `{sc['id']:02d}.mp3`\n")
    L.append(f"> ## {sc['narration']}\n")
    L.append(f"- 목표 시간: **{d}초 안쪽** (최대 {d + SPILL_OK:.1f}초) · {pace(rate)} · 약 {n}음절")
    L.append(f"- 이 장면의 화면 자막: 「{sc['caption']}」")
    for note in pron(sc["narration"]): L.append(f"- 발음: {note}")
    L.append("")
L.append("## 5. 보내는 방법\n")
L.append("1. **대화창에 첨부해서 보내는 것을 권장합니다.** (공개 저장소에 올리면 녹음에 실수로 들어간 개인정보까지 공개되어 되돌리기 어렵습니다.)")
L.append("2. 파일이 많아 첨부가 어렵다면 알려 주세요. 다른 방법을 안내합니다.")
L.append("3. 보내실 때 **어느 방법(A 또는 B)으로 녹음했는지** 한 줄만 적어 주세요.\n")
L.append("## 6. 보내 주시면 제가 하는 일\n")
L.append("1. 파일을 장면에 맞춰 배치하고 음량을 맞춥니다(−16 LUFS).")
L.append("2. 장면별 음성 시작 위치, 마지막 음성 끝, 피크, 무음 구간, 오디오·영상 길이를 검수합니다.")
L.append("3. 영상 우상단의 **\"AI 음성\" 배지를 제거**하고 설명글의 AI 음성 문구를 지웁니다. \"재현 화면\" 표기는 유지합니다.")
L.append("4. 영상 검수·보안 점검(녹음에 개인정보나 잡음이 없는지 포함)·재생 확인 후 내부테스트 결과서를 갱신하고 푸시합니다.")
L.append("5. 업로드 전 **직접 들어보시고**, 틱톡의 \"AI 생성 콘텐츠\" 라벨 설정을 앱에서 확인해 주세요(업로드는 사용자가 합니다).\n")
L.append(f"---\n전체 대사 약 {tot}음절 · 장면 15개 · 영상 {EP['total']}초\n")
open(out, "w", encoding="utf-8").write("\n".join(L))
print("OK", len(EP["scenes"]), "장면", tot, "음절")
