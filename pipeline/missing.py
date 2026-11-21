"""Words you hovered in game that Slovar didn't know, read from the addon's SavedVariables.

    pipeline/.venv/bin/python pipeline/missing.py [--wtf PATH]

WoW writes SavedVariables on logout and /reload, so do one of those first. For each word this says whether the next
`build.py` run fixes it by itself (the word is in Wiktionary; build.py reads the same log) or whether it needs a
line in pipeline/extra_words.tsv, with a suggested dictionary form to fill in the English for.
"""
import argparse
import os
import sys

from slovar import kaikki, morph, savedvars
from slovar.textnorm import norm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wtf", default=savedvars.DEFAULT_WTF, help="WoW WTF folder")
    args = ap.parse_args()
    words = savedvars.missing_words(args.wtf)
    if not words:
        print(f"No missing-word log found under {args.wtf}/Account/*/SavedVariables/Slovar.lua "
              "(hover an unknown word in game, then /reload or log out).")
        return
    lex = kaikki.load(os.path.join(ROOT, "data", "kaikki", "ru-en.jsonl.gz"), os.path.join(ROOT, "data", "cache"))
    index = lex.index()
    suggestions = []
    print(f"{len(words)} words in the log (most hovered first):\n")
    for m in words:
        key = norm(m.word)
        quest = f"  [quest {m.quest}]" if m.quest else ""
        if key in index or morph.link(key, lex):
            status = "in Wiktionary: the next build.py run adds it"
        else:
            p = morph.analyzer().parse(key)[0]
            lemma = p.normal_form.capitalize() if m.word[:1].isupper() else p.normal_form
            how = "known to pymorphy3" if p.is_known else "guessed"
            pos = p.tag.POS or "unknown part of speech"
            status = f"not in Wiktionary: dictionary form probably «{lemma}» ({pos}, {how})"
            suggestions.append(f"{lemma}\t")
        print(f"{m.word} ×{m.count}{quest}\n    {status}")
        for c in m.contexts:
            print(f"    « {c} »")
    if suggestions:
        print("\nTo fix the rest, add lines like these to pipeline/extra_words.tsv (fill in the English), then run")
        print("pipeline/.venv/bin/python pipeline/build.py and /reload in game:\n")
        print("\n".join(dict.fromkeys(suggestions)))


if __name__ == "__main__":
    sys.exit(main())
