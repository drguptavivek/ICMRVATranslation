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
    return sanitize_rich_html(value, preserve_references=False)


def sanitize_rich_html(value, preserve_references=True):
    if value is None:
        return Markup("")
    parser = _SafeRichTextParser(preserve_references=preserve_references)
    parser.feed(unescape(str(value)))
    parser.close()
    return Markup("".join(parser.parts))


class _SafeRichTextParser(HTMLParser):
    ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "br", "p", "div", "span", "font", "ul", "ol", "li"}
    SKIP_TAGS = {"script", "style", "iframe", "object"}
    COLOR_RE = re.compile(r"^(?:#[0-9a-fA-F]{3,8}|[a-zA-Z]{1,24}|rgb\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\))$")

    def __init__(self, preserve_references=True):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip_depth = 0
        self.preserve_references = preserve_references

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth or tag not in self.ALLOWED_TAGS:
            return
        attributes = dict(attrs)
        if tag == "font":
            tag = "span"
            attributes = {"style": f"color:{attributes.get('color', '')}"}
        style = self._safe_style(attributes.get("style", "")) if tag == "span" else ""
        attribute = f' style="{escape(style, quote=True)}"' if style else ""
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
            self.parts.append(f"</{'span' if tag == 'font' else tag}>")

    def handle_data(self, data):
        if self._skip_depth:
            return
        text = data if self.preserve_references else XLSFORM_REFERENCE_RE.sub("", data)
        safe = escape(text)
        safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
        safe = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", safe)
        safe = re.sub(r"(?m)^#{1,6}\s*", "", safe)
        self.parts.append(safe)

    def _safe_style(self, value):
        allowed = []
        for declaration in value.split(";"):
            if ":" not in declaration:
                continue
            property_name, property_value = (part.strip() for part in declaration.split(":", 1))
            property_name = property_name.lower()
            property_value = property_value.strip()
            if property_name == "color" and self.COLOR_RE.fullmatch(property_value):
                allowed.append(f"color:{property_value}")
            elif property_name == "font-weight" and property_value.lower() in {"bold", "bolder", "600", "700", "800", "900"}:
                allowed.append("font-weight:bold")
            elif property_name == "font-style" and property_value.lower() in {"italic", "oblique"}:
                allowed.append("font-style:italic")
            elif property_name == "text-decoration" and property_value.lower() == "underline":
                allowed.append(f"text-decoration:{property_value.lower()}")
        return ";".join(allowed)
