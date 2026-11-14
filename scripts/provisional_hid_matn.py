"""PROVISIONAL HID matn for كتاب الطهارات (development only for T2.3).

Not the official HID segmentation (that is T2.2's 01-tahara.matn.txt).
Rule: every "..." quote in S1 pages 11-45 that is preceded by «قال:» or opens a
paragraph starts a unit; later quotes in the same unit are appended (joined
with " … ") unless preceded by a hadith marker (﵊ ﷺ ﵁ ﵇ لقوله قوله روي).
Output: id<TAB>matn<TAB>lib_page (provisional ids HIDP.01.NN.SSSS, NN = heading order).
"""
import re, sqlite3, sys

DB = '/home/claude/kashshaf/data/kashshaf.db'
OUT = sys.argv[1] if len(sys.argv) > 1 else '/tmp/hid_prov.matn.txt'
c = sqlite3.connect(DB, timeout=60)
units = []  # [nn, [frags], page]
nn = 0
HAD = re.compile(r'(﵊|ﷺ|﵁|﵇|لقوله|قوله|روي|قول)[^"]{0,6}$')
for pid, body in c.execute("select lib_page_id, body from page where source_id='S1' "
                           "and lib_page_id between 11 and 45 order by lib_page_id"):
    pos = 0
    events = [(m.start(), 'h', m.group(1)) for m in
              re.finditer(r"<span data-type='title'[^>]*>([^<]*)</span>", body)]
    events += [(m.start(), 'q', m.group(1)) for m in re.finditer(r'"([^"\r]+)"', body)]
    for st, kind, txt in sorted(events):
        if kind == 'h':
            nn += 1
            continue
        pre = body[max(0, st - 30):st]
        if re.search(r'قال:\s*$', pre) or st == 0 or re.search(r'(\r|</span>)\s*$', pre):
            units.append([nn, [txt], pid])
        elif HAD.search(pre):
            continue
        else:  # provisional: every other non-hadith quote is its own unit
            units.append([nn, [txt], pid])
seq = {}
with open(OUT, 'w', encoding='utf-8') as f:
    for nn_, frags, pid in units:
        seq[nn_] = seq.get(nn_, 0) + 1
        f.write(f"HIDP.01.{nn_:02d}.{seq[nn_]:04d}\t{' … '.join(frags)}\t{pid}\n")
print(len(units), 'units ->', OUT)
