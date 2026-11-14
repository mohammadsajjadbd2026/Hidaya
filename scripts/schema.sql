-- مخطط قاعدة كشّاف كتب المرغيناني (PLAN.md §3.2) — SQLite
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS source(
  id TEXT PRIMARY KEY, title TEXT NOT NULL, author TEXT, death_h INTEGER,
  library TEXT CHECK(library IN ('shamela','aljame','pdf')), lib_id TEXT,
  edition TEXT, editor TEXT, publisher TEXT, volumes INTEGER, pages INTEGER,
  matches_print TEXT CHECK(matches_print IN ('yes','no','unknown')) DEFAULT 'unknown',
  is_ocr INTEGER DEFAULT 0, rights TEXT CHECK(rights IN ('turath','modern')));
CREATE TABLE IF NOT EXISTS page(
  id TEXT PRIMARY KEY, source_id TEXT REFERENCES source(id), lib_page_id INTEGER,
  vol TEXT, printed_page INTEGER, body TEXT, foot TEXT, toc_path TEXT);
CREATE INDEX IF NOT EXISTS page_src ON page(source_id, lib_page_id);
CREATE TABLE IF NOT EXISTS toc(
  source_id TEXT, title_id INTEGER, page_lib_id INTEGER, parent INTEGER, title TEXT,
  PRIMARY KEY(source_id,title_id));
CREATE TABLE IF NOT EXISTS masala(
  id TEXT PRIMARY KEY, work TEXT CHECK(work IN ('BID','HID','TAJ','MUK')),
  kitab TEXT, bab TEXT, fasl TEXT, seq INTEGER, vol TEXT, page_start INTEGER, page_end INTEGER,
  source_id TEXT REFERENCES source(id), matn_text TEXT, sharh_text TEXT,
  char_start INTEGER, char_end INTEGER, bid_masala_id TEXT,
  review_status TEXT CHECK(review_status IN ('auto','reviewed')) DEFAULT 'auto');
CREATE TABLE IF NOT EXISTS evidence(
  id TEXT PRIMARY KEY, masala_id TEXT REFERENCES masala(id), text TEXT,
  char_start INTEGER, char_end INTEGER,
  layer TEXT CHECK(layer IN ('matn','sharh','sharih','editor')), vol TEXT, page INTEGER);
CREATE TABLE IF NOT EXISTS tag(
  id TEXT PRIMARY KEY, evidence_id TEXT REFERENCES evidence(id), code TEXT, attrs TEXT,
  method TEXT CHECK(method IN ('regex','model','manual')), pattern_id TEXT, confidence REAL,
  review TEXT CHECK(review IN ('unreviewed','confirmed','rejected')) DEFAULT 'unreviewed',
  reviewer TEXT, reviewed_at TEXT);
CREATE TABLE IF NOT EXISTS sharh_link(
  id TEXT PRIMARY KEY, masala_id TEXT REFERENCES masala(id), source_id TEXT REFERENCES source(id),
  vol TEXT, page_start INTEGER, page_end INTEGER, anchor_text TEXT,
  match_method TEXT CHECK(match_method IN ('toc','lemma','manual')), score REAL, review TEXT);
CREATE TABLE IF NOT EXISTS material(
  id TEXT PRIMARY KEY, code TEXT, source_id TEXT, vol TEXT, page INTEGER, text TEXT,
  citation TEXT, note TEXT, ocr_verified INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS study(
  id TEXT PRIMARY KEY, title TEXT, author TEXT, kind TEXT, institution TEXT, year TEXT,
  pages TEXT, published TEXT, abstract TEXT, outline TEXT, relation_note TEXT, url TEXT);
CREATE TABLE IF NOT EXISTS stat(
  id TEXT PRIMARY KEY, indicator TEXT, scope_work TEXT, scope_kitab TEXT, scope_bab TEXT,
  value REAL, n_auto INTEGER, n_confirmed INTEGER, precision REAL, recall REAL,
  sample_n INTEGER, computed_at TEXT);
CREATE TABLE IF NOT EXISTS pattern(id TEXT PRIMARY KEY, code TEXT, regex TEXT, notes TEXT, version INTEGER);
