#!/usr/bin/env python3
"""T2.2: تقسيم كتاب فقهي من الهداية (S1) إلى مسائل — PLAN §4.2 الخطوة 2.

usage: segment_hid.py [--kitab 1] [--slug 01-tahara] [--reviewed] [--no-db]

قواعد التقسيم موثقة في docs/segmentation.md. الاستثناءات اليدوية في
scripts/segment_hid_exceptions.json (مفتاحها: lib_page_id:إزاحة علامة التنصيص داخل page.body،
مع بادئة نصية للتحقق؛ إن لم تطابق البادئة توقف السكربت).

النص لا يُغيَّر: kitab_text = "\\n".join(page.body) لصفحات الكتاب بترتيبها (فاصل "\\n" واحد
بين الصفحات لا غير)، وكل الإزاحات char_start/char_end نسبة إليه، والنصوص المخرجة شرائح حرفية منه.
"""
import argparse, hashlib, json, pathlib, re, sqlite3, sys

R = pathlib.Path(__file__).resolve().parents[1]
SRC = 'S1'

# ---------------------------------------------------------------- القرائن
BLESS = '﵊ﷺ'
# قرينة الحديث: «قوله/قال ﵊» وبعدها حتى 25 محرفًا بلا نقطة ولا فقرة ولا تنصيص
# (يغطي: لقوله ﵊: / وقوله ﵊ في البحر / لقوله ﵊ لعائشة ﵂ / فقال ﵊ / وقال ﵊)
RX_HADITH_QAWL = re.compile(r'(?:قوله|قال)\s*[' + BLESS + r'][^."\r\n]{0,25}$')
# «وقال/فقال» بلا اسم بعدها مباشرة قبل التنصيص (رواية مقول النبي ﵊ في سياق فعل نبوي)
RX_WAQALA = re.compile(r'(?:^|\s)[وف]قال\s*:?\s*$')
# «قال في آخر الحديث» ونحوه
RX_HADITH_WORD = re.compile(r'قال\s+في\s+آخر\s+(?:الحديث|الخبر)\s*:?\s*$')
# «قال:» المجردة (صيغة إيراد المتن) — إلا إذا سبقها خلال 40 محرفًا ذكرُ النبي ﷺ (سؤال وجواب)
RX_QALA_BARE = re.compile(r'(?:^|[\s.،])قال\s*:?\s*$')
RX_PROPHET = re.compile(r'[' + BLESS + r']|رسول الله|النبي')
# «وذكر منها "…"»: حكاية بعض لفظ الحديث المذكور قبلها
RX_DHAKARA = re.compile(r'ذكر\s+منها\s*:?\s*$')
# أثر: قول صحابي/تابعي مصرح به قبل التنصيص
RX_ATHAR = re.compile(r'(?:قول|عن|قال)\s+(?:علي|عمر|عائشة|ابن عباس|ابن مسعود|ابن عمر|أنس|إبراهيم)[^."\r\n]{0,25}$')
# بدايات جزء المتن التي تدل على أنه تتمة جملة متنية سابقة لا مسألة جديدة
RX_CONT_START = re.compile(r'^\s*(?:إلا|إلى|أو\s|أو$|حتى|عند|عندهما|بماء|بطعام|وقال\s+(?:أبو|محمد|زفر|الشافعي|مالك)|وقالا|وكذا\s+عند|وهذا\s+عند|وعندهما|وعنده)')
# فواتح جمل الشرح المرشحة لتوليد المسائل F1.M4.T1 (خارج علامتي المتن)
RX_TAWLID = re.compile(r'(?:(?<=[\s.،\r\n])|^)(ولو|وإن|فإن|وكذا|وعلى هذا)\s')


