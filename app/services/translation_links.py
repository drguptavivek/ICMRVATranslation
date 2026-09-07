"""Language-code helpers for external translation links."""


GOOGLE_TRANSLATE_CODE_ALIASES = {
    "asm": "as",
    "ass": "as",
    "ben": "bn",
    "gj": "gu",
    "guj": "gu",
    "hin": "hi",
    "kan": "kn",
    "mal": "ml",
    "mar": "mr",
    "od": "or",
    "odi": "or",
    "ori": "or",
    "pan": "pa",
    "pu": "pa",
    "tam": "ta",
    "tel": "te",
}


def google_translate_language_code(language_code):
    code = (language_code or "").strip().lower().replace("_", "-")
    if not code:
        return None
    base, separator, region = code.partition("-")
    normalized_base = GOOGLE_TRANSLATE_CODE_ALIASES.get(base, base)
    return f"{normalized_base}-{region}" if separator else normalized_base
