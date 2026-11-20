"""Russian quest text corpora: AzerothCore's ruRU locale tables and Wayfarer's voice-pack subtitles.

Both are only used to decide WHICH words the dictionary must contain; no quest text is written to the output.
"""
import os
import re
from dataclasses import dataclass, field

from . import sqldump

# Race bitmask in quest_template.AllowableRaces. 0 = any race. Draenei (1024) left out: not in WoW Forever.
ALLIANCE = 1 | 4 | 8 | 64  # Human, Dwarf, Night Elf, Gnome
FOREVER_FIRST_ID = 90000  # quests added by WoW Forever have IDs from here up


@dataclass
class Quest:
    id: int
    source: str  # "azerothcore" or "wayfarer"
    level: int | None
    texts: list[str] = field(default_factory=list)

    @property
    def forever_new(self) -> bool:
        return self.id >= FOREVER_FIRST_ID


def clean_ac(text: str) -> str:
    """Drop AzerothCore placeholders: $N name, $C class, $R race, $B line break, $Gmale:female; -> both words,
    |3-6($c) declined class name."""
    text = re.sub(r"\$[Gg]([^:;$]*):([^;$]*);", r"\1 \2", text)
    text = re.sub(r"\|3-\d+\([^)]*\)", " ", text)
    text = re.sub(r"\$[BbNnCcRr]", " ", text)
    return text


def azerothcore(ac_dir: str, max_level: int) -> dict[int, Quest]:
    """Alliance-available quests (incl. neutral) up to max_level, with all their ruRU text."""
    info = {}
    for r in sqldump.rows(os.path.join(ac_dir, "quest_template.sql")):
        qid, level, min_level, races = int(r[0]), int(r[2]), int(r[3]), int(r[73])
        info[qid] = (level if level > 0 else min_level, races)
    quests = {}
    for qid, (level, races) in info.items():
        if 0 < level <= max_level and (races == 0 or races & ALLIANCE):
            quests[qid] = Quest(qid, "azerothcore", level)

    def add(qid, *texts):
        q = quests.get(qid)
        if q:
            q.texts.extend(clean_ac(t) for t in texts if t)

    for r in sqldump.rows(os.path.join(ac_dir, "quest_template_locale.sql")):
        if r[1] == "ruRU":
            add(int(r[0]), *r[2:11])  # Title, Details, Objectives, EndText, CompletedText, ObjectiveText1-4
    for name in ("quest_request_items_locale", "quest_offer_reward_locale"):  # progress text, completion text
        for r in sqldump.rows(os.path.join(ac_dir, f"{name}.sql")):
            if r[1] == "ruRU":
                add(int(r[0]), r[2])
    return {qid: q for qid, q in quests.items() if q.texts}


# (table, index of the locale column, indexes of text columns)
VOCAB_TABLES = [
    ("item_template_locale", 1, [2, 3]),  # item name, description
    ("creature_template_locale", 1, [2, 3]),  # NPC name, title
    ("gameobject_template_locale", 1, [2, 3]),  # object name, cast bar caption
    ("npc_text_locale", 1, list(range(2, 18))),  # NPC gossip text
    ("page_text_locale", 1, [2]),  # books, letters, plaques
    ("gossip_menu_option_locale", 2, [3, 4]),  # gossip menu options
]


def wow_vocabulary(ac_dir: str) -> list[Quest]:
    """Other ruRU text from AzerothCore (names, gossip, books): only used to pick vocabulary."""
    texts = []
    for table, loc_col, cols in VOCAB_TABLES:
        path = os.path.join(ac_dir, f"{table}.sql")
        if os.path.exists(path):
            for r in sqldump.rows(path):
                if r[loc_col] == "ruRU":
                    texts.extend(clean_ac(r[c]) for c in cols if c < len(r) and r[c])
    return [Quest(0, "azerothcore-vocab", None, texts)]


def ac_levels(ac_dir: str) -> dict[int, int]:
    levels = {}
    for r in sqldump.rows(os.path.join(ac_dir, "quest_template.sql")):
        level, min_level = int(r[2]), int(r[3])
        levels[int(r[0])] = level if level > 0 else min_level
    return levels


_LUA_STR = r'"((?:[^"\\]|\\.)*)"'


def _lua_unescape(s: str) -> str:
    return re.sub(r"\\(\d{1,3}|.)", lambda m: chr(int(m[1])) if m[1].isdigit() else
                  {"n": "\n", "t": "\t"}.get(m[1], m[1]), s)


WAYFARER_PACKS = ("Wayfarer_Voices_Alliance", "Wayfarer_Voices_Shared", "Wayfarer_Voices_Narrator")


def wayfarer(addons_dir: str, max_level: int, fallback_levels: dict[int, int]) -> dict[int, Quest]:
    """Quest subtitles from the installed Wayfarer voice packs (Alliance, shared, narrator) up to max_level.
    Level comes from WayfarerRU's QuestBook (covers WoW Forever quests), else AzerothCore; unknown -> included."""
    book = {}
    book_path = os.path.join(addons_dir, "WayfarerRU", "QuestBook.lua")
    for m in re.finditer(r"\n        \[(\d+)\] = \{ -?\d+, " + _LUA_STR + r", (\d+) \}", open(book_path, encoding="utf-8").read()):
        book[int(m[1])] = (_lua_unescape(m[2]), int(m[3]))
    quests = {}
    for pack in WAYFARER_PACKS:
        path = os.path.join(addons_dir, pack, "Index.lua")
        if not os.path.exists(path):
            continue
        src = open(path, encoding="utf-8").read()
        start = re.search(r"\n    q = \{", src)
        if not start:
            continue
        end = src.find("\n    }", start.end())  # the q = { ... } section closes at 4-space indent
        parts = re.split(r"\n        \[(\d+)\] = ", src[start.end():end if end > 0 else None])
        for qid_s, body in zip(parts[1::2], parts[2::2]):
            qid = int(qid_s)
            title, level = book.get(qid, (None, fallback_levels.get(qid)))
            if level is not None and level > max_level:
                continue
            q = quests.setdefault(qid, Quest(qid, "wayfarer", level, [title] if title else []))
            q.texts.extend(_lua_unescape(t) for t in re.findall(r"\{ [\d.]+, " + _LUA_STR + r" \}", body))
    return quests
