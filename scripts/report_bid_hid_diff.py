"""T2.3 — write reports/bid-hid-diff.md from data/works/BID/01-tahara.{align,masail}.json.

Usage: python3 scripts/report_bid_hid_diff.py [--provisional] [--sample]
  --sample : print the 20 seeded random pairs for manual spot-check and exit.
Spot-check verdicts are read from data/works/BID/01-tahara.spotcheck.json
({"seed":..,"verdicts":{hid_id: "correct"|"wrong: note"}}).
"""
import difflib, json, os, random, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize_ar import normalize

ROOT = '/home/claude/kashshaf'
suf = '.provisional' if '--provisional' in sys.argv else ''
A = json.load(open(f'{ROOT}/data/works/BID/01-tahara.align{suf}.json', encoding='utf-8'))
M = json.load(open(f'{ROOT}/data/works/BID/01-tahara.masail{suf}.json', encoding='utf-8'))
meta, pairs, masail = A['meta'], A['pairs'], M['masail']
SEED = 20261114

matched = [p for p in pairs if p['status'] in ('exact', 'approx')]
rng = random.Random(SEED)
sample = rng.sample(matched, min(20, len(matched)))
if '--sample' in sys.argv:
    for p in sample:
        print('==', p['hid_id'], p['status'], p['score'], p['bid_id'])
        print('  HID:', p['hid_matn'])
        print('  BID:', p['bid_text'].replace('\n', ' ⏎ '))
    sys.exit()


def s2ref(r):
    a, b = r['printed_page_start'], r['printed_page_end']
    return f"S2 ص{a}" if a == b else f"S2 ص{a}–{b}"


def s1ref(h):
    if not h:
        return 'S1 —'
    a, b = h.get('page_start'), h.get('page_end')
    return f"S1 ج{h.get('vol')} ص{a}" + (f"–{b}" if b and b != a else '')


def tokdiff(a, b):
    a, b = normalize(a).split(), normalize(b).split()
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == 'equal':
            out.append(' '.join(a[i1:i2]))
        else:
            if i2 > i1:
                out.append('[-HID: ' + ' '.join(a[i1:i2]) + '-]')
            if j2 > j1:
                out.append('{+BID: ' + ' '.join(b[j1:j2]) + '+}')
    return ' '.join(out)


con = sqlite3.connect(f'{ROOT}/data/kashshaf.db', timeout=60)
S1RAW = {lib: b for lib, b in con.execute(
    "select lib_page_id, body from page where source_id='S1' and lib_page_id between 11 and 46")}
S1P = [(lib, v, pp, normalize(b)) for lib, v, pp, b in con.execute(
    "select lib_page_id, vol, printed_page, body from page where source_id='S1' "
    "and lib_page_id between 11 and 46 order by lib_page_id")]


def find_in_s1(text):
    n = normalize(text)
    hits = [f"ج{v} ص{pp} (صفحة الشاملة {lib})" for lib, v, pp, b in S1P if n and n in b]
    return hits


byhid = {p['hid_id']: p for p in pairs}
cnt = {k: sum(p['status'] == k for p in pairs) for k in ('exact', 'approx', 'unmatched')}
bid_only = [m for m in masail if m['bid_only']]
ext = meta['extent']
L = []
w = L.append
w('# مقابلة بداية المبتدي بمتن الهداية — كتاب الطهارة (T2.3)')
w('')
w('مادة الوسم `F1.M4.T2`. وصف آلي فقط (حالة: `آلي`)، بلا ترجيح ولا تعليق.')
w('')
if meta['provisional_hid']:
    w('> **تنبيه: هذا التقرير مبني على متن هداية مؤقت** استُخرج بسكربت `scripts/provisional_hid_matn.py`، '
      'لا على الملف المعتمد `data/works/HID/01-tahara.matn.txt` (لم يظهر ملف READY في المهلة).')
    w('')
