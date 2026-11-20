"""Lemma frequencies from the Russian National Corpus: Lyashevskaya & Sharoff (2009),
"Частотный словарь современного русского языка", http://dict.ruslang.ru/freq.php (freqrnc2011.csv)."""
import csv

from .textnorm import norm

# RNC part of speech -> kaikki parts of speech
POS_MAP = {"s": {"noun"}, "v": {"verb"}, "a": {"adj", "participle"}, "adv": {"adv"}, "spro": {"pron"},
           "apro": {"det", "pron", "adj"}, "advpro": {"adv", "pron"}, "conj": {"conj"}, "pr": {"prep"},
           "part": {"particle"}, "intj": {"intj"}, "num": {"num"}, "anum": {"adj", "num"}, "s.PROP": {"name"}}


class Freq:
    def __init__(self, path: str):
        self.rows = []  # (lemma, rnc pos, ipm), most frequent first
        self.by_word = {}  # norm(lemma) -> [(rnc pos, ipm)]
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                ipm = float(r["Freq(ipm)"])
                self.rows.append((r["Lemma"], r["PoS"], ipm))
                self.by_word.setdefault(norm(r["Lemma"]), []).append((r["PoS"], ipm))
        self.rows.sort(key=lambda x: -x[2])

    def score(self, word: str, pos: str) -> float:
        """Frequency (ipm) of `word` used as kaikki part of speech `pos`; 0 if the corpus never has it so.
        в as a preposition: 30000; в as "volt": 0."""
        return max((ipm for rp, ipm in self.by_word.get(norm(word), []) if pos in POS_MAP.get(rp, ())), default=0.0)

    def top(self, n: int):
        """The n most frequent common-word lemmas (proper names excluded) as (lemma, kaikki pos set)."""
        out = [(lemma, POS_MAP.get(pos, set())) for lemma, pos, _ in self.rows if pos != "s.PROP"]
        return out[:n]
