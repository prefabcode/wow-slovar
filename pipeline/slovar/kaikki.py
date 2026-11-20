"""Russian lexicon from kaikki.org's extract of English Wiktionary (Russian entries, English glosses).

Each JSONL line is one entry (word + part of speech + senses + forms). Two kinds matter:
  * headword entries (волк: senses with glosses, "forms" = inflection table with tags);
  * form-of entries (волков: "genitive/accusative plural of волк") -> just more forms of the headword.
Participles are form-of entries of a verb that have their own declension table: we keep them as headwords
("past passive participle of убить") and borrow the verb's glosses.
"""
import gzip
import json
import os
import pickle
import re
from dataclasses import dataclass, field

from . import tags as T
from .textnorm import is_word_form, norm, unstress

CACHE_VERSION = 8
SKIP_FORMOF = {"abbreviation", "initialism", "acronym", "misspelling"}

# Wiktionary shows one shared table for all personal pronouns, so its "forms" would make мне a form of он.
# These eight paradigms are small and fixed, so they are spelled out here (keys normalized: ё -> е).
PERSONAL_PRONOUNS = {
    "я": {"я": "N", "меня": "GA", "мне": "DP", "мной": "I", "мною": "I"},
    "ты": {"ты": "N", "тебя": "GA", "тебе": "DP", "тобой": "I", "тобою": "I"},
    "он": {"он": "N", "его": "GA", "него": "GA", "ему": "D", "нему": "D", "им": "I", "ним": "I", "нем": "P"},
    "оно": {"оно": "N", "его": "GA", "него": "GA", "ему": "D", "нему": "D", "им": "I", "ним": "I", "нем": "P"},
    "она": {"она": "N", "ее": "GA", "нее": "GA", "ей": "DIP", "ней": "DIP", "ею": "I", "нею": "I"},
    "мы": {"мы": "N", "нас": "GAP", "нам": "D", "нами": "I"},
    "вы": {"вы": "N", "вас": "GAP", "вам": "D", "вами": "I"},
    "они": {"они": "N", "их": "GA", "них": "GAP", "им": "D", "ним": "D", "ими": "I", "ними": "I"},
}
KEEP_POS = {"noun", "verb", "adj", "name", "adv", "num", "pron", "intj", "det", "prep", "conj", "particle",
            "postp", "contraction"}
MINOR_SENSE = {"obsolete", "archaic", "dated", "dialectal", "rare", "historical", "nonstandard", "proscribed",
               "Internet", "slang", "vulgar", "derogatory", "offensive", "humorous", "poetic", "misspelling"}


@dataclass
class Lemma:
    display: str  # dictionary form shown in the tooltip (stress removed, ё kept)
    pos: str  # kaikki part of speech, or "participle" / "guess"
    glosses: list[str] = field(default_factory=list)
    minor_glosses: list[str] = field(default_factory=list)  # archaic/rare senses, used only if nothing else
    gender: str = ""  # "m", "f", "n" (nouns)
    animacy: str = ""  # "animate" / "inanimate"
    plural_only: bool = False
    aspect: str = ""  # "perfective" / "imperfective" / "biaspectual"
    partner: str = ""  # aspect partner verb
    participle_of: str = ""
    participle_kind: str = ""  # e.g. "past passive"
    derived_from: str = ""  # героиня <- герой, найтись <- найти: borrow its glosses if ours say nothing
    forms: dict[str, set[str]] = field(default_factory=dict)  # normalized form -> tagsets
    source: str = "kaikki"

    @property
    def key(self):
        return (self.display, self.pos)

    def add_form(self, form: str, tagsets):
        self.forms.setdefault(norm(unstress(form)), set()).update(tagsets)