w('## المصادر والنطاق')
w('')
w(f"- البداية: S2 (بداية المبتدي، ط مكتبة ومطبعة محمد علي صبح). كتاب الطهارة يبدأ في صفحة الشاملة {ext['start_lib_page']} "
  f"(موضع الحرف {ext['start_body_offset']} من page.body، عند عنوان «كتاب الطَّهَارَة») "
  f"وينتهي في صفحة الشاملة {ext['end_lib_page']} قبل الموضع {ext['end_body_offset_exclusive']}؛ "
  f"وعنوان «= كتاب الصَّلَاة» في الصفحة {ext['kitab_salat_heading_lib_page']} عند الموضع {ext['kitab_salat_heading_offset']}. "
  f"طول النص المضموم {ext['concat_length']} حرفًا (الصفحات موصولة بـ`\\n`).")
w(f"- الهداية: S1، ملف المتن `{meta['hid_file']}`.")
w(f"- الإحالات: «S2 صN» = رقم الصفحة المطبوعة (عمود printed_page)؛ «S1 جV صN» = الجزء والصفحة المطبوعة.")
w('')
w('## المنهج')
w('')
w('- التطبيع للمطابقة فقط (`scripts/normalize_ar.py`): حذف التشكيل والتطويل، توحيد أ إ آ ٱ→ا، ى→ي، ة→ه، ؤ→و، ئ→ي، '
  'حذف الهمزة المفردة ء، حذف محارف الدعاء وعلامات الترقيم والوسوم، ضغط المسافات. النص المخزَّن لا يُغيَّر.')
w('- مقابلة رتيبة واحدة (monotonic) بـ`difflib.SequenceMatcher(autojunk=False)` على كلمات النصين بعد التطبيع؛ '
  'لكل متن من الهداية امتداد في البداية = أول كلمة إلى آخر كلمة نُسبت إليه (`scripts/align_bid_hid.py`).')
w(f"- الدرجة = نسبة التشابه (ratio) بين كلمات المتن وكلمات الامتداد. **العتبة {meta['threshold']}**: "
  f"«مطابق تام» إذا تساوت الكلمات بعد التطبيع، «تقريبي» إذا كانت الدرجة ≥ {meta['threshold']}، وما دونها «غير مطابق». "
  'اختيرت 0.60 لأن أدنى المطابقات الصحيحة في الفحص كانت قرابة 0.65–0.70 (متون قصيرة تختلف بكلمة)، '
  'وما دون 0.5 كان نسبة كلمات عامة متفرقة.')
w(f"- ما بقي من نص البداية بلا مقابل وطوله ≤ {meta['absorb_gap_tokens']} كلمة أُلحق بالمسألة السابقة في القسم نفسه؛ وما زاد فمسألة مستقلة «انفرد بها البداية».")
w('- العناوين (كتاب/باب/فصل) لا تدخل في المقابلة.')
w('')
w('## الأعداد')
w('')
w('| البند | العدد |')
w('|---|---|')
w(f"| متون الهداية (وحدات) | {len(pairs)} |")
w(f"| مطابق تام | {cnt['exact']} |")
w(f"| تقريبي | {cnt['approx']} |")
w(f"| غير موجود في البداية | {cnt['unmatched']} |")
w(f"| مسائل البداية المقسَّمة | {len(masail)} |")
w(f"| منها مقطع انفردت به البداية | {len(bid_only)} |")
w('')
sv = None
sp = f'{ROOT}/data/works/BID/01-tahara.spotcheck{suf}.json'
if os.path.exists(sp):
    sv = json.load(open(sp, encoding='utf-8'))
w('## الفحص اليدوي (20 زوجًا عشوائيًّا)')
w('')
if sv:
    ok = sum(1 for v in sv['verdicts'].values() if v == 'correct')
    w(f"بذرة العشوائية {SEED}. الصحيح: **{ok} من {len(sv['verdicts'])}**. "
      f"معيار الصحة: أن يكون امتداد البداية هو موضع المتن نفسه وحدوده لا تزيد ولا تنقص إلا بكلمة ربط.")
    w('')
    w('| معرف الهداية | الحالة | الدرجة | معرف البداية | الحكم |')
    w('|---|---|---|---|---|')
    for p in sample:
        w(f"| {p['hid_id']} | {p['status']} | {p['score']} | {p['bid_id']} | {sv['verdicts'].get(p['hid_id'], '—')} |")
