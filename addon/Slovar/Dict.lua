-- Dict.lua — Phase 1 mini dictionary. Phase 2 generates the real data from Wiktionary in the same shape.
--
-- Keys are normalized forms (lowercase, ё -> е). Each form maps to a LIST of candidates, because one form can
-- belong to several lemmas (стали: сталь or стать). Fields: l = lemma, p = part of speech, g = which form this
-- is, e = English glosses.
local _, ns = ...

ns.Dict = {
    ["волков"] = { { l = "волк", p = "noun, masc., animate", g = "genitive plural; accusative plural", e = { "wolf" } } },
    ["кобольдов"] = { { l = "кобольд", p = "noun, masc., animate", g = "genitive plural; accusative plural", e = { "kobold" } } },
    ["лесу"] = { { l = "лес", p = "noun, masc.", g = "locative singular (в лесу); dative singular", e = { "forest", "woods" } } },
    ["убить"] = { { l = "убить", p = "verb, perfective", g = "infinitive", e = { "to kill" } } },
    ["принеси"] = { { l = "принести", p = "verb, perfective", g = "imperative singular", e = { "to bring", "to fetch" } } },
    ["помочь"] = { { l = "помочь", p = "verb, perfective", g = "infinitive", e = { "to help" } } },
    ["мне"] = { { l = "я", p = "pronoun, personal", g = "dative; prepositional", e = { "I", "me" } } },
    ["земли"] = { { l = "земля", p = "noun, fem.", g = "genitive singular; nominative plural; accusative plural", e = { "land", "earth", "soil" } } },
    ["штормграда"] = { { l = "Штормград", p = "proper noun, masc.", g = "genitive singular", e = { "Stormwind" } } },
    ["еще"] = { { l = "ещё", p = "adverb", g = "invariable", e = { "still", "yet", "more" } } },
    ["кто-нибудь"] = { { l = "кто-нибудь", p = "pronoun, indefinite", g = "nominative", e = { "someone", "anyone" } } },
    ["стали"] = {
        { l = "сталь", p = "noun, fem.", g = "genitive / dative / prepositional singular; nominative / accusative plural", e = { "steel" } },
        { l = "стать", p = "verb, perfective", g = "past tense, plural", e = { "to become", "to begin (to do)", "to stand" } },
    },
}

function ns.Lookup(word)
    return ns.Dict[ns.Normalize(word)]
end
