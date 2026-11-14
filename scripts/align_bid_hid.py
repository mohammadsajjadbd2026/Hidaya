"""T2.3 — align بداية المبتدي (S2) كتاب الطهارة against the HID matn list.

Usage:
  python3 scripts/align_bid_hid.py HID_MATN_FILE [--write-db] [--provisional]

METHOD (documented for PLAN §4.2 step 3):
  1. BID text = concatenation of S2 page bodies from the «كتاب الطهارة» heading
     (p1) to just before «= كتاب الصلاة» (p10); pages joined by '\n'
     (a page-break marker; the only character not taken from page.body).
  2. Heading lines (كتاب/باب/فصل, as <span data-type="title"> or as plain short
     lines) are structure, not matn: their tokens are excluded from alignment.
     For a <span> title that carries matn text (e.g. toc-7 «فصل والمستحاضة …»)
     only the word «فصل» is treated as heading.
  3. Both sides are normalized (scripts/normalize_ar.py) and tokenized.
     HID tokens are labelled with their unit index (HID fragments joined by
     " … " are simply concatenated).
  4. ONE global monotonic alignment: difflib.SequenceMatcher(autojunk=False)
     over the two token sequences.  Opcodes:
       equal   -> BID token assigned to the unit of the paired HID token
       replace -> BID tokens assigned proportionally to the paired HID tokens' units
       delete  -> BID token unassigned (candidate BID-only)
       insert  -> HID token missing in BID
  matn_text of a BID segment = the exact slice of page.body (pages joined by
  '\n'); the only alteration is removal of Shamela markup tags (<span …>, </span>)
  where a title span cuts through matn (flag markup_removed).
  5. Unit span = first..last BID token assigned to it.  score = token-level
     SequenceMatcher ratio between the unit's normalized tokens and the BID span's
     tokens, averaged with the character-level ratio of the joined strings
     (so a one-letter variant in a 2-word matn is not rejected).
     exact: identical normalized token lists; approx: score >= THRESH;
     unmatched (HID-only): no tokens or score < THRESH.  Unmatched units are then
     REMOVED from the HID sequence and the alignment recomputed (repeat until
     stable), so absent HID matn cannot capture neighbouring BID words.
     A standalone «و»/«ف» in HID (from «و … X» fragments) is glued to the next token.
  6. Segmentation: every matched unit = one BID مسألة.  Unassigned BID runs of
     <= ABSORB tokens are absorbed into the preceding segment of the same
     heading section (else the following one); longer runs = BID-only segments.
     Segments never cross a heading.
"""
import bisect, difflib, json, os, random, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize_ar import normalize, tokens_with_spans

ROOT = '/home/claude/kashshaf'
DB = f'{ROOT}/data/kashshaf.db'
THRESH = 0.60
ABSORB = 2

args = [a for a in sys.argv[1:] if not a.startswith('--')]
HID_FILE = args[0]
WRITE_DB = '--write-db' in sys.argv
PROVISIONAL = '--provisional' in sys.argv

con = sqlite3.connect(DB, timeout=60)

# ---------- 1. BID text -------------------------------------------------------
pages = con.execute("select lib_page_id, printed_page, body from page where source_id='S2' "
                    "and lib_page_id between 1 and 12 order by lib_page_id").fetchall()
start_pg, end_pg = None, None
parts, page_off = [], []   # page_off: (concat_offset, lib_page, printed, body_offset_base)
for lib, printed, body in pages:
    if start_pg is None:
        m = re.search(r'=?<span data-type="title" id=toc-\d+>\s*كتاب الطَّهَارَة</span>', body)
        if not m:
            continue
        start_pg, start_off = lib, m.start()
        seg, base = body[m.start():], m.start()
    else:
        seg, base = body, 0
    m2 = re.search(r'\s*=\s*كتاب الصَّلَاة', seg)
    concat_off = sum(len(p) for p in parts) + len(parts)
    if m2:
        seg = seg[:m2.start()]
        end_pg, end_off = lib, base + m2.start()
        kitab_salat_off = base + seg.__len__() + (m2.group().index('='))
    parts.append(seg)
    page_off.append((concat_off, lib, printed, base))
    if m2:
        break
