"""RFQ input handling: plain text passes through; real MIME emails (.eml) are parsed.

Stdlib only. A MIME message is reduced to "Subject + best body part" so the extractor
sees the same clean text an operator would read: headers, quoted-printable/base64
encodings, and HTML markup never reach the rules. Plain-text input is returned
unchanged (byte-for-byte behavior of v1.0).
"""
from __future__ import annotations

import re
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from html.parser import HTMLParser

# Headers that mark the start of a real RFC 5322 message (vs. prose that merely
# mentions "from" or "subject").
_HEADER_LINE = re.compile(
    rb"^(From|To|Cc|Subject|Date|Received|Return-Path|Message-ID|MIME-Version|Content-Type):",
    re.IGNORECASE,
)


class _HTMLToText(HTMLParser):
    _SKIP = {"script", "style", "head", "title"}
    _BREAK = {"p", "br", "div", "tr", "li", "table", "h1", "h2", "h3", "h4"}
    # Rendered-or-not is ambiguous for these; their text is KEPT but flagged.
    _SUSPICIOUS_TAGS = {"template", "datalist", "dialog", "xml"}

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0
        self._hidden_tags: list[str] = []
        self._css: list[str] = []
        self.suspicious = False

    def handle_starttag(self, tag, attrs):
        # THE INVERSION for this wall (V2 round 10): rounds 8-10 proved that deciding
        # visibility from CSS deletes VISIBLE text sooner or later (Word writes
        # text-indent:-18.0pt on every bullet; background-color contains color).
        # So styles never delete anything: only non-content tags are skipped, and
        # hiding-CAPABLE styling raises the review flag instead. Detection happens
        # HERE, on the parser's DECODED view — unquoted attributes and entity-encoded
        # colons look exactly like their plain forms at this level (V2 round 11).
        # attrs is iterated as a LIST: browsers keep the FIRST duplicate style
        # attribute while dict() would keep the last (V2 round 12); the font tag's
        # color attribute hides exactly like a color declaration
        if tag in self._SUSPICIOUS_TAGS:
            self.suspicious = True
        for k, v in attrs:
            if (k == "hidden" or (k == "style" and _css_suspicious(v or ""))
                    or (k == "color" and _decl_hides("color", v or ""))):
                self.suspicious = True
                break
        if tag in self._SKIP:
            self._skip_depth += 1
            self._hidden_tags.append(tag)
        elif tag in self._BREAK:
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if self._hidden_tags and tag == self._hidden_tags[-1] and self._skip_depth:
            self._skip_depth -= 1
            self._hidden_tags.pop()
        elif tag in self._BREAK:
            self._chunks.append("\n")

    def handle_data(self, data):
        if self._hidden_tags and self._hidden_tags[-1] == "style":
            self._css.append(data)
        if not self._skip_depth:
            self._chunks.append(data)

    def handle_comment(self, data):
        # <!--[if mso]> ... <![endif]--> renders in Outlook: its text is KEPT (via a
        # sub-parse) and the message flags for review (V2 round 13).
        if data.lstrip().lower().startswith("[if"):
            inner = re.sub(r"^\s*\[if[^\]]*\]>?|<!\[endif\]\s*$", "", data,
                           flags=re.IGNORECASE | re.DOTALL)
            sub = _HTMLToText()
            sub.feed(inner)
            self._chunks.append("\n" + sub.text() + "\n")
            self.suspicious = True

    def css(self) -> str:
        return "\n".join(self._css)

    def text(self) -> str:
        out = "".join(self._chunks)
        return re.sub(r"\n{3,}", "\n\n", out).strip()


HIDDEN_SENTINEL = "[hidden-content-suspected]"
HTML_SENTINEL = "[html-source]"

_NUM = re.compile(r"-?(?:\d+(?:\.\d+)?|\.\d+)")


# hex white: #fff, #ffff, #ffffff, #ffffffff (V2 round 16 — through one rule)
_HEX_WHITE = re.compile(r"#f{3}f?\b|#f{6}(?:f{2})?\b")

# CSS escape: backslash + 1-6 hex digits + ONE optional whitespace terminator
# (space, tab, LF, CR, FF, or the CRLF pair) — per the CSS spec, not a guess.
_CSS_ESC = re.compile(r"\\([0-9a-fA-F]{1,6})(?:\r\n|[ \t\r\n\f])?|\\")

