-- Log.lua — settings, the missing-word log and shared helpers; data kept in SavedVariables.
--
-- SavedVariables: the .toc names a global (SlovarDB); WoW loads it from
-- WTF/Account/<account>/SavedVariables/Slovar.lua before ADDON_LOADED fires for this addon and writes it back on
-- logout or /reload. pipeline/missing.py reads that file, and pipeline/build.py adds the logged words.
local _, ns = ...

local MAX_WORDS = 2000
local MAX_CONTEXTS = 3
local MAX_SENTENCE = 300 -- bytes

function ns.Print(msg)
    print("|cffd4af37Slovar|r: " .. msg) -- print() goes to the chat window in WoW
end

function ns.InitDB()
    SlovarDB = type(SlovarDB) == "table" and SlovarDB or {}
    local db = SlovarDB
    db.version = 1
    if db.enabled == nil then
        db.enabled = true
    end
    db.missing = type(db.missing) == "table" and db.missing or {}
    db.saved = type(db.saved) == "table" and db.saved or {} -- words saved for Anki (Saved.lua)
    ns.db = db
    ns.enabled = db.enabled
end

-- The sentence of `text` that contains `word` (plain text, colour codes removed).
function ns.Sentence(text, word)
    text = ns.StripColors(text):gsub("|n", "\n")
    local s, e = text:find(word, 1, true)
    if not s then
        return nil
    end
    local first = 1
    for i = s - 1, 1, -1 do
        local c = text:sub(i, i)
        if c == "." or c == "!" or c == "?" or c == "\n" then
            first = i + 1
            break
        end
    end
    local last = text:find("[%.!%?\n]", e + 1) or #text
    local sentence = text:sub(first, last):gsub("^%s+", ""):gsub("%s+$", "")
    if #sentence > MAX_SENTENCE then
        local cut = MAX_SENTENCE
        while cut > 0 and (sentence:byte(cut + 1) or 0) >= 128 and sentence:byte(cut + 1) < 192 do
            cut = cut - 1 -- don't cut a 2-byte Cyrillic letter in half
        end
        sentence = sentence:sub(1, cut) .. "…"
    end
    return sentence
end

function ns.CurrentQuestID()
    local ok, id = pcall(GetQuestID) -- quest in the NPC window
    if (not ok or not id or id == 0) and C_QuestLog and C_QuestLog.GetSelectedQuest then
        ok, id = pcall(C_QuestLog.GetSelectedQuest) -- quest selected in the quest log
    end
    return ok and id and id ~= 0 and id or nil
end

-- Record a word that isn't in the dictionary. Returns true if it was logged.
function ns.LogMissing(word, context)
    local db = ns.db
    if not db then
        return false
    end
    local key = ns.Normalize(word)
    local entry = db.missing[key]
    if not entry then
        local n = 0
        for _ in pairs(db.missing) do
            n = n + 1
        end
        if n >= MAX_WORDS then
            return false
        end
        entry = { word = word, count = 0, contexts = {} }
        db.missing[key] = entry
    end
    entry.count = entry.count + 1
    entry.last = time()
    entry.quest = ns.CurrentQuestID() or entry.quest
    local sentence = type(context) == "string" and ns.Sentence(context, word)
    if sentence and #entry.contexts < MAX_CONTEXTS then
        for _, s in ipairs(entry.contexts) do
            if s == sentence then
                return true
            end
        end
        entry.contexts[#entry.contexts + 1] = sentence
    end
    return true
end

function ns.MissingSummary()
    local list = {}
    for _, entry in pairs(ns.db and ns.db.missing or {}) do
        list[#list + 1] = entry
    end
    table.sort(list, function(a, b)
        return (a.last or 0) > (b.last or 0)
    end)
    return list
end
