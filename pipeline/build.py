"""Build the Slovar dictionary: quest corpus -> lemmas -> every inflected form -> addon/Slovar/Data/*.lua.

    pipeline/.venv/bin/python pipeline/build.py            (after pipeline/fetch.py)

Which words go in:
  1. every lemma that any word of the quest corpus can belong to (all candidates for ambiguous forms);
  2. the N most frequent Russian lemmas (fallback for quests not in the corpus; --freq-top, default 10000);
  3. WoW names (guessed from the corpus) and pipeline/extra_words.tsv;
  4. words from your in-game missing-word log (SavedVariables), so a rebuild fixes them when it can.
Each chosen lemma contributes ALL its forms, so волков works even if the corpus only had волк.
"""
import argparse
import collections
import os
import re
import sys
import time

from slovar import align, corpus, freq, kaikki, luaout, morph, savedvars
from slovar.textnorm import WORD_RE, norm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
DEFAULT_ADDONS = "/Volumes/PerkDrive/games/World of Warcraft/_forever_/Interface/AddOns"


class Corpus:
    """Token counts of one group of quests, plus capitalization stats for guessing proper names."""

    def __init__(self, name, quests):
        self.name, self.quests = name, quests
        self.counts = collections.Counter()
        self.mid = collections.Counter()  # occurrences not at sentence start
        self.mid_cap = collections.Counter()  # ... of which capitalized
        for q in quests:
            for text in q.texts:
                for m in WORD_RE.finditer(text):
                    w = norm(m[0])
                    self.counts[w] += 1
                    before = text[:m.start()].rstrip()
                    if before and before[-1] not in ".!?…\n«\"—:":
                        self.mid[w] += 1
                        self.mid_cap[w] += m[0][0].isupper()

    def capitalized(self, w):
        return self.mid[w] > 0 and self.mid_cap[w] * 2 >= self.mid[w]


def merge(corpora):
    total = Corpus("all", [])
    for c in corpora:
        total.counts.update(c.counts)
        total.mid.update(c.mid)
        total.mid_cap.update(c.mid_cap)
    return total


def load_glossary(path):
    entries = []
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.split("#", 1)[0].rstrip()
            if line:
                word, english = line.split("\t")[:2]
                entries.append((word.strip(), english.strip()))
    return entries


class Selection:
    """Chosen lemmas for a token set: kaikki lemma keys, extra (pymorphy-linked) forms, guessed WoW names."""

    def __init__(self, lex, index, fq, glossary, tokens: Corpus, freq_top: int, vocab: Corpus | None = None):
        self.lex = lex
        self.chosen = set()
        self.extra = collections.defaultdict(dict)  # kaikki key -> {form: tagsets}
        self.guesses = {}  # norm(display) -> Lemma
        self.glossary_ignored = []
        forms_seen = set(tokens.counts)
        for tok in tokens.counts:
            for w in [tok] + (tok.split("-") if "-" in tok else []):
                if w in index:
                    self.chosen.update(index[w])
                    continue
                links = morph.link(w, lex)
                if links:
                    for key, ts in links.items():
                        self.chosen.add(key)
                        self.extra[key].setdefault(w, set()).update(ts)
                    continue
                if len(w) > 2 and "-" not in w:  # hyphenated words fall back to their parts
                    g = morph.guess(w, forms_seen, tokens.capitalized(w))
                    if g:
                        known = self.guesses.get(norm(g.display))
                        if known:
                            for f, ts in g.forms.items():
                                known.forms.setdefault(f, set()).update(ts)
                        else:
                            self.guesses[norm(g.display)] = g
        # Vocabulary-only text (item/NPC names, gossip, books): real words attested in the frequency list only —
        # item names are full of rare words that would bloat the data for little gain.
        for tok in (vocab.counts if vocab else ()):
            for w in [tok] + (tok.split("-") if "-" in tok else []):
                keys = index.get(w) or morph.link(w, lex)
                self.chosen.update(k for k in keys if fq.score(*k) > 0 or
                                   k[1] == "participle" and fq.score(lex.lemmas[k].participle_of, "verb") > 0)
        for lemma, poss in fq.top(freq_top):
            self.chosen.update(lex.find(lemma, poss))
        for word, english in glossary:
            if lex.find(word):
                self.glossary_ignored.append(word)  # Wiktionary already has it
                continue
            g = self.guesses.get(norm(word))
            if g:
                g.display, g.glosses, g.source = word, [english], "glossary"
            else:
                g = morph.from_lemma(word, english)
                if g:
                    self.guesses[norm(word)] = g


