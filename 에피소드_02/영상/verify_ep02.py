#!/usr/bin/env python3
"""에피소드 2 재현 화면 영상 검수. 사용: python3 -I verify_ep02.py <mp4> <scenes.json> (실패 시 종료코드 1)"""
import json, subprocess, sys, re
mp4, sj = sys.argv[1], sys.argv[2]
EP = json.load(open(sj, encoding="utf-8")); res = []
def chk(n, ok, msg): res.append(ok); print(("PASS" if ok else "FAIL"), n, msg)
def run(*a): return subprocess.run(a, capture_output=True, text=True)
pr = json.loads(run("ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", mp4).stdout)
vs = [s for s in pr["streams"] if s["codec_type"] == "video"]; au = [s for s in pr["streams"] if s["codec_type"] == "audio"]
v = vs[0]; dur = float(pr["format"]["duration"])
chk("V01", (v["width"], v["height"]) == (1080, 1920), f'해상도 {v["width"]}x{v["height"]} (9:16)')
chk("V02", v["codec_name"] == "h264" and v["pix_fmt"] == "yuv420p", f'코덱 {v["codec_name"]} {v["pix_fmt"]}')
chk("V03", v["r_frame_rate"] == "30/1", f'프레임레이트 {v["r_frame_rate"]}')
chk("V04", 60 <= dur <= 90 and abs(dur - EP["total"]) < 0.1, f"길이 {dur:.2f}초 (시간표 {EP['total']}초, 규격 60~90초)")
chk("V05", int(v["nb_read_frames"]) == EP["frames"], f'프레임 수 {v["nb_read_frames"]} (기대 {EP["frames"]})')
dec = run("ffmpeg", "-v", "error", "-i", mp4, "-f", "null", "-"); chk("V06", dec.stderr.strip() == "", "전체 디코딩 오류 0건")
tags = json.dumps(pr["format"].get("tags", {})) + "".join(json.dumps(s.get("tags", {})) for s in pr["streams"])
chk("V07", not re.search(r"location|gps|iso6709|latitude|longitude", tags, re.I), "위치정보(GPS) 태그 없음")
chk("V08", len(EP["scenes"]) == 16 and all(a["end"] == b["start"] for a, b in zip(EP["scenes"], EP["scenes"][1:])), "장면 16개, 시간표 연속")
chk("V09", all(2 <= s["duration"] <= 5 for s in EP["scenes"]), "장면 길이 2~5초")
chk("V10", EP.get("mock_badge") is False and EP.get("voice") == "user", "재현 화면 배지·AI 음성 배지 미표시 설정")
print("참고: 오디오 스트림", len(au), "개 (무음 시안이면 0)")
print(f"{sum(res)}/{len(res)} 통과"); sys.exit(0 if all(res) else 1)