else:
    w('لم يُسجَّل بعد.')
w('')
w('## (أ) نص في البداية لا يقابله متن في الهداية')
w('')
for m in bid_only:
    ctx = ' / '.join(x for x in (m['bab'], m['fasl']) if x) or 'تحت عنوان الكتاب مباشرة'
    w(f"- **{m['id']}** ({s2ref(m)}؛ {ctx}؛ {m['n_tokens']} كلمة)")
    w(f"  > {m['matn_text'].replace(chr(10), ' ')}")
    i = masail.index(m)
    pv = next((x for x in reversed(masail[:i]) if x['hid_id']), None)
    nx = next((x for x in masail[i + 1:] if x['hid_id']), None)
    pref = lambda x: f"{x['hid_id']} ({s1ref(byhid[x['hid_id']]['hid_ref'])})" if x else '—'
    w(f"  - موضعه بين متون الهداية: بعد {pref(pv)} وقبل {pref(nx)}.")
    hits = find_in_s1(m['matn_text'])
    if pv and nx and not hits:   # page-boundary context only when the text is not found in S1
        l1 = byhid[pv['hid_id']]['hid_ref'].get('lib_page_end')
        l2 = byhid[nx['hid_id']]['hid_ref'].get('lib_page_start')
        if l1 and l2 and l2 > l1:
            for lib in range(l1, l2):
                w(f"  - آخر صفحة الشاملة {lib} من S1: «…{S1RAW[lib][-60:]}»؛ وأول صفحة {lib + 1}: «{S1RAW[lib + 1][:60]}…».")
    w(f"  - بحث آلي عن النص نفسه (بعد التطبيع) في نص الهداية S1 ص11–46 من الشاملة: "
      + ('ورد في نص الهداية في ' + '، '.join(hits) if hits else 'لم يرد بلفظه متصلًا.'))
w('')
def _nb(p, step):
    i = pairs.index(p)
    j = i + step
    while 0 <= j < len(pairs):
        if pairs[j].get('bid_id'):
            q = pairs[j]
            return f"{q['bid_id']} ({s2ref(q['bid_ref'])})"
        j += step
    return '—'


def prev_bid(p):
    return _nb(p, -1)


def next_bid(p):
    return _nb(p, 1)


w('## (ب) متن في الهداية لا يوجد في البداية')
w('')
for p in pairs:
    if p['status'] == 'unmatched':
        w(f"- **{p['hid_id']}** ({s1ref(p['hid_ref'])}؛ الدرجة {p['score']})")
        w(f"  > {p['hid_matn']}")
        w(f"  - موضعه بين أزواج البداية: بعد {prev_bid(p)} وقبل {next_bid(p)}.")
w('')
w('## (ج) فروق اللفظ في الأزواج المتقابلة (الدرجة < 1)')
w('')
w('`[-HID: …-]` لفظ في الهداية ليس في البداية، `{+BID: …+}` لفظ في البداية ليس في الهداية (بعد التطبيع).')
w('')
for p in pairs:
    if p['status'] == 'approx':
        w(f"### {p['hid_id']} ↔ {p['bid_id']} (الدرجة {p['score']})")
        w(f"- الهداية ({s1ref(p['hid_ref'])}): {p['hid_matn']}")
        w(f"- البداية ({s2ref(p['bid_ref'])}): {p['bid_text'].replace(chr(10), ' ')}")
        w(f"- الفرق: {tokdiff(p['hid_matn'], p['bid_text'])}")
        w('')
open(f'{ROOT}/reports/bid-hid-diff{suf}.md', 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('written', len(L), 'lines')
