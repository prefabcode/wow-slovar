-- Saved.lua — words you mark for Anki: hover a word, press the key bound to "Сохранить слово для Anki"
-- (Options -> Keybindings -> Slovar). Kept in SlovarDB.saved; pipeline/anki_export.py turns them into a deck.
--
-- One card per dictionary word: saving волков and later волка both go to the волк card, as example sentences.
local _, ns = ...

local MAX_EXAMPLES = 3

local function Glosses(e)
    local out = {}
    for i = 1, 3 do
        out[#out + 1] = e.e[i] -- e.e can have holes; this packs it
    end
    return out
end

-- Card key for a looked-up word: the dictionary form of the best candidate (or the whole hyphenated word when it
-- was only found part by part).
function ns.SavedKeyFor(word, entries, byParts)
    return byParts and ns.Normalize(word) or ns.Normalize(entries[1].l)
end

function ns.SavedCount()
    local n = 0
    for _ in pairs(ns.db and ns.db.saved or {}) do
        n = n + 1
    end
    return n
end

function ns.SaveWord(word, context)
    local db = ns.db
    if not db then
        return
    end
    local entries, byParts = ns.Lookup(word)
    if not entries then
        ns.Print(("«%s» нет в словаре — сохранять нечего (оно уже в журнале незнакомых слов)"):format(word))
        return
    end
    local key = ns.SavedKeyFor(word, entries, byParts)
    local card = db.saved[key]
    local isNew = card == nil
    if isNew then
        local first = entries[1]
        card = {
            lemma = byParts and word or first.l,
            label = byParts and "" or first.p,
            glosses = byParts and {} or Glosses(first),
            others = {}, -- other readings of the saved form (стали: сталь besides стать), or the parts
            examples = {},
            added = time(),
            count = 0,
        }
        for i = byParts and 1 or 2, #entries do
            local e = entries[i]
            card.others[#card.others + 1] = { lemma = e.l, label = e.p, grammar = e.g, glosses = Glosses(e) }
        end
        db.saved[key] = card
    end
    card.count = card.count + 1
    card.last = time()

    local sentence = type(context) == "string" and ns.Sentence(context, word) or nil
    local known = false
    for _, ex in ipairs(card.examples) do
        known = known or (ex.form == word and ex.sentence == sentence)
    end
    local added = not known and #card.examples < MAX_EXAMPLES
    if added then
        card.examples[#card.examples + 1] = {
            form = word,
            grammar = byParts and "" or entries[1].g, -- e.g. "genitive / accusative plural"
            sentence = sentence,
            quest = ns.CurrentQuestID(),
        }
    end

    if isNew then
        local total = ns.SavedCount()
        local form = ns.Normalize(word) ~= ns.Normalize(card.lemma) and (" (" .. word .. ")") or ""
        ns.Print(("★ %s%s — сохранено для Anki · %d %s"):format(card.lemma, form, total,
            ns.Plural(total, "слово", "слова", "слов")))
    else
        ns.Print(("★ %s уже в списке%s"):format(card.lemma, added and " — добавлен пример" or ""))
    end
    ns.RefreshTooltip() -- show the ★ mark right away
end

-- Bound in Bindings.xml. Global because key-binding code runs in the global environment.
function Slovar_SaveHoveredWord()
    local h = ns.hovered
    -- The mouse may have left the word without a "leave" event (window closed): only trust a visible tooltip.
    if not h or not ns.TooltipShownFor(h.owner) then
        ns.Print("наведи мышь на слово в тексте квеста и нажми клавишу ещё раз")
        return
    end
    ns.SaveWord(h.word, h.context)
end

-- Remove a saved word, given its dictionary form or any form it was saved as. Returns the lemma or nil.
function ns.UnsaveWord(word)
    local saved = ns.db and ns.db.saved
    if not saved then
        return nil
    end
    local target = ns.Normalize(word)
    local entries, byParts = ns.Lookup(word)
    local keys = { target, entries and ns.SavedKeyFor(word, entries, byParts) }
    for _, key in ipairs(keys) do
        if saved[key] then
            local lemma = saved[key].lemma
            saved[key] = nil
            return lemma
        end
    end
    for key, card in pairs(saved) do
        for _, ex in ipairs(card.examples) do
            if ns.Normalize(ex.form) == target then
                saved[key] = nil
                return card.lemma
            end
        end
    end
    return nil
end

-- Saved cards, most recently saved first.
function ns.SavedList()
    local list = {}
    for _, card in pairs(ns.db and ns.db.saved or {}) do
        list[#list + 1] = card
    end
    table.sort(list, function(a, b)
        return (a.last or a.added or 0) > (b.last or b.added or 0)
    end)
    return list
end
