"""Turn the words you saved in game (hotkey "Сохранить слово для Anki") into an Anki deck.

    pipeline/.venv/bin/python pipeline/anki_export.py [--wtf PATH] [--out exports/slovar.apkg]

WoW writes the saved words to SavedVariables on /reload or logout, so do one of those first. Then double-click the
.apkg (or Anki: File -> Import). Every export contains all saved words; notes have stable IDs, so importing again
updates the cards you already have (review history kept) and adds the new ones. No duplicates.

One note per dictionary word: front = the quest sentence(s) with the saved form in bold, back = dictionary form,
part of speech, meaning, the grammar of each saved form, and other possible readings.
"""
import argparse
import html
import os
import sys
import time

import genanki

from slovar import savedvars

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(ROOT, "exports", "slovar.apkg")

# Fixed IDs: Anki recognises the note type and deck on every re-import. Never change them (or the fields below).
MODEL_ID = 1734563851
DECK_ID = 1366062196
FIELDS = ["Lemma", "Label", "Meaning", "Examples", "Forms", "Other"]

CSS = """
.card { font-family: -apple-system, "Segoe UI", sans-serif; font-size: 20px; text-align: center;
        color: #222; background: #fafafa; }
.ex { font-size: 22px; margin: 0.6em auto; max-width: 34em; line-height: 1.4; }
.ex b { color: #b8860b; }
.lemma { font-size: 34px; font-weight: bold; margin-top: 0.4em; }
.label { color: #888; font-size: 15px; }
.meaning { font-size: 24px; margin: 0.5em 0; }
.forms, .other { color: #666; font-size: 15px; margin-top: 0.4em; }
.other { color: #999; }
.nightMode .card, .card.nightMode { color: #eee; background: #2b2b2b; }
.nightMode .ex b { color: #f0c040; }
"""

MODEL = genanki.Model(
    MODEL_ID, "Slovar (WoW Forever)",
    fields=[{"name": f} for f in FIELDS],
    templates=[{
        "name": "Russian → English",
        "qfmt": "{{Examples}}",
        "afmt": "{{FrontSide}}<hr id=answer>"
                "<div class=lemma>{{Lemma}}</div><div class=label>{{Label}}</div>"
                "<div class=meaning>{{Meaning}}</div><div class=forms>{{Forms}}</div>"
                "{{#Other}}<div class=other>{{Other}}</div>{{/Other}}",
    }],
    css=CSS,
)


def _bold_form(sentence: str, form: str) -> str:
    text = html.escape(sentence)
    form = html.escape(form)
    i = text.find(form)
    return text if i < 0 else f"{text[:i]}<b>{form}</b>{text[i + len(form):]}"


def note_fields(w: savedvars.SavedWord) -> list[str]:
    examples = [e for e in w.examples if e.get("sentence")][:2]
    if examples:
        front = "".join(f"<div class=ex>{_bold_form(e['sentence'], e['form'])}</div>" for e in examples)
    else:  # saved without a sentence: show the word itself
        front = f"<div class=ex><b>{html.escape(w.examples[0]['form'] if w.examples else w.lemma)}</b></div>"
    forms = "".join(f"<div><b>{html.escape(e['form'])}</b> — {html.escape(e['grammar'])}</div>"
                    for e in w.examples if e.get("grammar"))
    if not w.glosses and w.others:  # hyphenated word found part by part: кобольд (kobold) + вредитель (pest)
        meaning = " + ".join(f"{o.get('lemma', '')} ({o['glosses'][0]})" if o.get("glosses") else o.get("lemma", "")
                             for o in w.others)
        return [html.escape(w.lemma), "", html.escape(meaning), front, forms, ""]
    other = "".join(
        f"<div>{html.escape(o.get('lemma', ''))} — {html.escape(o.get('label', ''))}"
        f"{': ' + html.escape('; '.join(o['glosses'])) if o.get('glosses') else ''}</div>"
        for o in w.others)
    return [html.escape(w.lemma), html.escape(w.label), html.escape("; ".join(w.glosses)), front, forms, other]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wtf", default=savedvars.DEFAULT_WTF, help="WoW WTF folder")
    ap.add_argument("--out", default=DEFAULT_OUT, help="where to write the .apkg")
    args = ap.parse_args()

    words = savedvars.saved_words(args.wtf)
    if not words:
        print(f"No saved words in {args.wtf}/Account/*/SavedVariables/Slovar.lua.\n"
              "In game: hover a word, press your 'Сохранить слово для Anki' key, then /reload or log out.")
        return 1

    deck = genanki.Deck(DECK_ID, "Slovar::WoW Forever")
    for w in words:
        deck.add_note(genanki.Note(model=MODEL, fields=note_fields(w), guid=genanki.guid_for("slovar", w.key),
                                   tags=["slovar"]))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    genanki.Package(deck).write_to_file(args.out)

    # "new since last export": remember the newest save time we exported
    stamp = os.path.join(os.path.dirname(os.path.abspath(args.out)), ".last_export")
    last = int(open(stamp).read().strip() or 0) if os.path.exists(stamp) else 0
    new = [w for w in words if w.added > last]
    open(stamp, "w").write(str(max(w.added for w in words)))

    print(f"{len(words)} words exported, {len(new)} new since the last export"
          + (f": {', '.join(w.lemma for w in new[:15])}{' …' if len(new) > 15 else ''}" if new else "") + ".")
    print(f"Wrote {args.out} ({time.strftime('%H:%M')}). Double-click it (or Anki: File → Import) to add the cards "
          "to the deck «Slovar::WoW Forever»; cards you already have are updated, not duplicated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