def build_output(sel: Selection, fq):
    lex = sel.lex
    cands = collections.defaultdict(dict)  # form -> {lemma (key or guess id): tagsets}
    for key in sel.chosen:
        for f, ts in lex.lemmas[key].forms.items():
            cands[f].setdefault(key, set()).update(ts)
    for key, forms in sel.extra.items():
        for f, ts in forms.items():
            cands[f].setdefault(key, set()).update(ts)
    for gid, g in sel.guesses.items():
        for f, ts in g.forms.items():
            cands[f].setdefault(("guess", gid), set()).update(ts)

    def obj(k):
        return sel.guesses[k[1]] if k[0] == "guess" and k[1] in sel.guesses else lex.lemmas[k]

    score_cache = {}

    def score(k):
        if k not in score_cache:
            lem = obj(k)
            if lem.source in ("guess", "glossary"):
                s = 1.0 if lem.source == "glossary" else 0.5
            else:
                s = fq.score(lem.display, lem.pos)
                if lem.pos == "participle":
                    s = max(s, fq.score(lem.participle_of, "verb"))
            score_cache[k] = s
        return score_cache[k]

    final = {}
    for f, by_lemma in cands.items():
        ranked = sorted(by_lemma, key=lambda k: (-score(k), str(k)))
        if score(ranked[0]) > 0:  # drop never-attested homographs (в = "volt") when a real word exists
            ranked = [k for k in ranked if score(k) > 0]
        if any(k[1] != "name" for k in ranked):  # real-world names (Волков) never matter next to a word (волков)
            ranked = [k for k in ranked if k[1] != "name"]
        merged = []  # тот as "determiner" and as "pronoun": one tooltip entry (the more frequent one)
        for k in ranked:
            twin = next((m for m in merged if m[1] in ("det", "pron") and k[1] in ("det", "pron")
                         and m[0] == k[0] and m != k), None)
            if twin:
                by_lemma[twin] = by_lemma[twin] | by_lemma[k]
            else:
                merged.append(k)
        final[f] = [(k, by_lemma[k]) for k in merged[:3]]
    return final, obj, score


def align_guesses(sel: Selection, final, aligner):
    """Give guessed WoW words an English name from the parallel quest text. Returns [(lemma, english|None)]."""
    results = []
    for gid, g in sel.guesses.items():
        if g.source != "guess":
            continue
        forms = [f for f in g.forms if f in final and final[f][0][0] == ("guess", gid)]
        english = aligner.english(forms) if forms else None
        if english:
            g.glosses = [english]
        results.append((g, english, forms))
    return results


def _short(glosses, budget=70):
    """At most 3 glosses and about `budget` characters in total ("pest; vermin; saboteur; ... malware" is too
    much for a tooltip). The first gloss is always kept."""
    out, used = [], 0
    for g in glosses[:3]:
        if out and used + len(g) > budget:
            break
        out.append(g)
        used += len(g) + 2
    return out


