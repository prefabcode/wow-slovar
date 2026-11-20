"""Download the pipeline's source data into data/ (git-ignored). Safe to re-run: skips files already present.

    python3 pipeline/fetch.py
"""
import os
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
AC = "https://raw.githubusercontent.com/azerothcore/azerothcore-wotlk/master/data/sql/base/db_world/"
FILES = {
    "kaikki/ru-en.jsonl.gz": "https://kaikki.org/dictionary/Russian/kaikki.org-dictionary-Russian.jsonl.gz",
    "freq/Freq2011.zip": "http://dict.ruslang.ru/Freq2011.zip",
    **{f"azerothcore/{t}.sql": f"{AC}{t}.sql" for t in (
        "quest_template", "quest_template_locale", "quest_request_items_locale", "quest_offer_reward_locale",
        # only needed for build.py --vocab:
        "item_template_locale", "creature_template_locale", "gameobject_template_locale", "npc_text_locale",
        "page_text_locale", "gossip_menu_option_locale")},
}


def main():
    for rel, url in FILES.items():
        path = os.path.join(DATA, rel)
        if os.path.exists(path):
            print(f"have {rel}")
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        print(f"downloading {rel} ...", flush=True)
        urllib.request.urlretrieve(url, path + ".part")
        os.replace(path + ".part", path)
    freq_csv = os.path.join(DATA, "freq", "freqrnc2011.csv")
    if not os.path.exists(freq_csv):
        with zipfile.ZipFile(os.path.join(DATA, "freq", "Freq2011.zip")) as z:
            z.extract("freqrnc2011.csv", os.path.join(DATA, "freq"))
    print("ok")


if __name__ == "__main__":
    main()