# CSS numeric token: sign, leading-dot decimals, scientific notation — ONE parser
# for every arm, colors included (V2 rounds 15-16).
_CSS_NUM = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?", re.IGNORECASE)

# off-screen offset thresholds by unit, in that unit (≈500px equivalents);
# '%' relative to the container is judged like a viewport unit.
_OFF = {"px": 500, "pt": 375, "pc": 31, "cm": 13, "mm": 132, "in": 5.2,
        "em": 10, "rem": 10, "ch": 20, "ex": 20, "vh": 40, "vw": 40, "vmin": 40, "vmax": 40, "%": 90, "": 500}
_UNIT = re.compile(r"[a-z%]+")
_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def _unescape_css(s: str) -> str:
    """Resolve CSS identifier escapes ('non\\65' is 'none') and strip comments
    ('display/**/:none') before any matching (V2 rounds 12-16)."""
    return _CSS_ESC.sub(lambda m: chr(int(m.group(1), 16)) if m.group(1) else "",
                        _COMMENT.sub("", s))


def _nums(val: str) -> list[tuple[float, str]]:
    """All numeric tokens in a CSS value as (number, unit) via the ONE parser."""
    out = []
    for m in _CSS_NUM.finditer(val):
        u = _UNIT.match(val[m.end():])
        out.append((float(m.group(0)), u.group(0) if u else ""))
    return out


def _off_screen(num: float, unit: str, factor: float = 1.0) -> bool:
    return num <= -_OFF.get(unit, 500) * factor


def _alpha_zero(val: str) -> bool:
    """Fully transparent colors by alpha: rgba(...,0), rgb(0 0 0 / 0), #0000,
    #00000000 (V2 round 17 — 'transparent' judged numerically, not by keyword)."""
    hx = re.match(r"#([0-9a-f]{4}|[0-9a-f]{8})\b", val.strip())
    if hx:
        h = hx.group(1)
        return (h[3] == "0") if len(h) == 4 else (h[6:8] == "00")
    fn = re.match(r"(?:rgba?|hsla?|hwb)\(([^)]*)", val.strip())
    if fn:
        args = _nums(fn.group(1))
        if len(args) >= 4 and args[3][0] == 0:
            return True
    return False


def _color_is_whiteish(val: str) -> bool:
    """White-family judged NUMERICALLY through the one parser (V2 round 16):
    rgb components >= 250 (or >= 98%), hsl lightness / hwb whiteness >= 95%,
    any hue unit, any spelling of the numbers."""
    if "transparent" in val or _alpha_zero(val) \
            or re.search(r"\bwhite\b", val) or _HEX_WHITE.search(val):
        return True
    if re.fullmatch(r"f{3}f?|f{6}(?:f{2})?", val.strip()):
        return True          # hash-less legacy colors are white in every client
    fn = re.match(r"(rgba?|hsla?|hwb)\(([^)]*)", val.strip())
    if not fn:
        return False
    kind, args = fn.group(1), _nums(fn.group(2))
    if kind.startswith("rgb") and len(args) >= 3:
        return all(n >= (98 if u == "%" else 250) for n, u in args[:3])
    if kind.startswith("hsl") and len(args) >= 3:
        return args[2][0] >= 95
    if kind == "hwb" and len(args) >= 2:
        return args[1][0] >= 95
    return False


