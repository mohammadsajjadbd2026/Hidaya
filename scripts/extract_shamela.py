#!/usr/bin/env python3
"""استخراج كتب الشاملة إلى قاعدة الكشّاف (PLAN §4.0 المسار أ، المهمتان T1.4 و T1.6).

الخطوات:
1. ExtractBooks.java يقرأ مقطع Lucene (store/page) ويكتب <book>.jsonl فيه نص كل صفحة (body/foot) بلا مرور في سياق النموذج.
2. هذا السكربت يضمّ إليه جدول page من ملف الكتاب <book>.db (الجزء ورقم الصفحة المطبوعة) ويُدخل الصفوف في data/kashshaf.db.

الاستعمال:
  python3 extract_shamela.py --jsonl /tmp/ext/6170.jsonl --bookdb .../book/170/6170.db --source S2 --book 6170
"""
import argparse, json, sqlite3, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jsonl', required=True)
    ap.add_argument('--bookdb', required=True)
    ap.add_argument('--source', required=True, help='S1, S2 …')
    ap.add_argument('--book', type=int, required=True)
    ap.add_argument('--db', default=str(ROOT / 'data' / 'kashshaf.db'))
    a = ap.parse_args()

    meta = {}
    b = sqlite3.connect(a.bookdb)
    for pid, part, page, number in b.execute('select id, part, page, number from page'):
        meta[pid] = (part, page)
    titles = b.execute('select id, page, parent from title').fetchall()

    rows, missing_meta = [], 0
    for line in open(a.jsonl, encoding='utf-8'):
        r = json.loads(line)
        bk, pid = r['id'].split('-')
        assert int(bk) == a.book, r['id']
        pid = int(pid)
        part, page = meta.get(pid, (None, None))
        if pid not in meta:
            missing_meta += 1
        rows.append((f'{a.source}:p{pid:05d}', a.source, pid, part, page,
                     r.get('body', ''), r.get('foot', ''), None))
    rows.sort(key=lambda x: x[2])

    db = sqlite3.connect(a.db)
    db.execute('delete from page where source_id=?', (a.source,))
    db.executemany('insert into page(id,source_id,lib_page_id,vol,printed_page,body,foot,toc_path) values (?,?,?,?,?,?,?,?)', rows)
    db.execute('delete from toc where source_id=?', (a.source,))
    db.executemany('insert into toc(source_id,title_id,page_lib_id,parent,title) values (?,?,?,?,NULL)',
                   [(a.source, t, p, par) for t, p, par in titles])
    db.commit()

    vols = {}
    for r in rows:
        vols[r[3]] = vols.get(r[3], 0) + 1
    report = {'source': a.source, 'book': a.book, 'pages_extracted': len(rows),
              'pages_in_bookdb': len(meta), 'pages_without_meta': missing_meta,
              'pages_per_vol': vols, 'toc_entries': len(titles),
              'first_lib_page': rows[0][2] if rows else None, 'last_lib_page': rows[-1][2] if rows else None}
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    sys.exit(main())
