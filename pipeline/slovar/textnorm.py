"""Tokenizing and normalizing Russian text — must behave exactly like addon/Slovar/Text.lua.

Lua side: a "letter" is a UTF-8 sequence with lead byte 0xD0/0xD1, i.e. code points U+0400..U+047F; a word is a
run of letters, with single hyphens allowed between letters. Normalize = drop stress marks, lowercase А-Я and ASCII,
ё -> е. Nothing else is lowercased (Lua can't), so we don't either.
"""
import re

LETTERS = "Ѐ-ѿ"
WORD_RE = re.compile(f"[{LETTERS}]+(?:-[{LETTERS}]+)*")
_FORM_RE = re.compile(f"^[{LETTERS}̀́]+(?:-[{LETTERS}̀́]+)*$")

_MAP = {ord(c): chr(ord(c) + 32) for c in "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"}
_MAP.update({ord(c): chr(ord(c) + 32) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"})
_MAP.update({ord("Ё"): "е", ord("ё"): "е", 0x0300: None, 0x0301: None})
_STRESS = {0x0300: None, 0x0301: None, ord("ѐ"): "е", ord("ѝ"): "и"}


def norm(word: str) -> str:
    """Dictionary key, identical to ns.Normalize in Text.lua."""
    return word.translate(_MAP)


def unstress(word: str) -> str:
    """Display form: stress marks removed, case and ё kept (волко́в -> волков, ещё stays ещё)."""
    return word.translate(_STRESS)


def tokens(text: str) -> list[str]:
    return WORD_RE.findall(text)


def is_word_form(form: str) -> bool:
    """A single Cyrillic word (hyphens allowed), as opposed to romanizations, phrases or table junk."""
    return bool(_FORM_RE.match(form))
