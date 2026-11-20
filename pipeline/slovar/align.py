"""English names for WoW words Wiktionary doesn't know (Штормград, мурлок, Макбрайд), found automatically from
AzerothCore's parallel quest text: the English term that appears in the same quests as the Russian word.

For a Russian word W (all its forms) and an English term E, over all quests:
    dice = 2 * |quests with both| / (|quests with W| + |quests with E|)
Штормград occurs in ~500 quests and "Stormwind" in almost exactly the same ones -> dice close to 1.
"""
import collections
import os
import re

from . import sqldump
from .corpus import clean_ac
from .textnorm import WORD_RE, norm

STOP = set("""a about above after again against all also am an and any are as at back be because been before being
below between both but by can come could did do does doing down each even few find for from further get go had has
have having he her here hers him his how i if in into is it its just kill know like long make me more most much must
my need no nor not now of off on once one only or other our out over own please return same see she should so some
such take tell than that the their them then there these they this those through to too under until up us very want
was way we well were what when where which while who whom why will with would you your yours yes
time help good may let back bring thing many think must quest more name""".split())


def _en_terms(text: str):
    text = re.sub(r"\$[A-Za-z]", " ", text)
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        lw = lw[:-2] if lw.endswith("'s") else lw
        if lw in STOP or len(lw) < 3:
            continue
        stem = lw[:-1] if lw.endswith("s") and not lw.endswith("ss") and len(lw) > 4 else lw
        out.append((stem, w))
        if w[0].isupper() and i + 1 < len(words) and words[i + 1][0].isupper():
            nxt = words[i + 1]
            out.append((stem + " " + nxt.lower(), w + " " + nxt))  # Loch Modan, Dun Morogh, Elwynn Forest
    return out


class Aligner:
    def __init__(self, ac_dir: str):
        ru, en = collections.defaultdict(set), collections.defaultdict(set)
        surface = collections.defaultdict(collections.Counter)
        classic = set()
        for r in sqldump.rows(os.path.join(ac_dir, "quest_template.sql")):
            qid, level, min_level = int(r[0]), int(r[2]), int(r[3])
            if max(level, min_level) > 60:  # Northrend etc.: names like Dragonblight would compete
                continue
            classic.add(qid)
            for field in [r[74], r[75], r[76], r[77], r[78], *r[100:104]]:
                for stem, word in _en_terms(field or ""):
                    en[qid].add(stem)
                    surface[stem][word] += 1
        for r in sqldump.rows(os.path.join(ac_dir, "quest_template_locale.sql")):
            if r[1] == "ruRU" and int(r[0]) in classic:
                for field in r[2:11]:
                    ru[int(r[0])].update(norm(w) for w in WORD_RE.findall(clean_ac(field or "")))
        self.ru, self.en, self.surface = ru, en, surface
        self.df = collections.Counter(t for terms in en.values() for t in terms)
        self.ru_index = collections.defaultdict(set)
        for qid, words in ru.items():
            for w in words:
                self.ru_index[w].add(qid)

    def english(self, forms, min_quests=3, min_dice=0.5) -> str | None:
        quests = set().union(*(self.ru_index.get(f, set()) for f in forms))
        if len(quests) < min_quests:
            return None
        co = collections.Counter(t for q in quests for t in self.en.get(q, ()))
        scored = sorted(((2 * c / (len(quests) + self.df[t]), t) for t, c in co.items() if c >= min_quests),
                        reverse=True)
        if not scored or scored[0][0] < min_dice:
            return None
        best_dice, best = scored[0]
        for dice, t in scored[:5]:  # Лок -> "Loch Modan" (two-word name that fits at least as well)
            if " " in t and best in t.split() and dice >= best_dice:
                best = t
                break
        surfaces = self.surface[best]
        word = surfaces.most_common(1)[0][0]
        singular = word[:-1]
        if word.endswith("s") and any(w.lower() == singular.lower() for w in surfaces):
            word = singular  # murlocs -> murloc, but Darnassus stays Darnassus
        capitalized = sum(n for w, n in surfaces.items() if w[0].isupper()) * 2 > sum(surfaces.values())
        return word if capitalized else word.lower()  # Stormwind, McBride, Loch Modan / murloc
