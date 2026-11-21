# Slovar

A World of Warcraft: Forever addon for Russian immersion. Hover over any Russian word in quest text to see its
dictionary form, part of speech, grammatical form (e.g. "genitive plural") and English glosses. Everything comes
from an offline dictionary that ships with the addon.

## Layout

```
addon/Slovar/    the addon itself (this folder goes into Interface/AddOns)
tests/lua/       offline tests for the pure-Lua parts (run with luajit)
scripts/         install helper
pipeline/        Python pipeline that builds the dictionary (Phase 2)
data/            big downloads for the pipeline (git-ignored)
```

## Install

```sh
scripts/install.sh          # symlinks addon/Slovar into _forever_/Interface/AddOns
scripts/install.sh --copy   # copies instead, if the client doesn't pick up the symlink
```

The default target is `/Volumes/PerkDrive/games/World of Warcraft/_forever_/Interface/AddOns`. Override it with
`WOW_ADDONS=...`.

## In game

- `/slovar on` / `/slovar off` turns hovering on or off. The setting is remembered.
- `/slovar missing` lists the words you hovered that weren't in the dictionary; `/slovar clear` empties that log.
- `/slovar status` shows hook diagnostics, `/slovar test` opens a test window, and `/slovar debug` shows the hover layer.

## Fixing missing words

Words you hover that the dictionary doesn't have are logged, together with their sentence, to
`WTF/Account/<account>/SavedVariables/Slovar.lua`. WoW writes that file when you log out or `/reload`.

```sh
pipeline/.venv/bin/python pipeline/missing.py   # what's missing, and how to fix each word
pipeline/.venv/bin/python pipeline/build.py     # reads the same log: words Wiktionary has get added
```

Words that aren't in Wiktionary at all, like WoW names or the odd verb such as поохотиться, need a line in
`pipeline/extra_words.tsv` (`dictionary form<TAB>English`). After rebuilding, `/reload` in game.

## Dev loop

- Edited a `.lua` file: `/reload` in game.
- Added or renamed a file, or edited the `.toc`: restart the client.
- Tokenizer tests: `luajit tests/lua/test_text.lua`.
- In game: `/slovar test` opens a test window, `/slovar status` prints hook diagnostics, and `/slovar debug` draws
  the invisible hover layer in red so you can check it lines up with the text.

## Dictionary pipeline

```sh
python3 pipeline/fetch.py                                    # source data into data/ (~250 MB, git-ignored)
python3 -m venv pipeline/.venv && pipeline/.venv/bin/pip install -r pipeline/requirements.txt
pipeline/.venv/bin/python pipeline/build.py                  # writes addon/Slovar/Data/*.lua + coverage report
luajit tests/lua/lookup.lua волков стали Штормграде           # look words up with the addon's own Lua code
```

`build.py` reads Russian quest text from AzerothCore (Alliance quests up to `--max-level 30`) and from the
installed Wayfarer voice packs, including WoW Forever's new quests. It then picks every dictionary word those
quests use, plus the 10,000 most frequent Russian words (`--freq-top`), and writes every inflected form of each.
WoW names that Wiktionary lacks get their forms from pymorphy3. Their English names come from matching Russian and
English quest text (`pipeline/slovar/align.py`); you can correct them in `pipeline/extra_words.tsv`, and fix
misleading glosses in `pipeline/gloss_overrides.tsv`.

Sources:
- [kaikki.org](https://kaikki.org/dictionary/Russian/): English Wiktionary's Russian entries (CC BY-SA 4.0). This
  is where the glosses and inflection tables come from.
- [pymorphy3](https://github.com/no-plagiarism/pymorphy3) with the OpenCorpora dictionary (CC BY-SA): forms of
  words that Wiktionary lacks.
- Lyashevskaya & Sharoff's frequency dictionary from the Russian National Corpus
  ([dict.ruslang.ru](http://dict.ruslang.ru/freq.php)): which words count as common.
- [AzerothCore](https://github.com/azerothcore/azerothcore-wotlk) quest tables and Wayfarer's subtitles: used
  only to choose words and align names. No quest text ends up in the output.

The generated data is derived from Wiktionary, so if this addon is ever shared, it falls under CC BY-SA.

## How the hover works

Blizzard's quest FontStrings are never modified. The addon post-hooks them (`hooksecurefunc`) and places its own
frame on top of each one. That frame holds an invisible copy of the text with every Cyrillic word wrapped in a
hyperlink (`|Haddon:slovar:слово|hслово|h`), so hovering over a word fires our own `OnHyperlinkEnter`. Blizzard's
quest frames have their own hyperlink handler that treats every link as a quest ID, and the NPC window animates the
original text, so changing Blizzard's text directly breaks both.
