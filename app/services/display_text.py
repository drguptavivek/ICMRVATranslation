from html import escape, unescape
from html.parser import HTMLParser
import re

from markupsafe import Markup


XLSFORM_REFERENCE_RE = re.compile(r"\$\{[^}]*\}")


class _DisplayTextParser(HTMLParser):
    BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "p",
        "section",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
    }
    LINE_BREAK_TAGS = {"br"}
    SKIP_TAGS = {"script", "style"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in self.LINE_BREAK_TAGS or tag in self.BLOCK_TAGS:
            self._append_break()

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in self.BLOCK_TAGS:
            self._append_break()

    def handle_data(self, data):
        if self._skip_depth:
            return
        self.parts.append(data)

    def _append_break(self):
        if self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")


def clean_text_for_display(value):
    if value is None:
        return ""

    parser = _DisplayTextParser()
    parser.feed(unescape(str(value)))
    parser.close()
    text = XLSFORM_REFERENCE_RE.sub("", "".join(parser.parts).replace("\xa0", " "))
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def clean_html_for_display(value):
    if value is None:
        return Markup("")
    parser = _SafeRichTextParser()
    parser.feed(unescape(str(value)))
    parser.close()
    return Markup("".join(parser.parts))


class _SafeRichTextParser(HTMLParser):
    ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "br", "p", "div", "span", "ul", "ol", "li"}
    SKIP_TAGS = {"script", "style", "iframe", "object"}
    COLOR_RE = re.compile(r"^(?:#[0-9a-fA-F]{3,8}|[a-zA-Z]{1,24}|rgb\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\))$")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth or tag not in self.ALLOWED_TAGS:
            return
        attribute = ""
        if tag == "span":
            style = dict(attrs).get("style", "")
            match = re.fullmatch(r"\s*color\s*:\s*([^;]+)\s*;?\s*", style, re.IGNORECASE)
            if match and self.COLOR_RE.fullmatch(match.group(1).strip()):
                attribute = f' style="color:{escape(match.group(1).strip(), quote=True)}"'
        self.parts.append(f"<{tag}{attribute}>")

    def handle_startendtag(self, tag, attrs):
        if tag.lower() == "br" and not self._skip_depth:
            self.parts.append("<br>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if not self._skip_depth and tag in self.ALLOWED_TAGS and tag != "br":
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if self._skip_depth:
            return
        text = XLSFORM_REFERENCE_RE.sub("", data)
        safe = escape(text)
        safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
        safe = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", safe)
        safe = re.sub(r"(?m)^#{1,6}\s*", "", safe)
        self.parts.append(safe)
