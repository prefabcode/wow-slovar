"""pymorphy3 (OpenCorpora dictionary + suffix-based guessing) for words Wiktionary doesn't list:
  * link(): a form missing from Wiktionary's tables, whose dictionary form IS in Wiktionary -> attach it there;
  * guess(): WoW names and creatures (Штормграда, мурлоков) -> a guessed headword with its full declension.
"""
import pymorphy3

from . import tags as T
from .kaikki import Lemma, Lexicon
from .textnorm import norm

_morph = None

# pymorphy part of speech -> compatible kaikki parts of speech
POS_MAP = {
    "NOUN": {"noun", "name"}, "ADJF": {"adj", "participle", "det", "pron", "num"}, "ADJS": {"adj", "participle"},
    "COMP": {"adj", "adv"}, "VERB": {"verb"}, "INFN": {"verb"}, "PRTF": {"participle", "verb", "adj"},
    "PRTS": {"participle", "verb", "adj"}, "GRND": {"verb"}, "NUMR": {"num"}, "ADVB": {"adv"}, "NPRO": {"pron"},
    "PRED": {"adv"}, "PREP": {"prep"}, "CONJ": {"conj"}, "PRCL": {"particle"}, "INTJ": {"intj"},
}


def analyzer():
    global _morph
    if _morph is None:
        _morph = pymorphy3.MorphAnalyzer()
    return _morph


def link(token: str, lex: Lexicon) -> dict[tuple, set[str]]:
    """{lemma key: tagsets} for dictionary parses of `token` whose lemma exists in the lexicon."""
    out = {}
    for p in analyzer().parse(token):
        if not p.is_known or p.tag.POS not in POS_MAP:
            continue
        for key in lex.find(p.normal_form, POS_MAP[p.tag.POS]):
            if key[1] in POS_MAP[p.tag.POS]:
                out.setdefault(key, set()).add(T.from_pymorphy(p.tag))
    return out


def lexeme_lemma(parse, display: str, label_pos: str) -> Lemma:
    lem = Lemma(display, "guess", source="guess")
    grams = set(parse.tag.grammemes)
    lem.gender = next((g[0] for g in ("masc", "femn", "neut") if g in grams), "")
    lem.participle_kind = label_pos  # reused as the label for guessed words: "proper noun", "noun", "adjective"
    for f in parse.lexeme:
        if f.tag.POS == parse.tag.POS:
            lem.forms.setdefault(norm(f.word), set()).add(T.from_pymorphy(f.tag))
    return lem


def guess(token: str, corpus_forms: set[str], capitalized: bool) -> Lemma | None:
    """Best noun/adjective reading of an unknown word: the candidate dictionary form whose declension covers the
    most word forms actually seen in the corpus (мурлоков, мурлоки, мурлоками -> мурлок, not мурлокова)."""
    best = None
    for p in analyzer().parse(token):
        if p.tag.POS not in ("NOUN", "ADJF"):
            continue
        support = len({norm(f.word) for f in p.lexeme} & corpus_forms)
        rank = (support, p.score)
        if best is None or rank > best[0]:
            best = (rank, p)
    if best is None:
        if not capitalized:
            return None
        lem = Lemma(token.capitalize(), "guess", source="guess")  # Магни, Шру: name that doesn't decline here
        lem.participle_kind = "proper noun"
        lem.forms = {token: {""}}
        return lem
    p = best[1]
    display = p.normal_form.capitalize() if capitalized else p.normal_form
    label = "adjective" if p.tag.POS == "ADJF" else ("proper noun" if capitalized else "noun")
    return lexeme_lemma(p, display, label)


def from_lemma(word: str, english: str) -> Lemma | None:
    """Glossary entry -> headword with full declension (Штормград -> штормграда, штормграде, ...)."""
    capitalized = word[:1].isupper()
    parses = [p for p in analyzer().parse(word) if p.tag.POS in ("NOUN", "ADJF") and norm(p.normal_form) == norm(word)]
    if not parses:
        return None
    p = parses[0]
    lem = lexeme_lemma(p, word, "adjective" if p.tag.POS == "ADJF" else ("proper noun" if capitalized else "noun"))
    lem.glosses = [english]
    lem.source = "glossary"
    return lem