BID = '\n'.join(parts)
extent = dict(start_lib_page=start_pg, start_body_offset=start_off,
              end_lib_page=end_pg, end_body_offset_exclusive=end_off,
              kitab_salat_heading_lib_page=end_pg, kitab_salat_heading_offset=kitab_salat_off,
              concat_length=len(BID))
offs = [p[0] for p in page_off]


def locate(ci):
    """concat offset -> (lib_page, printed_page, body_offset)"""
    k = bisect.bisect_right(offs, ci) - 1
    co, lib, printed, base = page_off[k]
    return lib, printed, base + ci - co


# ---------- 2. headings -------------------------------------------------------
heading_ranges = []   # (start,end, text, level)
pos = 0
for line in BID.replace('\n', '\r').split('\r'):
    ls, le = pos, pos + len(line)
    pos = le + 1
    n = normalize(line)
    if not n:
        continue
    toks = n.split()
    is_span = '<span' in line
    if toks[0] in ('كتاب', 'باب', 'فصل') and (is_span or len(toks) <= 12):
        if is_span and len(toks) > 12:     # title span carrying matn: only «فصل»
            mm = re.search(r'فصل', line)
            heading_ranges.append((ls, ls + mm.end(), 'فصل', 'fasl'))
        else:
            txt = re.sub(r'<[^>]*>', '', line).strip(' =')
            heading_ranges.append((ls, le, txt, {'كتاب': 'kitab', 'باب': 'bab', 'فصل': 'fasl'}[toks[0]]))


def heading_index(ci):
    """index of last heading starting at or before ci (section id)"""
    k = -1
    for i, h in enumerate(heading_ranges):
        if h[0] <= ci:
            k = i
    return k


btoks_all = tokens_with_spans(BID)
btoks = [t for t in btoks_all if not any(h[0] <= t[1] < h[1] for h in heading_ranges)]
btok_sec = [heading_index(t[1]) for t in btoks]
B = [t[0] for t in btoks]

# ---------- 3. HID units ------------------------------------------------------
units = []
for line in open(HID_FILE, encoding='utf-8'):
    line = line.rstrip('\n')
    if not line.strip():
        continue
    f = line.split('\t')
    units.append({'hid_id': f[0], 'matn': f[1], 'prov_page': f[2] if len(f) > 2 else None})
hid_meta = {}
for r in con.execute("select id, vol, page_start, page_end from masala where work='HID'"):
    hid_meta[r[0]] = r[1:]
CONJ = {'و', 'ف'}


def hid_tokens(text):
    """normalized tokens; a standalone conjunction (from «و … X») is glued to the next token"""
    out, carry = [], ''
    for t in normalize(text).split():
        if t in CONJ:
            carry += t
            continue
        out.append(carry + t)
        carry = ''
    if carry:
        out.append(carry)
    return out


for u in units:
    u['ntoks'] = hid_tokens(u['matn'])

# S1 printed pages
s1pp = {r[0]: (r[1], r[2]) for r in con.execute(
    "select lib_page_id, vol, printed_page from page where source_id='S1' and lib_page_id between 1 and 60")}


def hid_ref(u):
    m = hid_meta.get(u['hid_id'])
    if m and m[1] is not None:   # HID rows store S1 lib_page_id in page_start/page_end
        return {'vol': m[0], 'page_start': s1pp[m[1]][1], 'page_end': s1pp[m[2]][1],
                'lib_page_start': m[1], 'lib_page_end': m[2]}
    if u['prov_page']:
        v, pp = s1pp[int(u['prov_page'])]
        return {'vol': v, 'page_start': pp, 'page_end': pp, 'lib_page': int(u['prov_page'])}
    return None


