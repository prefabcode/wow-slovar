"""Read WoW SavedVariables files: Lua assignments of table literals, written by the game on logout and /reload.

    SlovarDB = { ["missing"] = { ["поохотиться"] = { ["word"] = "поохотиться", ["count"] = 2, ... } } }
"""
import glob
import os
import re
from dataclasses import dataclass, field

DEFAULT_WTF = "/Volumes/PerkDrive/games/World of Warcraft/_forever_/WTF"
_WS = re.compile(r"(?:\s+|--\[\[.*?\]\]|--[^\n]*)*", re.S)
_NUM = re.compile(r"-?(?:0x[0-9a-fA-F]+|\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ESC = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v", "\\": "\\", '"': '"',
        "'": "'", "\n": "\n"}


class _Parser:
    def __init__(self, src: str):
        self.s, self.i = src, 0

    def ws(self):
        self.i = _WS.match(self.s, self.i).end()

    def eat(self, tok):
        self.ws()
        if self.s.startswith(tok, self.i):
            self.i += len(tok)
            return True
        return False

    def string(self):
        quote = self.s[self.i]
        self.i += 1
        out = []
        while self.s[self.i] != quote:
            c = self.s[self.i]
            if c == "\\":
                nxt = self.s[self.i + 1]
                m = re.match(r"\d{1,3}", self.s[self.i + 1:self.i + 4])
                if m:
                    out.append(chr(int(m[0])))
                    self.i += 1 + len(m[0])
                    continue
                out.append(_ESC.get(nxt, nxt))
                self.i += 2
            else:
                out.append(c)
                self.i += 1
        self.i += 1
        text = "".join(out)
        try:  # \ddd escapes are bytes: re-decode them as UTF-8
            return text.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return text

    def value(self):
        self.ws()
        c = self.s[self.i]
        if c == "{":
            return self.table()
        if c in "\"'":
            return self.string()
        for lit, val in (("true", True), ("false", False), ("nil", None)):
            if self.s.startswith(lit, self.i):
                self.i += len(lit)
                return val
        m = _NUM.match(self.s, self.i)
        if not m:
            raise ValueError(f"unexpected {self.s[self.i:self.i + 30]!r}")
        self.i = m.end()
        return float(m[0]) if any(ch in m[0] for ch in ".eE") and not m[0].startswith("0x") else int(m[0], 0)

    def table(self):
        self.i += 1  # {
        out, n = {}, 0
        while not self.eat("}"):
            self.ws()
            if self.s[self.i] == "[":
                self.i += 1
                key = self.value()
                self.eat("]")
                self.eat("=")
                out[key] = self.value()
            else:
                m = _NAME.match(self.s, self.i)
                save = self.i
                if m:
                    self.i = m.end()
                    if self.eat("="):
                        out[m[0]] = self.value()
                    else:
                        self.i = save
                        m = None
                if not m:
                    n += 1
                    out[n] = self.value()
            self.eat(",") or self.eat(";")
        return out

    def assignments(self) -> dict:
        out = {}
        self.ws()
        while self.i < len(self.s):
            m = _NAME.match(self.s, self.i)
            if not m:
                raise ValueError(f"unexpected {self.s[self.i:self.i + 30]!r}")
            self.i = m.end()
            self.eat("=")
            out[m[0]] = self.value()
            self.ws()
        return out


def read(path: str) -> dict:
    return _Parser(open(path, encoding="utf-8", errors="replace").read()).assignments()


@dataclass
class Missing:
    word: str
    count: int
    contexts: list[str] = field(default_factory=list)
    quest: int | None = None


def _as_list(t) -> list:
    """Lua arrays come back as {1: a, 2: b}; empty ones as {}."""
    return [v for _, v in sorted(t.items())] if isinstance(t, dict) else list(t or [])


@dataclass
class SavedWord:
    """A word saved for Anki with the in-game hotkey (SlovarDB.saved, see addon/Slovar/Saved.lua)."""
    key: str  # normalized dictionary form: one Anki note per key
    lemma: str
    label: str
    glosses: list[str]
    others: list[dict]  # other readings or parts: {lemma, label, grammar, glosses}
    examples: list[dict]  # {form, grammar, sentence, quest}
    added: int  # game time() of the first save
    count: int


def saved_words(wtf_dir: str = DEFAULT_WTF) -> list[SavedWord]:
    """All saved words, merged over accounts, oldest first."""
    merged: dict[str, SavedWord] = {}
    for path in glob.glob(os.path.join(wtf_dir, "Account", "*", "SavedVariables", "Slovar.lua")):
        db = read(path).get("SlovarDB") or {}
        for key, c in (db.get("saved") or {}).items():
            examples = _as_list(c.get("examples"))
            others = [{**o, "glosses": _as_list(o.get("glosses"))} for o in _as_list(c.get("others"))]
            w = merged.get(key)
            if w is None:
                merged[key] = SavedWord(key, c.get("lemma", key), c.get("label", ""), _as_list(c.get("glosses")),
                                        others, examples, int(c.get("added", 0)), int(c.get("count", 0)))
            else:
                w.examples += [e for e in examples if e not in w.examples]
                w.count += int(c.get("count", 0))
                w.added = min(w.added, int(c.get("added", 0)))
    return sorted(merged.values(), key=lambda w: (w.added, w.key))


def missing_words(wtf_dir: str = DEFAULT_WTF) -> list[Missing]:
    """Words logged by /slovar's missing-word log, merged over all accounts, most hovered first."""
    merged: dict[str, Missing] = {}
    for path in glob.glob(os.path.join(wtf_dir, "Account", "*", "SavedVariables", "Slovar.lua")):
        db = read(path).get("SlovarDB") or {}
        for key, e in (db.get("missing") or {}).items():
            contexts = [c for _, c in sorted((e.get("contexts") or {}).items())]
            m = merged.setdefault(key, Missing(e.get("word", key), 0, [], e.get("quest")))
            m.count += int(e.get("count", 0))
            m.contexts += [c for c in contexts if c not in m.contexts]
    return sorted(merged.values(), key=lambda m: -m.count)
