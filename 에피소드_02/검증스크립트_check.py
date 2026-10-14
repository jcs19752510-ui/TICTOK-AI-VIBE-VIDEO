#!/usr/bin/env python3
"""에피소드 2 문서 검증. 사용: python3 에피소드_02/검증스크립트_check.py  (실패가 있으면 종료코드 1)"""
import re, sys, os
here = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(here, '02_코딩몰라도앱고치기.md'), encoding='utf-8').read()
res = []
def chk(n, ok, msg): res.append((n, ok, msg)); print(('PASS' if ok else 'FAIL'), n, msg)
def sec(s): m, x = s.split(':'); return int(m)*60 + int(x)
rows = [[x.strip() for x in r.strip('|').split('|')] for r in t.split('\n') if re.match(r'\| \d+ \| \d:\d\d', r)]
chk('T01', len(rows) == 16, f'장면 {len(rows)}개')
prev = 0; bad = []
for c in rows:
    a, b = c[1].replace('–', '-').split('-'); d = sec(b) - sec(a)
    n = len(re.findall('[가-힣0-9]', c[3]))
    if sec(a) != prev or not 2 <= d <= 5 or n > d*5.5 or c[4] != f'{n}/{int(d*5.5)}': bad.append((c[0], d, n, c[4]))
    prev = sec(b)
chk('T02', not bad, f'장면 연속·길이 2~5초·음절 ≤ 초×5.5·표의 음절 표기 일치, 위반 {bad}')
chk('T03', 60 <= prev <= 90, f'총 길이 {prev}초')
cs = re.search(r'## C\..*?\n\n(.*?)\n## D', t, re.S).group(1)
cl = [re.sub(r'^\d+\. ', '', x) for x in cs.split('\n') if re.match(r'\d+\. ', x)]
bn = [c[3] if c[3][-1] in '?.' else c[3] + '.' for c in rows]
chk('T04', cl == bn, 'C 대본과 B 나레이션 일치')
d = re.search(r'\*\*설명글\*\*.*?\n\n(.*?)\n\n\*\*해시', t, re.S).group(1)
chk('T05', len(d) <= 500, f'설명글 {len(d)}자')
chk('T06', d.split('\n')[0].split('.')[0].strip().endswith('?') or '?' in d[:30], '설명글 첫 줄 질문')
chk('T07', d.strip().endswith('재현 화면입니다.'), '설명글 마지막 줄 재현 화면 표기')
tags = re.findall(r'#\S+', t.split('**해시태그')[1].split('## E')[0])
chk('T08', len(tags) == 10, f'해시태그 {len(tags)}개')
body = t.split('## H.')[0]
for i, w in enumerate(['제가 직접', '저도', '해봤', '해 봤', '헤맸', '무조건', '100%', '누구나', '1분 만에', '클릭 한 번'], 9):
    chk(f'T{i:02d}', body.count(w) == 0, f'금지 표현 "{w}" 0건')
chk('T19', not re.search('해요|줘요|볼게요', cs), 'C 대본에 ~해요/~줘요/~볼게요 없음')
chk('T20', len(re.findall(r'^- 예시 [①②③]', t, re.M)) >= 2, '입력 프롬프트 예시 2개 이상')
chk('T21', all(k in t for k in ['1단계', '2단계', '3단계']), '1·2·3단계 구성')
chk('T22', "'앱고치기'" in t and '프롬프트 템플릿을 드리겠습니다' in t, '댓글 CTA')
chk('T23', 'AI 음성' not in re.sub(r'AI 음성 ?(은|없)[^\n]*', '', body), '본문에 AI 음성 사용 표기 없음')
chk('T24', '```' in t.split('## G.')[1].split('## H.')[0], 'G 템플릿 본문 있음')
chk('T25', not re.search(r'sk-[A-Za-z0-9]{10,}|[\w.]+@[\w.]+\.\w+|\d{2,3}-\d{3,4}-\d{4}', t), '키·이메일·전화번호 패턴 없음')
print(f'\n{sum(o for _, o, _ in res)}/{len(res)} 통과'); sys.exit(0 if all(o for _, o, _ in res) else 1)
