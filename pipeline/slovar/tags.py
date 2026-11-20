"""Compact grammar codes shared with addon/Slovar/Lookup.lua.

A "tagset" is one grammatical reading of a form, encoded as a short string of one-char codes in canonical order,
e.g. "Gp" = genitive plural, "1su" = 1st person singular future, "tac"... One case per tagset; a form like волков
(genitive or accusative plural) gets two tagsets: "Gp", "Ap". Lookup.lua turns them back into English.
"""

CASE = {"nominative": "N", "genitive": "G", "dative": "D", "accusative": "A", "instrumental": "I",
        "prepositional": "P", "locative": "L", "vocative": "V", "partitive": "R"}
OTHER = {
    "first-person": "1", "second-person": "2", "third-person": "3",
    "singular": "s", "plural": "p",
    "masculine": "m", "feminine": "f", "neuter": "n",
    "animate": "y", "inanimate": "z",
    "present": "r", "past": "t", "future": "u",
    "active": "a", "passive": "e",
    "imperative": "o", "infinitive": "i",
    "short-form": "h", "comparative": "k", "superlative": "x",
}
ORDER = "NGDAIPLVR123spmfnyzrtuaecwoihkx"  # c = participle, w = gerund (adverbial participle)
_RANK = {c: i for i, c in enumerate(ORDER)}

# Tags that make a kaikki form an inflected form of the headword (as opposed to a related word like волчица).
CORE = set(CASE) | {"infinitive", "present", "past", "future", "imperative", "participle", "short-form",
                    "comparative", "superlative"}
SKIP = {"romanization", "table-tags", "inflection-template", "class", "error-unknown-tag", "error-unrecognized-form"}
NOMINAL_POS = {"noun", "name"}


def canon(codes) -> str:
    return "".join(sorted(set(codes), key=_RANK.__getitem__))


def from_kaikki(tags, pos: str, plural_only: bool = False) -> list[str]:
    """kaikki tag list -> tagsets (one per case). [] if the tags don't describe an inflected form."""
    t = set(tags)
    if t & SKIP or not t & CORE:
        return []
    rest = [OTHER[x] for x in t if x in OTHER]
    if "participle" in t:
        rest.append("w" if "adverbial" in t else "c")
    if "o" in rest:  # imperative: person is implied
        rest = [c for c in rest if c not in "123"]
    if "y" in rest or "z" in rest:  # animacy only matters for accusative forms
        if "accusative" not in t:
            rest = [c for c in rest if c not in "yz"]
    cases = [CASE[x] for x in t if x in CASE]
    if cases and pos in NOMINAL_POS and "s" not in rest and "p" not in rest:
        rest.append("p" if plural_only else "s")  # noun head forms like ('во́лка', ['genitive']) are singular
    if "p" in rest or pos in NOMINAL_POS:  # plurals have no gender; a noun's gender belongs to the word, not the form
        rest = [c for c in rest if c not in "mfn"]
    if cases and "s" not in rest and "p" not in rest and any(c in rest for c in "mfn"):
        rest.append("s")  # adjective tables: a gender column means singular

    return [canon([c] + rest) for c in cases] if cases else [canon(rest)]


_PM_CASE = {"nomn": "N", "gent": "G", "datv": "D", "accs": "A", "ablt": "I", "loct": "P", "voct": "V",
            "gen2": "R", "acc2": "A", "loc2": "L", "gen1": "G", "loc1": "P"}
_PM_OTHER = {"1per": "1", "2per": "2", "3per": "3", "sing": "s", "plur": "p", "masc": "m", "femn": "f", "neut": "n",
             "pres": "r", "past": "t", "futr": "u", "actv": "a", "pssv": "e", "impr": "o", "INFN": "i",
             "ADJS": "h", "PRTS": "h", "COMP": "k", "Supr": "x", "PRTF": "c", "GRND": "w"}


def from_pymorphy(tag) -> str:
    """pymorphy3 OpencorporaTag -> tagset."""
    grams = set(tag.grammemes)
    codes = [_PM_OTHER[g] for g in grams if g in _PM_OTHER]
    if "PRTS" in grams:
        codes.append("c")
    cases = [_PM_CASE[g] for g in grams if g in _PM_CASE]
    if cases and "accs" in grams and tag.POS in ("ADJF", "PRTF", "NPRO") and ("anim" in grams or "inan" in grams):
        codes.append("y" if "anim" in grams else "z")
    if "impr" in grams:
        codes = [c for c in codes if c not in "123"]
    if tag.POS == "VERB" and "past" in grams:
        codes = [c for c in codes if c not in "123"]
    if "plur" in grams or tag.POS == "NOUN":
        codes = [c for c in codes if c not in "mfn"]
    return canon(codes + cases[:1])