def _clean_gloss(sense) -> str | None:
    glosses = sense.get("glosses")
    if not glosses:
        return None
    text = " ".join(unstress(glosses[-1]).split()).rstrip(".").replace("|", "/")
    if "form_of" in sense or "alt_of" in sense:  # "female equivalent of геро́й (gerój): heroine" -> "heroine"
        text = text.split("): ", 1)[1] if "): " in text else re.sub(r" \([^()]*\)$", "", text)
    if not text or text.startswith("[") or re.match(r"[Ѐ-ӿ]", text):  # "леса scaffolding": sense of one form
        return None
    # Keep glosses short: "to bring (by foot), to fetch (transitive)..." -> "to bring"
    cut = text.find(" (")
    if cut >= 8:
        text = text[:cut]
    text = re.sub(r"\s*\([^()]*\)|\s*\[[^\]]*\]", "", text).strip(" ,;:")
    if not text:
        return None
    if len(glosses) > 1 and glosses[0].startswith("[with "):  # [with prepositional] in, at, on
        text += f" (+ {glosses[0][6:].rstrip(']')})"
    if len(text) > 70:
        cut = max(text.rfind(", ", 0, 70), text.rfind("; ", 0, 70))
        text = text[:cut] if cut > 25 else text[:69] + "…"
    return text


def _head_gender(entry) -> tuple[str, str]:
    for h in entry.get("head_templates", []):
        m = re.search(r"\)\s+([mfn])(?: or [mfn])?\s+(anim|inan)", h.get("expansion", ""))
        if m:
            return m[1], "animate" if m[2] == "anim" else "inanimate"
    return "", ""


class Lexicon:
    def __init__(self):
        self.lemmas: dict[tuple, Lemma] = {}
        self.by_word: dict[str, list[tuple]] = {}  # norm(display) -> lemma keys

    def get(self, display, pos) -> Lemma:
        key = (display, pos)
        lem = self.lemmas.get(key)
        if lem is None:
            lem = self.lemmas[key] = Lemma(display, pos)
            self.by_word.setdefault(norm(display), []).append(key)
        return lem

    def find(self, word: str, pos_options=None) -> list[tuple]:
        keys = self.by_word.get(norm(word), [])
        if pos_options:
            keys = [k for k in keys if k[1] in pos_options] or keys
        return keys

    def index(self) -> dict[str, list[tuple]]:
        """normalized form -> lemma keys that have it."""
        idx = {}
        for key, lem in self.lemmas.items():
            for form in lem.forms:
                idx.setdefault(form, []).append(key)
        return idx


