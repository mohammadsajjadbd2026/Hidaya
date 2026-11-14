# بنية ملفات الشاملة على جهاز الباحث (T1.4)

فُحصت في 14-11-2026. الجهاز: Windows، والشاملة 4 مثبتة في `C:\shamela4`.

## المجلدات

```
C:\shamela4\database\
  master.db            فهرس الكتب والمؤلفين (SQLite)
  book\NNN\<id>.db     ملف لكل كتاب، و NNN = آخر ثلاثة أرقام من المعرِّف (6170 → book\170\6170.db)
  store\page\          فهرس Lucene فيه نصوص الصفحات (body, foot)
  store\title\         فهرس Lucene فيه نصوص العناوين
  store\{author,aya,book,esnad,s_author,s_book}\
```

## ملف الكتاب `<id>.db`

ملف SQLite صغير ليس فيه نص، بل هيكل الكتاب فقط:

```sql
page (id INTEGER PRIMARY KEY, part TEXT, page INTEGER, number INTEGER, services TEXT)
     -- id = page_id في أدوات الشاملة؛ part = الجزء؛ page = رقم الصفحة المطبوعة
title (id INTEGER PRIMARY KEY, page INTEGER, parent INTEGER)   -- شجرة الفهرس بلا نصوص
```

مثال: `6170.db` (بداية المبتدي) فيه 266 صفًّا في `page`، و162 صفًّا في `title`.

## النصوص: فهرس Lucene 10.4 (`store\page`)

- الإصدار: Lucene 10.4.0، والترميز `Lucene104` (قرأناه من `.si`). الحقول المخزَّنة: `id` (بصيغة `"<book>-<page_id>"`)، `body`، `foot`. وفي الفهرس أيضًا قيم رقمية (DocValues) منها `book` و`page`.
- النص المخزَّن هو النص الخام بعلامات العناوين `<span data-type="title" id=toc-N>…</span>`، والفقرات مفصولة بـ `\r`.
- **التحقق:** صفحة مستخرجة بالسكربت (كتاب 3334، صفحة 78) طابقت ناتج `shamela_get_page` (keep_html) حرفًا بحرف في المتن والحاشية.

### مواضع الكتب المطلوبة

قرأنا قيم `book` في المقطع `_2jn`، فوُجدت فيه كل الكتب الأساسية، وعدد صفحاتها مطابق لما في §1.1:

| المصدر | المعرِّف | الصفحات في `_2jn` |
|---|---|---|
| S1 الهداية | 11820 | 1246 |
| S2 بداية المبتدي | 6170 | 266 |
| S3 النهاية | 811 | 5318 |
| S4 معراج الدراية | 30179 | 7597 |
| S5 العناية | 9403 | 5149 |
| S6 التنبيه | 18259 | 2128 |
| S7 البناية | 427 | 7019 |
| S8 فتح القدير | 21744 | 3611 |
| S9 نتائج الأفكار | 1496 | 1541 |
| S12 الجواهر المضية (ت الحلو) | 1163 | 3157 |
| S13 الجواهر المضية (النظامية) | 6725 | 872 |
| S14 تاج التراجم | 10925 | 290 |
| S15 الفوائد البهية | 132617 | 249 |
| (مساند) الجامع الصغير | 6160 | 459 |

S10 (5908) وS11 (11428) لم يوجدا في المقاطع التي فحصناها (`_2jn`، `_2zv`، `_3dn`، `_4la`، `_4lq`، `_4o0`، `_4oh`، `_4oj`، `_4oi`). لم تُفحص بعد المقاطع المركبة الكبيرة `_3ow`، `_403`، `_48u`، `_4c9`، `_4dq`، `_4eu`، `_4js`، `_4ok`، `_4ol`، `_4om`.

## العائق

حجم `_2jn.fdt` (النصوص المخزنة) 1.78 غ.ب، وحدّ نسخ الملف الواحد من الجهاز 400 م.ب. أما بقية ملفات المقطع اللازمة (`.si`، `.fnm`، `_1.fnm`، `.fdm`، `.fdx`، `.dvd/.dvm`) فقد نُسخت.

**الحل المقترح:** يُقسَّم `_2jn.fdt` على الجهاز إلى أجزاء ≤ 380 م.ب (سكربت PowerShell في PROGRESS.md)، فتُنسخ ثم تُجمع هنا. هذا يكفي لكل الكتب في الجدول أعلاه، أي الهداية والبداية والشروح السبعة وكتب التراجم.

## الأدوات

- `scripts/java/lucene-core-10.4.0.jar`: مبني من مصدر Lucene 10.4.0 الرسمي (GitHub apache/lucene، الوسم `releases/lucene/10.4.0`، المجلد `lucene/core/src/java`)، لأن مستودع Maven غير متاح من مساحة العمل.
- `scripts/java/ExtractBooks.java`: يستخرج صفحات كتب بعينها من مقطع واحد إلى `<book>.jsonl`.
- `scripts/java/BookDocs.java`: يبيّن أي الكتب في أي مقطع، ومدى أرقام وثائقها.
- `scripts/java/SegInfo.java`: يسرد حقول المقطع.
- `scripts/extract_shamela.py`: يضم الناتج إلى `<id>.db` ويُدخله في `data/kashshaf.db`.

أمر الاستخراج (بعد جمع `_2jn.fdt`):

```
cd <staged>/store/page
java -cp scripts/java/lucene-core-10.4.0.jar:scripts/java ExtractBooks . _2jn 1 raw/shamela 11820 6170
python3 scripts/extract_shamela.py --jsonl raw/shamela/6170.jsonl --bookdb <staged>/book/170/6170.db --source S2 --book 6170
```
