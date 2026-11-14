#!/usr/bin/env python3
"""T2.1: يبني فهرس الكتاب (كتاب/باب/فصل) من عناوين الشاملة (store/title) وجدول title في ملف الكتاب.
usage: build_toc.py <source S1|S2> <book_id> <work HID|BID>"""
import json, sqlite3, sys, re, gzip, pathlib
R = pathlib.Path(__file__).resolve().parents[1]
src, book, work = sys.argv[1], int(sys.argv[2]), sys.argv[3]
titles = {}
for l in gzip.open(R/f'raw/shamela_titles/{book}.jsonl.gz', 'rt', encoding='utf-8'):
    r = json.loads(l); titles[int(r['id'].split('-')[1])] = r['body'].strip()
db = sqlite3.connect(R/'data/kashshaf.db')
rows = db.execute('select title_id,page_lib_id,parent from toc where source_id=? order by title_id', (src,)).fetchall()
for tid, _, _ in rows:
    db.execute('update toc set title=? where source_id=? and title_id=?', (titles.get(tid), src, tid))
db.commit()
pg = {p: (v, pp) for p, v, pp in db.execute('select lib_page_id,vol,printed_page from page where source_id=?', (src,))}
node = {tid: {'title_id': tid, 'title': titles.get(tid), 'page_id': p, 'vol': pg.get(p, (None,))[0],
              'printed_page': pg.get(p, (None, None))[1], 'parent': par, 'children': []} for tid, p, par in rows}
roots = []
for tid, p, par in rows:
    (node[par]['children'] if par in node else roots).append(node[tid])
def kind(t):
    t = re.sub(r'[ً-ْ]', '', t or '')
    for k in ('كتاب', 'باب', 'فصل'):
        if t.startswith(k): return k
    return 'other'
def walk(n, depth):
    n['kind'] = kind(n['title']); n['depth'] = depth
    for c in n['children']: walk(c, depth + 1)
for r in roots: walk(r, 1)
# الكتب الفقهية مرقمة: كل عقدة نوعها «كتاب» في أي عمق، بترتيب ورودها
kutub, n = [], 0
def collect(x):
    global n
    if x['kind'] == 'كتاب':
        n += 1; x['kitab_no'] = n; kutub.append({'no': n, 'title': x['title'], 'title_id': x['title_id'], 'page_id': x['page_id'], 'vol': x['vol'], 'printed_page': x['printed_page']})
    for c in x['children']: collect(c)
for r in roots: collect(r)
# نهاية كل كتاب = صفحة بداية الكتاب التالي - 1
last = db.execute('select max(lib_page_id) from page where source_id=?', (src,)).fetchone()[0]
for i, k in enumerate(kutub):
    k['page_end'] = (kutub[i+1]['page_id'] - 1) if i + 1 < len(kutub) else last
out = R/f'data/works/{work}/toc.json'
out.write_text(json.dumps({'source': src, 'book_id': book, 'n_titles': len(rows), 'kutub': kutub, 'tree': roots}, ensure_ascii=False, indent=1))
print(src, 'titles', len(rows), 'with text', sum(1 for t in rows if titles.get(t[0])), 'kutub', len(kutub))
for k in kutub[:80]: print(' ', k['no'], k['vol'], k['page_id'], '-', k['page_end'], k['title'][:50])