def _decl_hides(name: str, val: str) -> bool:
    """TRUE declaration parsing (V2 round 10): exact property names; every numeric
    arm reads through _nums()/_off_screen(), every escape and comment through
    _unescape_css(), every color through _color_is_whiteish() (V2 rounds 15-16).
    Used ONLY to raise the review flag — never to delete text."""
    name = _unescape_css(name.strip().lower()).strip()
    val = _unescape_css(val.strip().lower()).strip()
    toks = _nums(val)
    first = toks[0] if toks else None

    if name == "display" and "none" in val:
        return True
    if name == "visibility" and ("hidden" in val or "collapse" in val):
        return True
    if name == "mso-hide" and "all" in val:
        return True
    if name == "color" and _color_is_whiteish(val):
        return True
    if name == "opacity" and first is not None:
        num = first[0] / 100 if first[1] == "%" else first[0]
        if num <= 0.05:
            return True
    if name in ("font-size", "width", "height", "max-height", "max-width") \
            and first is not None and first[0] == 0:
        return True
    if name == "font" and first is not None and first[0] == 0:
        return True
    if name in ("clip", "clip-path"):
        return True
    if name == "text-indent" and first is not None \
            and _off_screen(first[0], first[1], factor=0.3):
        return True          # -18pt Word bullets / -2em hanging indents stay; -150px/-50cm hide
    if name in ("left", "right", "top", "bottom", "inset", "margin-left",
                "margin-right", "margin-top", "translate") \
            and any(_off_screen(n, u) for n, u in toks):
        return True
    if name == "transform":
        for fm in re.finditer(r"translate(?:[xyz]|3d)?\(([^)]*)\)", val):
            if any(_off_screen(n, u) for n, u in _nums(fm.group(1))):
                return True
        for fm in re.finditer(r"scale(?:[xyz]|3d)?\(([^)]*)\)", val):
            if any(n == 0 and u in ("", "%") for n, u in _nums(fm.group(1))):
                return True
        for fm in re.finditer(r"matrix\(([^)]*)\)", val):
            args = _nums(fm.group(1))
            if args and (args[0][0] == 0 or (len(args) > 3 and args[3][0] == 0)):
                return True
        for fm in re.finditer(r"matrix3d\(([^)]*)\)", val):
            args = _nums(fm.group(1))
            if len(args) >= 6 and (args[0][0] == 0 or args[5][0] == 0):
                return True
    if name == "scale" and any(n == 0 for n, _ in toks):
        return True
    return False


def _css_suspicious(css: str) -> bool:
    """Scan bare name:value declaration pairs, ignoring brace structure entirely —
    an @media-nested rule hides exactly like a flat one (V2 round 11). The WHOLE
    text is unescaped first so escaped property NAMES ('displa\\79:none') tokenize
    like their plain forms (V2 round 13)."""
    css = _unescape_css(css)
    # newlines inside parentheses ("translate(-9999px,\n0)") must not truncate the
    # declaration tokenizer (V2 round 17)
    css = re.sub(r"\(([^)]*)\)", lambda mm: "(" + mm.group(1).replace("\n", " ") + ")", css)
    return any(_decl_hides(nm.group(1), nm.group(2))
               for nm in re.finditer(r"([a-zA-Z-]+)\s*:\s*([^;{}\n]+)", css))


def html_to_text(html: str) -> str:
    p = _HTMLToText()
    p.feed(html)
    out = p.text()
    # Hiding-CAPABLE styling anywhere flags the whole message for human review:
    # nothing is deleted, and any value the hidden text contributed sits behind this
    # flag. Detection runs on the parser's DECODED attributes plus the collected
    # <style> text scanned as bare declarations (V2 rounds 10-11).
    if p.suspicious or _css_suspicious(p.css()):
        out += "\n" + HIDDEN_SENTINEL
    # STRUCTURAL (V2 round 17): every HTML-derived text carries a constant
    # provenance marker — rendering-equivalence is undecidable, so no HTML value
    # is EVER unflagged by construction; the tripwire above stays as the
    # high-signal alarm, not a completeness obligation.
    out += "\n" + HTML_SENTINEL
    return out


def looks_like_mime(raw: bytes, filename: str | None = None) -> bool:
    if filename and filename.lower().endswith(".eml"):
        return True
    head = raw.lstrip()[:2048]
    # Require at least two header-looking lines among the first few, so an RFQ that
    # happens to start with "Subject: hoses" prose is not enough on its own.
    hits = sum(1 for line in head.splitlines()[:12] if _HEADER_LINE.match(line))
    return hits >= 2


def _best_body(msg: EmailMessage) -> str:
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    content = part.get_content()
    if part.get_content_type() == "text/html":
        return html_to_text(content)
    return content.strip()


def extract_rfq_text(raw: bytes, filename: str | None = None) -> str:
    """Return the RFQ text the agent should extract from.

    MIME input -> "Subject\n\nbody" (best text part, HTML stripped).
    Anything else -> the input decoded as UTF-8, unchanged.
    """
    if looks_like_mime(raw, filename):
        msg = BytesParser(policy=policy.default).parsebytes(raw)
        subject = str(msg.get("Subject", "")).strip()
        body = _best_body(msg)
        if subject or body:
            return f"{subject}\n\n{body}".strip()
        # fall through: header-shaped but empty message — treat as plain text
    return raw.decode("utf-8", errors="replace")
