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

## Dev loop

- Edited a `.lua` file: `/reload` in game.
- Added or renamed a file, or edited the `.toc`: restart the client.
- Tokenizer tests: `luajit tests/lua/test_text.lua`.
- In game: `/slovar test` opens a test window, `/slovar status` prints hook diagnostics, and `/slovar debug` draws
  the invisible hover layer in red so you can check it lines up with the text.

## How the hover works

Blizzard's quest FontStrings are never modified. The addon post-hooks them (`hooksecurefunc`) and places its own
frame on top of each one. That frame holds an invisible copy of the text with every Cyrillic word wrapped in a
hyperlink (`|Haddon:slovar:слово|hслово|h`), so hovering over a word fires our own `OnHyperlinkEnter`. Blizzard's
quest frames have their own hyperlink handler that treats every link as a quest ID, and the NPC window animates the
original text, so changing Blizzard's text directly breaks both.
