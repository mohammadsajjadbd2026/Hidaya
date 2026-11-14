"""Arabic normalization for MATCHING ONLY (T2.3).

Never applied to stored text. Provides:
  normalize(s)            -> normalized string
  normalize_map(s)        -> (normalized string, list mapping each normalized
                              char index -> index in the original string)
  tokens_with_spans(s)    -> list of (token, orig_start, orig_end)

Rules:
  - strip HTML tags (<span ...>, </span>) entirely (treated as a space)
  - strip tashkeel (U+064B..U+065F, U+0670 superscript alef, U+06D6..U+06ED Quranic marks)
    and tatweel (U+0640)
  - unify أ إ آ ٱ ٲ ٳ -> ا ;  ى -> ي ;  ة -> ه ; ؤ -> و ; ئ -> ي ; bare ء dropped
  - remove blessing glyphs ﵊ ﵀ ﵁ ﵃ ﵄ ﵏ ﷺ ﷽ (and the whole U+FD3E..U+FDFF / U+FE70.. presentation
    blocks are not expected; ﴿﴾ are treated as punctuation)
  - all punctuation / symbols / digits-as-markers -> space ; '=' -> space
  - collapse whitespace
"""
import re
import sys
import unicodedata

TASHKEEL = set(chr(c) for c in range(0x064B, 0x0660)) | {'ٰ', 'ـ'} | \
    set(chr(c) for c in range(0x06D6, 0x06EE))
UNIFY = {'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا', 'ٲ': 'ا', 'ٳ': 'ا',
         'ى': 'ي', 'ة': 'ه', 'ؤ': 'و', 'ئ': 'ي'}
BLESSINGS = set('﵊﵀﵁﵃﵄﵇﵏ﷺ﷽')
DROP = {'ء'}  # bare hamza dropped (المتوضىء/المتوضئ)
TAG_RE = re.compile(r'<[^>]*>')


def _is_word_char(ch):
    cat = unicodedata.category(ch)
    return cat[0] == 'L' or cat == 'Nd'


def normalize_map(s):
    """Return (norm, idx) where idx[i] = position in s of norm[i]."""
    # blank out tags but keep positions
    masked = TAG_RE.sub(lambda m: ' ' * len(m.group()), s)
    out, idx = [], []
    prev_space = True
    for i, ch in enumerate(masked):
        if ch in TASHKEEL or ch in DROP:
            continue
        if ch in BLESSINGS:
            ch = ' '
        ch = UNIFY.get(ch, ch)
        if not _is_word_char(ch):
            if prev_space:
                continue
            out.append(' ')
            idx.append(i)
            prev_space = True
            continue
        out.append(ch)
        idx.append(i)
        prev_space = False
    if out and out[-1] == ' ':
        out.pop(); idx.pop()
    return ''.join(out), idx


def normalize(s):
    return normalize_map(s)[0]


def tokens_with_spans(s):
    """Tokens of the normalized text with [start,end) offsets into the original s."""
    norm, idx = normalize_map(s)
    toks = []
    for m in re.finditer(r'\S+', norm):
        a, b = m.start(), m.end()
        os_, oe = idx[a], idx[b - 1] + 1
        # extend over trailing/leading chars dropped by normalization (tashkeel, ء)
        while oe < len(s) and (s[oe] in TASHKEEL or s[oe] in DROP):
            oe += 1
        while os_ > 0 and s[os_ - 1] in DROP:
            os_ -= 1
        toks.append((m.group(), os_, oe))
    return toks


if __name__ == '__main__':
    for line in sys.stdin:
        print(normalize(line))