def _read(path) -> Lexicon:
    lex = Lexicon()
    pending = []  # (form, target word, pos, tagsets) from form-of entries
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            pos, word = e.get("pos"), e.get("word", "")
            if pos not in KEEP_POS or not is_word_form(word):
                continue
            display = unstress(word)
            forms = e.get("forms", [])
            head_senses, formof_senses = [], []
            own_table = any("inflection-template" in fm.get("tags", []) for fm in forms)
            for s in e.get("senses", []):
                stags = set(s.get("tags", []))
                derived = own_table and not ("participle" in stags and "adverbial" not in stags)
                if ("form_of" in s or "alt_of" in s) and not derived:
                    formof_senses.append(s)
                else:
                    # Real headwords, plus "form-of" entries with their own inflection table: героиня ("female
                    # equivalent of герой"), найтись ("passive of найти") are words in their own right.
                    head_senses.append(s)

            if head_senses:
                lem = lex.get(display, pos)
                entry_glosses = []
                for s in head_senses:
                    src = s.get("form_of") or s.get("alt_of")
                    if src and not lem.derived_from and is_word_form(src[0].get("word", "")):
                        lem.derived_from = unstress(src[0]["word"])
                    g = _clean_gloss(s)
                    if g:
                        minor = MINOR_SENSE & set(s.get("tags", [])) or g.lower().startswith("used ")  # usage notes
                        bucket = lem.minor_glosses if minor else entry_glosses
                        if g.casefold() not in (x.casefold() for x in bucket):
                            bucket.append(g)
                # Same word + part of speech in several Wiktionary entries (стать: "to stand..." and "to become"):
                # take the meanings in turns, so each entry's main sense makes the top 3.
                merged, groups = [], [lem.glosses, entry_glosses]
                for i in range(max(map(len, groups))):
                    merged += [grp[i] for grp in groups if i < len(grp)]
                lem.glosses = list(dict.fromkeys(merged)) if lem.glosses else entry_glosses
                canon_tags = set()
                for fm in forms:
                    if "canonical" in fm.get("tags", []):
                        canon_tags |= set(fm["tags"])
                sense_tags = set(head_senses[0].get("tags", []))
                all_tags = canon_tags | sense_tags
                if pos in ("noun", "name") and not lem.gender:
                    hg, ha = _head_gender(e)
                    lem.gender = next((x[0] for x in ("masculine", "feminine", "neuter") if x in all_tags), hg)
                    lem.animacy = next((x for x in ("animate", "inanimate") if x in all_tags), ha)
                    lem.plural_only = "plural-only" in sense_tags or ("plural" in canon_tags and pos == "noun")
                if pos == "verb":
                    for fm in forms:
                        ft = set(fm.get("tags", []))
                        if ft & {"canonical", "infinitive"}:
                            if {"perfective", "imperfective"} <= ft:
                                lem.aspect = "biaspectual"
                            elif not lem.aspect:
                                lem.aspect = next((x for x in ("perfective", "imperfective") if x in ft), "")
                        elif ft in ({"perfective"}, {"imperfective"}) and not lem.partner and is_word_form(fm["form"]):
                            lem.partner = unstress(fm["form"])
                for fm in forms:
                    if fm.get("form") and fm["form"] != "-" and is_word_form(fm["form"]):
                        ts = T.from_kaikki(fm.get("tags", []), pos, lem.plural_only)
                        if ts:
                            lem.add_form(fm["form"], ts)
                default = {"noun": ["Np" if lem.plural_only else "Ns"], "name": ["Ns"], "verb": ["i"],
                           "adj": ["Nms"]}.get(pos, [""])
                lem.add_form(word, default)

            for s in formof_senses:
                target = (s.get("form_of") or s.get("alt_of"))[0].get("word", "")
                if not is_word_form(target):
                    continue
                stags = set(s.get("tags", []))
                if stags & SKIP_FORMOF and "apocopic" not in stags:  # в as an abbreviation of восток (ж = же stays)
                    continue
                case_forms = [fm for fm in forms if set(fm.get("tags", [])) & set(T.CASE)]
                if "participle" in stags and "adverbial" not in stags and case_forms:
                    plem = lex.get(display, "participle")
                    plem.participle_of = unstress(target)
                    plem.participle_kind = " ".join(x for x in ("present", "past", "active", "passive") if x in stags)
                    for fm in case_forms:
                        if fm["form"] != "-" and is_word_form(fm["form"]):
                            plem.add_form(fm["form"], T.from_kaikki(fm["tags"], "adj"))
                    plem.add_form(word, ["Nms"])
                else:
                    ts = T.from_kaikki(stags - {"form-of", "alt-of"}, pos) or [""]
                    pending.append((word, target, pos, ts))

    for form, target, pos, ts in pending:
        keys = lex.find(unstress(target), {pos}) if pos in KEEP_POS else lex.find(unstress(target))
        for key in keys[:2]:
            lex.lemmas[key].add_form(form, ts)
    personal_forms = {f for paradigm in PERSONAL_PRONOUNS.values() for f in paradigm}
    for key, lem in lex.lemmas.items():
        if key[1] != "pron":
            continue
        if norm(lem.display) in PERSONAL_PRONOUNS:
            lem.forms = {form: set(cases) for form, cases in PERSONAL_PRONOUNS[norm(lem.display)].items()}
        else:  # его, себя, её...: drop the shared table's personal forms (мне is not a form of себя)
            lem.forms = {f: ts for f, ts in lem.forms.items() if f not in personal_forms or f == norm(lem.display)}
    return lex


def load(path: str, cache_dir: str) -> Lexicon:
    os.makedirs(cache_dir, exist_ok=True)
    cache = os.path.join(cache_dir, f"lexicon-v{CACHE_VERSION}-{int(os.path.getmtime(path))}.pkl")
    if os.path.exists(cache):
        with open(cache, "rb") as f:
            return pickle.load(f)
    lex = _read(path)
    with open(cache, "wb") as f:
        pickle.dump(lex, f, protocol=pickle.HIGHEST_PROTOCOL)
    return lex