def load(kitab_no):
    toc = json.loads((R / 'data/works/HID/toc.json').read_text(encoding='utf-8'))
    kutub = toc['kutub']
    k = next(x for x in kutub if x['no'] == kitab_no)
    nxt = next((x for x in kutub if x['no'] == kitab_no + 1), None)
    db = sqlite3.connect(R / 'data/kashshaf.db', timeout=60)
    pages = db.execute('select lib_page_id,vol,printed_page,body from page where source_id=? '
                       'and lib_page_id between ? and ? order by lib_page_id',
                       (SRC, k['page_id'], k['page_end'] + (1 if nxt and nxt['page_id'] == k['page_end'] else 0))).fetchall()
    titles = db.execute('select title_id,page_lib_id,parent,title from toc where source_id=? order by title_id', (SRC,)).fetchall()
    db.close()
    return k, nxt, pages, titles


def build_text(pages):
    """kitab_text وجدول بدايات الصفحات."""
    parts, starts, pos = [], [], 0
    for lib, vol, pr, body in pages:
        starts.append((pos, lib, vol, pr))
        parts.append(body)
        pos += len(body) + 1
    return '\n'.join(parts), starts


def page_at(starts, off):
    cur = starts[0]
    for s in starts:
        if s[0] <= off:
            cur = s
        else:
            break
    return cur  # (start, lib, vol, printed)


def descendants(titles, root_id):
    kids = {}
    for tid, p, par, t in titles:
        kids.setdefault(par, []).append((tid, p, par, t))
    out = []
    def walk(i):
        for ch in kids.get(i, []):
            out.append(ch); walk(ch[0])
    walk(root_id)
    return sorted(out)