# ---------- 4./5. alignment, spans, scores (iterative) -------------------------
def score_pair(htoks, btoks_):
    tr = difflib.SequenceMatcher(None, htoks, btoks_, autojunk=False).ratio()
    cr = difflib.SequenceMatcher(None, ' '.join(htoks), ' '.join(btoks_), autojunk=False).ratio()
    return round((tr + cr) / 2, 4), round(tr, 4), round(cr, 4)


def run_alignment(active):
    """align B against the HID tokens of the active units; returns (assign, span, matched_tok, stray)"""
    H, Hu = [], []
    for ui in active:
        H += units[ui]['ntoks']
        Hu += [ui] * len(units[ui]['ntoks'])
    sm = difflib.SequenceMatcher(None, B, H, autojunk=False)
    assign = [None] * len(B)
    matched_tok = [0] * len(units)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                assign[i1 + k] = Hu[j1 + k]
                matched_tok[Hu[j1 + k]] += 1
        elif tag == 'replace':
            for k in range(i1, i2):
                assign[k] = Hu[j1 + (k - i1) * (j2 - j1) // (i2 - i1)]
    # keep only the densest cluster of each unit's assigned tokens (guards against a
    # stray common word matched far away inflating the span)
    byunit = {}
    for k, ui in enumerate(assign):
        if ui is not None:
            byunit.setdefault(ui, []).append(k)
    span, stray = {}, 0
    for ui, ks in byunit.items():
        maxgap = max(5, len(units[ui]['ntoks']))
        clusters, cur = [], [ks[0]]
        for k in ks[1:]:
            if k - cur[-1] > maxgap:
                clusters.append(cur); cur = [k]
            else:
                cur.append(k)
        clusters.append(cur)
        best = max(clusters, key=len)
        for c in clusters:
            if c is not best:
                for k in c:
                    assign[k] = None; stray += 1
        span[ui] = (best[0], best[-1])
    return assign, span, matched_tok, stray


# pass 1..n: units scoring < THRESH are removed from the HID sequence and the
# alignment is recomputed, so their words cannot pull BID words away from the
# neighbouring units (e.g. HID «وسؤر الكلب نجس» absent from BID).
active = list(range(len(units)))
dropped = set()
for it in range(5):
    assign, span, matched_tok, stray_released = run_alignment(active)
    newly = set()
    for ui in active:
        u = units[ui]
        if ui in span:
            a, b = span[ui]
            seg = B[a:b + 1]
            u['score'], u['tok_ratio'], u['char_ratio'] = score_pair(u['ntoks'], seg)
            u['status'] = 'exact' if seg == u['ntoks'] else ('approx' if u['score'] >= THRESH else 'unmatched')
        else:
            u['score'], u['tok_ratio'], u['char_ratio'], u['status'] = 0.0, 0.0, 0.0, 'unmatched'
        if u['status'] == 'unmatched':
            newly.add(ui)
            u['dropped_in_pass'] = it + 1
    if not newly:
        break
    dropped |= newly
    active = [ui for ui in active if ui not in dropped]
for ui in dropped:
    span.pop(ui, None)
n_passes = it + 1
# tokens inside a kept unit span all belong to it
owner = [None] * len(B)
overlaps = []
for ui, (a, b) in sorted(span.items()):
    for k in range(a, b + 1):
        if owner[k] is not None and owner[k] != ui:
            overlaps.append((owner[k], ui))
        owner[k] = ui

# ---------- 6. segmentation ---------------------------------------------------
segs = []   # dict(kind, ui, tok_a, tok_b)
k = 0
while k < len(B):
    if owner[k] is not None:
        ui = owner[k]
        a = k
        while k + 1 < len(B) and owner[k + 1] == ui:
            k += 1
        segs.append({'kind': 'matched', 'ui': ui, 'a': a, 'b': k})
    else:
        a = k
        while k + 1 < len(B) and owner[k + 1] is None and btok_sec[k + 1] == btok_sec[a]:
            k += 1
        segs.append({'kind': 'gap', 'ui': None, 'a': a, 'b': k})
    k += 1
# split matched segs crossing a heading? (report only)
cross = [s for s in segs if s['kind'] == 'matched' and btok_sec[s['a']] != btok_sec[s['b']]]
# absorb short gaps
final = []
for i, s in enumerate(segs):
    if s['kind'] == 'gap' and s['b'] - s['a'] + 1 <= ABSORB:
        if final and final[-1]['kind'] != 'gap_kept' and btok_sec[final[-1]['b']] == btok_sec[s['a']]:
            final[-1]['b'] = s['b']; final[-1].setdefault('absorbed', []).append((s['a'], s['b']))
            continue
        nxt = segs[i + 1] if i + 1 < len(segs) else None
        if nxt and nxt['kind'] == 'matched' and btok_sec[nxt['a']] == btok_sec[s['a']]:
            nxt['a'] = s['a']; nxt.setdefault('absorbed', []).append((s['a'], s['b']))
            continue
        if final and btok_sec[final[-1]['b']] == btok_sec[s['a']]:
            final[-1]['b'] = s['b']; final[-1].setdefault('absorbed', []).append((s['a'], s['b']))
            continue
    if s['kind'] == 'gap':
        s['kind'] = 'bid_only'
    final.append(s)

# ids: NN from HID unit id (field 3), BID-only inherit preceding NN in same section else following
def hid_nn(ui):
    return units[ui]['hid_id'].split('.')[2]
for i, s in enumerate(final):
    if s['kind'] == 'matched':
        s['nn'] = hid_nn(s['ui'])
for i, s in enumerate(final):
    if s['kind'] == 'bid_only':
        nn = None
        for j in range(i - 1, -1, -1):
            if final[j]['kind'] == 'matched' and btok_sec[final[j]['b']] == btok_sec[s['a']]:
                nn = final[j]['nn']; break
        if nn is None:
            for j in range(i + 1, len(final)):
                if final[j]['kind'] == 'matched':
                    nn = final[j]['nn']; break
        if nn is None:
            for j in range(i - 1, -1, -1):
                if final[j]['kind'] == 'matched':
                    nn = final[j]['nn']; break
        s['nn'] = nn
seqc = {}
masail = []
for order, s in enumerate(final, 1):
    seqc[s['nn']] = seqc.get(s['nn'], 0) + 1
    bid_id = f"BID.01.{s['nn']}.{seqc[s['nn']]:04d}"
    cs, ce = btoks[s['a']][1], btoks[s['b']][2]
    sec = btok_sec[s['a']]
    # bab / fasl context
    bab = fasl = None
    for h in heading_ranges[:sec + 1]:
        if h[3] == 'bab':
            bab, fasl = h[2], None
        elif h[3] == 'fasl':
            fasl = h[2]
        elif h[3] == 'kitab':
            bab = fasl = None
    ls, ps, os_ = locate(cs)
    le, pe, oe = locate(ce - 1)
    rec = {'id': bid_id, 'seq': seqc[s['nn']], 'order': order, 'kind': s['kind'], 'bid_only': s['kind'] == 'bid_only',
           'hid_id': units[s['ui']]['hid_id'] if s['ui'] is not None else None,
           'kitab': 'كتاب الطَّهَارَة', 'bab': bab, 'fasl': fasl,
           'concat_char_start': cs, 'concat_char_end': ce,
           'lib_page_start': ls, 'lib_page_end': le, 'printed_page_start': ps, 'printed_page_end': pe,
           'body_char_start': os_, 'body_char_end': oe + 1,
           'n_tokens': s['b'] - s['a'] + 1,
           'crosses_heading': s in cross,
           'matn_text': re.sub(r'<[^>]*>', '', BID[cs:ce]),
           'markup_removed': '<' in BID[cs:ce]}
    assert '<' not in rec['matn_text'], rec
    if s['ui'] is not None:
        units[s['ui']]['bid_id'] = bid_id
        units[s['ui']]['seg'] = rec
    masail.append(rec)

# ---------- outputs ------------------------------------------------------------
os.makedirs(f'{ROOT}/data/works/BID', exist_ok=True)
suffix = '.provisional' if PROVISIONAL else ''
align = []
for ui, u in enumerate(units):
    rec = {'hid_id': u['hid_id'], 'hid_matn': u['matn'], 'hid_ref': hid_ref(u),
           'status': u['status'], 'score': u['score'],
           'tok_ratio': u.get('tok_ratio'), 'char_ratio': u.get('char_ratio'),
           'hid_tokens': len(u['ntoks']), 'matched_tokens': matched_tok[ui],
           'bid_id': u.get('bid_id')}
    if 'seg' in u:
        sg = u['seg']
        rec.update({'bid_text': sg['matn_text'], 'concat_char_start': sg['concat_char_start'],
                    'concat_char_end': sg['concat_char_end'],
                    'bid_ref': {'lib_page_start': sg['lib_page_start'], 'lib_page_end': sg['lib_page_end'],
                                'printed_page_start': sg['printed_page_start'],
                                'printed_page_end': sg['printed_page_end']}})
    align.append(rec)
meta = {'task': 'T2.3', 'hid_file': HID_FILE, 'provisional_hid': PROVISIONAL,
        'method': 'difflib.SequenceMatcher(autojunk=False) global monotonic alignment over normalized tokens; '
                  'see scripts/align_bid_hid.py docstring',
        'threshold': THRESH, 'absorb_gap_tokens': ABSORB, 'extent': extent,
        'page_break_marker': '\\n (between page bodies in concat text)',
        'headings': [{'concat_start': h[0], 'concat_end': h[1], 'text': h[2], 'level': h[3]} for h in heading_ranges]}
json.dump({'meta': meta, 'pairs': align}, open(f'{ROOT}/data/works/BID/01-tahara.align{suffix}.json', 'w',
                                              encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump({'meta': meta, 'masail': masail}, open(f'{ROOT}/data/works/BID/01-tahara.masail{suffix}.json', 'w',
                                                 encoding='utf-8'), ensure_ascii=False, indent=1)
open(f'{ROOT}/data/works/BID/01-tahara.concat{suffix}.txt', 'w', encoding='utf-8').write(BID)

cnt = {}
for u in units:
    cnt[u['status']] = cnt.get(u['status'], 0) + 1
print('extent', extent)
print('HID units', len(units), cnt)
print('passes', n_passes, 'stray tokens released', stray_released, 'overlapping unit pairs', len(set(overlaps)))
print('BID segments', len(masail), 'bid_only', sum(m['bid_only'] for m in masail),
      'crossing heading', len(cross))

if WRITE_DB:
    assert not PROVISIONAL
    with con:
        con.execute("delete from masala where work='BID' and id like 'BID.01.%'")
        for m in masail:
            con.execute("insert into masala(id, work, kitab, bab, fasl, seq, vol, page_start, page_end, source_id,"
                        " matn_text, sharh_text, char_start, char_end, bid_masala_id, review_status)"
                        " values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        # conventions mirrored from the HID rows of T2.2: kitab='01',
                        # page_start/page_end = lib_page_id, char_* = offsets in the
                        # concatenated kitab text (data/works/BID/01-tahara.concat.txt)
                        (m['id'], 'BID', '01', m['bab'], m['fasl'], m['seq'], None,
                         m['lib_page_start'], m['lib_page_end'], 'S2', m['matn_text'], None,
                         m['concat_char_start'], m['concat_char_end'], None, 'auto'))
        n = 0
        for u in units:
            cur = con.execute("update masala set bid_masala_id=? where id=? and work='HID'",
                              (u.get('bid_id'), u['hid_id']))
            n += cur.rowcount
    print('DB: inserted', len(masail), 'BID rows; updated', n, 'HID rows')
