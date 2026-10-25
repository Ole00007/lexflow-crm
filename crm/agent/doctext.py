"""Text extraction + extractive (offline, deterministic) summary for matter documents.

Nothing here follows instructions found inside a document: the text is treated purely as data.
"""
from __future__ import annotations

import io
import re
import zipfile
from typing import Any, Dict, Tuple

MAX_BYTES = 8 * 1024 * 1024
MAX_PDF_PAGES = 60
MAX_TEXT_CHARS = 250_000

_DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/.]\d{1,2}[/.]\d{2,4}|"
    r"\d{1,2}\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre|"
    r"january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4})\b", re.I)
_AMOUNT_RE = re.compile(r"(?:€|EUR\s?)\s?\d[\d.,]*|\b\d[\d.,]*\s?(?:€|euro|EUR)\b", re.I)
_OBLIG_RE = re.compile(
    r"\b(entro|termine|scadenza|udienza|deposit\w*|dovr[àa]|deve|devono|obbligo|notific\w*|"
    r"shall|must|deadline|due|hearing|no later than|within)\b", re.I)


def extract_text(name: str, mime: str, data: bytes) -> Tuple[str, Dict[str, Any], str]:
    """Return (text, meta, note). note is non-empty when text could not be fully extracted."""
    if len(data) > MAX_BYTES:
        return '', {}, 'file too large to read (limit 8 MB)'
    ext = (name.rsplit('.', 1)[-1] if '.' in name else '').lower()
    meta: Dict[str, Any] = {'bytes': len(data)}
    if ext in ('txt', 'md', 'markdown', 'csv') or (mime or '').startswith('text/'):
        return data.decode('utf-8', errors='replace')[:MAX_TEXT_CHARS], meta, ''
    if ext == 'docx':
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                xml = z.read('word/document.xml').decode('utf-8', errors='replace')
            xml = re.sub(r'</w:p>', '\n', xml)
            xml = re.sub(r'<w:tab/>', '\t', xml)
            text = re.sub(r'<[^>]+>', '', xml)
            text = (text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                    .replace('&quot;', '"').replace('&apos;', "'"))
            return text[:MAX_TEXT_CHARS], meta, ''
        except Exception:
            return '', meta, 'could not open this .docx file'
    if ext == 'pdf':
        try:
            import fitz  # pymupdf
        except Exception:
            return '', meta, 'PDF text extraction is not installed on this server (pymupdf)'
        try:
            doc = fitz.open(stream=data, filetype='pdf')
            meta['pages'] = doc.page_count
            parts = [doc[i].get_text() for i in range(min(doc.page_count, MAX_PDF_PAGES))]
            text = '\n'.join(parts).strip()
            if not text:
                return '', meta, 'this PDF has no text layer (scanned image) — OCR is not available'
            return text[:MAX_TEXT_CHARS], meta, ''
        except Exception:
            return '', meta, 'could not open this PDF'
    if ext in ('png', 'jpg', 'jpeg'):
        return '', meta, 'images are not readable as text (OCR is not available)'
    if ext == 'doc':
        return '', meta, 'legacy .doc is not supported — please upload as .docx or PDF'
    return '', meta, f'unsupported file type .{ext}'


def _uniq(items, limit):
    seen, out = set(), []
    for it in items:
        k = it.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(it.strip())
        if len(out) >= limit:
            break
    return out


def _sentences(text: str):
    flat = re.sub(r'[ \t]+', ' ', text)
    for chunk in re.split(r'(?<=[.!?;])\s+|\n+', flat):
        chunk = chunk.strip(' -•*#\t')
        if len(chunk) >= 12:
            yield chunk


def summarize_text(text: str) -> Dict[str, Any]:
    """Deterministic extractive summary: lead sentences, key dates, amounts, obligation lines."""
    sents = list(_sentences(text))
    lead = [s[:220] for s in sents[:3]]
    dates = _uniq(_DATE_RE.findall(text), 10)
    amounts = _uniq(_AMOUNT_RE.findall(text), 8)
    obligations = [s[:200] for s in sents if _OBLIG_RE.search(s)]
    obligations = _uniq(obligations, 6)
    headings = _uniq([ln.lstrip('# ').strip()[:80] for ln in text.splitlines()
                      if ln.startswith('#') and len(ln.strip('# ')) > 2], 6)
    return {'chars': len(text), 'headings': headings, 'lead': lead, 'key_dates': dates,
            'amounts': amounts, 'obligations_and_deadlines': obligations}