def kind(t):
    t = t.strip()
    for k in ('كتاب', 'باب', 'فصل'):
        if t.startswith(k):
            return k
    return 'other'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kitab', type=int, default=1)
    ap.add_argument('--slug', default='01-tahara')
    ap.add_argument('--reviewed', action='store_true', help="review_status='reviewed' لكل المسائل")
    ap.add_argument('--no-db', action='store_true')
    a = ap.parse_args()
    kno = a.kitab
    k, nxt, pages, titles = load(kno)
    text, starts = build_text(pages)
    pstart = {lib: s for s, lib, _, _ in starts}

    exc = json.loads((R / 'scripts/segment_hid_exceptions.json').read_text(encoding='utf-8'))
    exc_k = {e['key']: e for e in exc.get(f'HID.{kno:02d}', []) }
    used_exc = set()

    def gkey(off):
        s, lib, _, _ = page_at(starts, off)
        return f'{lib}:{off - s}'

    def exc_for(off, kinds):
        e = exc_k.get(gkey(off))
        if e and e['kind'] in kinds:
            pre = e.get('prefix', '')
            if not text.startswith(pre, off):
                sys.exit(f'exception {e["key"]} prefix mismatch: {text[off:off+30]!r}')
            used_exc.add(e['key'])
            return e
        return None

    # ----- نهاية الكتاب: عنوان الكتاب التالي إن وقع في الصفحات المحمّلة
    end = len(text)
    if nxt:
        m = re.search(r"<span data-type='title' id=toc-%d>" % nxt['title_id'], text)
        if m:
            end = m.start()
        else:
            m = re.search(re.escape(nxt['title']), text)
            if m:
                end = m.start()
    # ----- الوحدات (أبواب/فصول) من الفهرس
    heads = []
    for tid, p, par, t in descendants(titles, k['title_id']):
        if kind(t) not in ('باب', 'فصل'):
            continue
        m = re.search(r"<span data-type='title' id=toc-%d>(.*?)</span>" % tid, text)
        if m:
            hs, he, how = m.start(), m.end(), 'span'
        else:
            plain = t.replace(':', '').replace('  ', ' ')
            m = re.search(r'(?:^|[\r\n])(' + re.escape(plain) + r')\s*(?=[\r\n])', text)
            if m:
                hs, he, how = m.start(1), m.end(1), 'plain'
            elif p == k['page_id']:
                # عنوان افتراضي من الفهرس، لا يظهر في النص: يبدأ بعد عنوان الكتاب
                km = re.search(r"<span data-type='title' id=toc-%d>.*?</span>" % k['title_id'], text)
                hs = he = km.end() if km else 0; how = 'virtual'
            else:
                hs = he = pstart[p]; how = 'virtual'
        heads.append(dict(title_id=tid, title=t, kind=kind(t), parent=par, hs=hs, he=he, how=how, page=p))
    heads.sort(key=lambda h: h['hs'])
    # اسم الباب لكل وحدة
    bab_of = {}
    for h in heads:
        if h['kind'] == 'باب':
            bab_of[h['title_id']] = h['title']
    km = re.search(r"<span data-type='title' id=toc-%d>.*?</span>" % k['title_id'], text)
    k_body_start = km.end() if km else 0
    units = []
    if heads and heads[0]['hs'] > k_body_start and text[k_body_start:heads[0]['hs']].strip():
        units.append(dict(no=0, title=None, bab=None, fasl=None, s=k_body_start, how='none'))
    for i, h in enumerate(heads, 1):
        bab = h['title'] if h['kind'] == 'باب' else bab_of.get(h['parent'])
        fasl = h['title'] if h['kind'] == 'فصل' else None
        units.append(dict(no=i, title=h['title'], bab=bab, fasl=fasl, s=h['he'], how=h['how'], title_id=h['title_id']))
    for i, u in enumerate(units):
        nxt_s = None
        if i + 1 < len(units):
            nh = next(h for h in heads if h['title_id'] == units[i + 1]['title_id'])
            nxt_s = nh['hs']
        u['e'] = nxt_s if nxt_s is not None else end
        # تخطَّ الفواصل بعد العنوان
        while u['s'] < u['e'] and text[u['s']] in '\r\n \t':
            u['s'] += 1

    # ----- علامات التنصيص
    qpos = [i for i in range(len(text[:end])) if text[i] == '"']
    quotes = []  # (open, close) ؛ open قد يكون افتراضيًّا
    i = 0
    virtual_opens = [e for e in exc_k.values() if e['kind'] == 'virtual_open']
    vo_offsets = {}
    for e in virtual_opens:
        lib, off = map(int, e['key'].split(':'))
        go = pstart[lib] + off
        if not text.startswith(e['prefix'], go):
            sys.exit(f'virtual_open {e["key"]} prefix mismatch: {text[go:go+30]!r}')
        vo_offsets[e['close_key']] = (go, e)
        used_exc.add(e['key'])
    while i < len(qpos):
        o = qpos[i]
        ck = gkey(o)
        if ck in vo_offsets:  # علامة إغلاق يتيمة: افتتاح افتراضي
            go, e = vo_offsets[ck]
            quotes.append(dict(o=go - 1, c=o, virtual_open=True, vreason=e['reason']))
            i += 1; continue
        if i + 1 >= len(qpos):
            sys.exit(f'unpaired quote at {gkey(o)}: {text[o-30:o+30]!r}')
        quotes.append(dict(o=o, c=qpos[i + 1], virtual_open=False))
        i += 2
    # ----- التصنيف
    prev_c = None
    prev_type = None
    for q in quotes:
        o, c = q['o'], q['c']
        q['text'] = text[o + 1:c]
        u = next((u for u in units if u['s'] <= o + 1 < u['e'] or (u['s'] <= o + 1 and o + 1 <= u['e'])), None)
        lead_from = max(prev_c + 1 if prev_c is not None else 0, u['s'] if u else 0)
        lead = text[lead_from:o + 1] if q['virtual_open'] else text[lead_from:o]
        if q['virtual_open']:
            lead = text[lead_from:o + 1]
        q['lead'] = lead
        para_lead = re.split(r'[\r\n]', lead)[-1] if re.search(r'[\r\n]', lead) else None
        q['para_start'] = (para_lead is not None and para_lead.strip() == '') or (lead.strip() == '' and lead_from == (u['s'] if u else -1))
        q['para_lead'] = para_lead
        tail = lead[-60:]
        e = exc_for(o if not q['virtual_open'] else o + 1, ('classify',))
        if e:
            q['type'], q['rule'] = e['type'], 'EXC:' + e['reason']
        elif RX_HADITH_QAWL.search(tail):
            q['type'], q['rule'] = 'hadith', 'H1 قوله/قال ﵊'
        elif RX_HADITH_WORD.search(tail):
            q['type'], q['rule'] = 'hadith', 'H2 في آخر الحديث'
        elif RX_WAQALA.search(tail) and (RX_PROPHET.search(text[max(0, o - 120):o]) or
                                         (prev_type == 'hadith' and len(lead) < 80 and not re.search(r'[\r\n]', lead))):
            q['type'], q['rule'] = 'hadith', 'H3 وقال/فقال في سياق نبوي'
        elif RX_DHAKARA.search(tail) and prev_type == 'hadith':
            q['type'], q['rule'] = 'hadith', 'H5 «وذكر منها» حكاية لفظ الحديث السابق'
        elif RX_ATHAR.search(tail):
            q['type'], q['rule'] = 'athar', 'A1 قول صحابي'
        elif RX_QALA_BARE.search(tail) and RX_PROPHET.search(re.split(r'[.\r\n]', tail)[-1][-45:]):
            q['type'], q['rule'] = 'hadith', 'H4 قال: بعد ذكر النبي (سؤال وجواب)'
        elif RX_QALA_BARE.search(tail):
            q['type'], q['rule'] = 'matn', 'M1 قال:'
        elif q['para_start']:
            q['type'], q['rule'] = 'matn', 'M2 أول الفقرة/الوحدة'
        else:
            q['type'], q['rule'] = 'matn', 'M3 تنصيص داخل الشرح بلا قرينة حديث'
        q['unit'] = u['no'] if u else None
        prev_c = c
        prev_type = q['type']

    # ----- تجميع المسائل
    masail = []
    for u in units:
        uq = [q for q in quotes if q['unit'] == u['no'] and u['s'] <= q['o'] + (1 if q['virtual_open'] else 0) and q['c'] < u['e']]
        cur = None
        last_matn = None
        for q in uq:
            if q['type'] != 'matn':
                if cur:
                    cur['quotes'].append(q)
                else:
                    pending = u.setdefault('pending', []); pending.append(q)
                continue
            # جديد أم تتمة؟
            e = exc_for(q['o'] if not q['virtual_open'] else q['o'] + 1, ('join', 'split'))
            if e:
                is_new = e['kind'] == 'split'; jrule = 'EXC:' + e['reason']
            elif cur is None:
                is_new, jrule = True, 'first in unit'
            elif re.match(r"\s*ثم\s", q["text"]):
                # قرار الباحث (14-11-2026): «ثم» تفريع داخل المسألة، ولا تُفرد إلا إذا تغير الموضوع (باستثناء split يدوي)
                is_new, jrule = False, 'J6 ثم: تفريع داخل المسألة'
            elif RX_QALA_BARE.search(q['lead'][-60:]) or q['para_start']:
                is_new, jrule = True, 'J1 قال:/أول فقرة'
            elif last_matn is not None and len(last_matn['text'].strip()) <= 4:
                is_new, jrule = False, 'J2 الجزء السابق حرف عطف/نفي قصير'
            elif RX_CONT_START.search(q['text']):
                is_new, jrule = False, 'J3 بداية تتمة (إلا/إلى/أو/وقال فلان/عنده…)'
            elif not re.match(r"\s*[وف]", q["text"]):
                is_new, jrule = False, 'J4 لا يبدأ بواو/فاء: تتمة جملة'
            else:
                is_new, jrule = True, 'J5 جملة متنية جديدة تبدأ بواو/فاء'
            q['join_rule'] = jrule
            q['skip'] = 0
            if e and e.get('skip_prefix'):
                if not q['text'].startswith(e['skip_prefix']):
                    sys.exit(f'skip_prefix mismatch at {e["key"]}')
                q['skip'] = len(e['skip_prefix'])
            if is_new:
                if cur is None:
                    start = u['s']
                else:
                    m = RX_QALA_BARE.search(q['lead'])
                    if m and q['lead'][m.end():].strip() == '':
                        rel = m.start() + (1 if q['lead'][m.start()] in ' .،\r\n\t' else 0)
                        start = (q['o'] + 1 if q['virtual_open'] else q['o']) - len(q['lead']) + rel
                    elif q['para_start'] and q['para_lead'] is not None:
                        start = q['o'] - len(q['para_lead']) + (1 if q['virtual_open'] else 0)
                    else:
                        start = q['o'] + (1 if q['virtual_open'] else 0)
                    if q['skip']:
                        start = q['o'] + 1 + q['skip']
                    cur['end'] = start
                cur = dict(unit=u, start=start, matn=[q], quotes=[q], join=[jrule])
                if u.get('pending'):
                    cur['quotes'] = u.pop('pending') + cur['quotes']
                masail.append(cur)
            else:
                cur['matn'].append(q); cur['quotes'].append(q); cur['join'].append(jrule)
            last_matn = q
        if cur is None:
            # وحدة بلا متن
            cur = dict(unit=u, start=u['s'], matn=[], quotes=u.pop('pending', []), join=[])
            masail.append(cur)
        cur['end'] = u['e']
    # مقاطع متن خارج علامات التنصيص (استثناء matn_span بقرار الباحث، مثل الآية في صدر الكتاب)
    spans = []
    for ek, e in exc_k.items():
        if e['kind'] != 'matn_span':
            continue
        lib, po = map(int, ek.split(':'))
        base = next(st[0] for st in starts if st[1] == lib)
        o = base + po
        if not text.startswith(e['prefix'], o):
            sys.exit(f'matn_span {ek} prefix mismatch: {text[o:o+30]!r}')
        ce = (text.index(e['until'], o) + len(e['until'])) if e.get('until') else o + len(e['prefix'])
        spans.append(dict(text=text[o:ce], char_start=o, char_end=ce, page=lib, virtual_open=False, matn_span=e['reason']))
        used_exc.add(ek)
    # تقليم المسافات في آخر كل مسألة (تبقى ضمن الشريحة الحرفية بلا تغيير)
    out = []
    seqs = {}
    for m in masail:
        u = m['unit']
        s, e = m['start'], m['end']
        while e > s and text[e - 1] in '\r\n \t':
            e -= 1
        seqs[u['no']] = seqs.get(u['no'], 0) + 1
        seq = seqs[u['no']]
        mid = f'HID.{kno:02d}.{u["no"]:02d}.{seq:04d}'
        ps, pe = page_at(starts, s), page_at(starts, max(s, e - 1))
        frags = [dict(text=q['text'][q.get('skip', 0):], char_start=q['o'] + 1 + q.get('skip', 0), char_end=q['c'],
                      page=page_at(starts, q['o'] + 1)[1], virtual_open=q['virtual_open'],
                      **({'skipped_prefix': q['text'][:q['skip']]} if q.get('skip') else {})) for q in m['matn']]
        frags = sorted(frags + [sp for sp in spans if s <= sp['char_start'] < e], key=lambda f: f['char_start'])
        flags = []
        if u['how'] == 'virtual' and seq == 1:
            flags.append(f'heading_virtual: عنوان «{u["title"]}» من فهرس الشاملة ولا يظهر في نص الصفحة')
        if seq == 1:
            pre_end = (m['matn'][0]['o'] if m['matn'] else e)
            pre = text[s:pre_end]
            pre_c = re.sub(r'(?:^|\s)قال\s*:?\s*$', '', pre).strip()
            if pre_c:
                flags.append('preamble: نص قبل أول متن في الوحدة: ' + pre_c[:60])
        if not m['matn']:
            flags.append('no_matn: وحدة/مسألة بلا متن منصوص')
        if len(frags) > 1:
            flags.append(f'matn_fragments={len(frags)}')
        for q in m['matn']:
            if q['virtual_open']:
                flags.append('virtual_open: ' + q['vreason'])
            if q.get('skip'):
                flags.append('quote_misplaced: بداية علامة التنصيص في المصدر تشمل «%s» وهو من الشرح؛ بدأت المسألة بعده (الإزاحة فقط، النص لم يُغيَّر)' % q['text'][:q['skip']].strip())
        # شروح بلا متن: فقرات تبدأ بلا متن، وقرائن التوليد خارج التنصيص
        body = text[s:e]
        cands = []
        inq = intervals = [(q['o'] - s, q['c'] - s) for q in m['quotes']]
        for mm in RX_TAWLID.finditer(body):
            p = mm.start(1)
            if any(a <= p <= b for a, b in intervals):
                continue
            # تجاوز «ثم» و«فإن/وإن» داخل جملة تعليل قصيرة؟ نُبقيها مرشحة فقط
            cands.append(dict(cue=mm.group(1), char_start=s + p, snippet=body[p:p + 50]))
        paras = []
        for mm in re.finditer(r'\r([^\r]*)', body):
            ptxt = mm.group(1)
            pa = s + mm.start(1)
            if not any(q['o'] >= pa and q['o'] < pa + 8 for q in m['matn']) and not re.match(r'\s*قال\s*:?\s*"', ptxt):
                paras.append(dict(char_start=pa, snippet=ptxt[:50]))
        quotes_out = [dict(text=q['text'], type=q['type'], rule=q['rule'], char_start=q['o'] + 1, char_end=q['c'],
                           **({'join_rule': q['join_rule']} if q.get('join_rule') else {})) for q in m['quotes']]
        out.append(dict(
            id=mid, kitab=k['title'], bab=u['bab'], fasl=u['fasl'], unit_no=u['no'], seq=seq,
            vol=ps[2], page_start=ps[1], page_end=pe[1], printed_start=ps[3], printed_end=pe[3],
            matn_text=' … '.join(f['text'] for f in frags), matn_fragments=frags,
            sharh_text=text[s:e], char_start=s, char_end=e,
            quotes=quotes_out, flags=flags,
            tawlid_candidates=[dict(c, tag='F1.M4.T1') for c in cands],
            sharh_paragraphs=[dict(p, tag='F1.M4.T1?') for p in paras],
        ))
    unused = set(exc_k) - used_exc
    if unused:
        print('WARNING unused exceptions:', sorted(unused), file=sys.stderr)
    # ----- الكتابة
    wd = R / 'data/works/HID'
    meta = dict(source=SRC, kitab_no=kno, kitab=k['title'], text_def='kitab_text = "\\n".join(page.body) للصفحات %d..%d، مقطوعًا عند عنوان الكتاب التالي' % (pages[0][0], pages[-1][0]),
                kitab_text_len=end, kitab_text_sha1=hashlib.sha1(text[:end].encode()).hexdigest(),
                units=[dict(no=u['no'], title=u['title'], bab=u['bab'], fasl=u['fasl'], heading=u['how'], char_start=u['s'], char_end=u['e']) for u in units])
    (wd / f'{a.slug}.masail.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    (wd / f'{a.slug}.meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')
    with open(wd / f'{a.slug}.matn.txt', 'w', encoding='utf-8') as f:
        for m in out:
            f.write(m['id'] + '\t' + m['matn_text'].replace('\r', ' ').replace('\n', ' ') + '\n')
    if not a.no_db:
        db = sqlite3.connect(R / 'data/kashshaf.db', timeout=60)
        with db:
            db.execute("delete from masala where work='HID' and kitab=?", (f'{kno:02d}',))
            db.execute("delete from masala where work='HID' and id like ?", (f'HID.{kno:02d}.%',))
            for m in out:
                db.execute('insert into masala(id,work,kitab,bab,fasl,seq,vol,page_start,page_end,source_id,matn_text,sharh_text,char_start,char_end,review_status) '
                           'values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                           (m['id'], 'HID', f'{kno:02d}', m['bab'], m['fasl'], m['seq'], m['vol'], m['page_start'], m['page_end'], SRC,
                            m['matn_text'], m['sharh_text'], m['char_start'], m['char_end'], 'reviewed' if a.reviewed else 'auto'))
        db.close()
    n_h = sum(1 for m in out for q in m['quotes'] if q['type'] == 'hadith')
    print(f'{len(out)} masail, {len(units)} units, quotes={sum(len(m["quotes"]) for m in out)} hadith={n_h}')


if __name__ == '__main__':
    main()