def glosses_for(lex, lem):
    if lem.pos == "participle":
        verb = lex.lemmas.get((lem.participle_of, "verb"))
        if verb:
            return _short(verb.glosses or verb.minor_glosses)
    own = lem.glosses[:3] or lem.minor_glosses[:3]
    # "passive of хранить" says nothing by itself: add хранить's meanings.
    if getattr(lem, "derived_from", "") and len(own) < 3 and any(re.search(r"\bof \S+$", g) for g in own):
        base = next((lex.lemmas[k] for k in lex.find(lem.derived_from, {lem.pos})), None)
        if base:
            own = own + [g for g in base.glosses if g not in own][:3 - len(own)]
    return _short(own)


def coverage(c: Corpus, final_forms):
    total = sum(c.counts.values())
    direct = sum(n for w, n in c.counts.items() if w in final_forms)
    parts = sum(n for w, n in c.counts.items() if w not in final_forms and "-" in w
                and all(p in final_forms for p in w.split("-")))
    missing = collections.Counter({w: n for w, n in c.counts.items() if w not in final_forms and not (
        "-" in w and all(p in final_forms for p in w.split("-")))})
    return total, direct, parts, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-level", type=int, default=30)
    ap.add_argument("--freq-top", type=int, default=10000)
    ap.add_argument("--addons", default=DEFAULT_ADDONS, help="WoW Interface/AddOns folder (for Wayfarer text)")
    ap.add_argument("--out", default=os.path.join(ROOT, "addon", "Slovar", "Data"))
    ap.add_argument("--wtf", default=savedvars.DEFAULT_WTF, help="WoW WTF folder (for the missing-word log)")
    ap.add_argument("--vocab", action="store_true",
                    help="also take vocabulary from AzerothCore item/NPC names, gossip and books (+1.5 MB)")
    ap.add_argument("--show-guesses", type=int, default=150, help="how many guessed WoW words to list")
    args = ap.parse_args()
    t0 = time.time()

    def step(msg):
        print(f"[{time.time() - t0:5.1f}s] {msg}", flush=True)

    step("reading quest corpora")
    ac = corpus.azerothcore(os.path.join(DATA, "azerothcore"), args.max_level)
    wf = corpus.wayfarer(args.addons, args.max_level, corpus.ac_levels(os.path.join(DATA, "azerothcore")))
    groups = [
        Corpus(f"AzerothCore Alliance quests 1-{args.max_level}", list(ac.values())),
        Corpus("Wayfarer: classic quests", [q for q in wf.values() if not q.forever_new]),
        Corpus("Wayfarer: new WoW Forever quests", [q for q in wf.values() if q.forever_new]),
    ]
    logged = savedvars.missing_words(args.wtf) if os.path.isdir(args.wtf) else []
    if logged:
        texts = [m.word for m in logged] + [c for m in logged for c in m.contexts]
        groups.append(Corpus("Your missing-word log", [corpus.Quest(0, "log", None, texts)]))
    for g in groups:
        step(f"  {g.name}: {len(g.quests)} quests, {sum(g.counts.values())} words, {len(g.counts)} distinct")
    vocab = Corpus("AzerothCore names, gossip, books", corpus.wow_vocabulary(os.path.join(DATA, "azerothcore"))) \
        if args.vocab else None
    if vocab:
        step(f"  {vocab.name} (vocabulary only): {sum(vocab.counts.values())} words, {len(vocab.counts)} distinct")
    step("loading kaikki lexicon (first run parses ~1 GB, then cached)")
    lex = kaikki.load(os.path.join(DATA, "kaikki", "ru-en.jsonl.gz"), os.path.join(DATA, "cache"))
    index = lex.index()
    step(f"  {len(lex.lemmas)} lemmas, {len(index)} distinct forms")
    fq = freq.Freq(os.path.join(DATA, "freq", "freqrnc2011.csv"))
    glossary = load_glossary(os.path.join(ROOT, "pipeline", "extra_words.tsv"))
    for line in open(os.path.join(ROOT, "pipeline", "gloss_overrides.tsv"), encoding="utf-8"):
        if line.strip() and not line.startswith("#"):
            word, pos, glosses = line.rstrip("\n").split("\t")
            for key in lex.find(word, {pos}):
                if key[1] == pos:
                    lex.lemmas[key].glosses = [g.strip() for g in glosses.split(";")]

    step("selecting lemmas")
    sel = Selection(lex, index, fq, glossary, merge(groups), args.freq_top, vocab)
    final, obj, score = build_output(sel, fq)
    step("aligning WoW names with English quest text")
    aligned = align_guesses(sel, final, align.Aligner(os.path.join(DATA, "azerothcore")))

    # Lemma ids: most frequent first (shorter ids for common words).
    used = {k for cands in final.values() for k, _ in cands}
    order = sorted(used, key=lambda k: (-score(k), str(k)))
    ids = {k: i + 1 for i, k in enumerate(order)}
    rows = [(obj(k).display, luaout.label(obj(k)), glosses_for(lex, obj(k))) for k in order]
    forms = {f: [(ids[k], luaout.sort_tagsets(ts)) for k, ts in cands] for f, cands in final.items()}
    luaout.write(args.out, rows, forms)
    step(f"wrote {args.out}")

    # ---- report -------------------------------------------------------------------------------------------
    print("\n=== Output")
    sizes = {f: os.path.getsize(os.path.join(args.out, f)) for f in sorted(os.listdir(args.out))}
    for f, s in sizes.items():
        print(f"  {f}: {s / 1e6:.2f} MB")
    n_guess = sum(1 for k in used if k[0] == "guess")
    print(f"  total {sum(sizes.values()) / 1e6:.2f} MB; {len(order)} lemmas ({n_guess} WoW names/guesses), "
          f"{len(forms)} forms; ambiguous forms: {sum(1 for c in final.values() if len(c) > 1)}")
    print(f"  extra_words.tsv entries already in Wiktionary (ignored; use gloss_overrides.tsv): "
          f"{', '.join(sel.glossary_ignored) or '-'}")

    print("\n=== Coverage (share of word tokens that get a tooltip)")
    for g in groups:
        total, direct, parts, missing = coverage(g, final)
        guess_only = sum(n for w, n in g.counts.items() if w in final and all(k[0] == "guess" for k, _ in final[w]))
        print(f"  {g.name}: {100 * (direct + parts) / total:.1f}%  (direct {100 * direct / total:.1f}%, "
              f"hyphen parts {100 * parts / total:.1f}%; WoW names/guesses {100 * guess_only / total:.1f}%)")
        print(f"      unresolved: {', '.join(f'{w}({n})' for w, n in missing.most_common(25))}")

    # Held-out: how well would we cover quests we have NOT seen (like future Forever content)?
    seen = [g for g in groups if "Forever" not in g.name]
    held = next(g for g in groups if "Forever" in g.name)
    sel_h = Selection(lex, index, fq, glossary, merge(seen), args.freq_top, vocab)
    final_h, _, _ = build_output(sel_h, fq)
    total, direct, parts, missing = coverage(held, final_h)
    print("\n=== Held-out test: dictionary built WITHOUT the new Forever quests, measured on them")
    print(f"  {100 * (direct + parts) / total:.1f}% of {total} words  (unresolved: "
          f"{', '.join(f'{w}({n})' for w, n in missing.most_common(20))})")

    all_counts = merge(groups).counts
    ranked = sorted(((sum(all_counts[f] for f in forms), g, en) for g, en, forms in aligned), key=lambda x: -x[0])
    found = sum(n for n, g, en in ranked if en)
    print(f"\n=== Guessed WoW words: {len(ranked)}; with an English name from quest alignment: "
          f"{sum(1 for _, _, en in ranked if en)} (covering {100 * found / max(1, sum(n for n, _, _ in ranked)):.0f}% "
          f"of their occurrences)")
    print("  " + ", ".join(f"{g.display}={en or '?'}({n})" for n, g, en in ranked[:args.show_guesses]))
    step("done")


if __name__ == "__main__":
    sys.exit(main())
