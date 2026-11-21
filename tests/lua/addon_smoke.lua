-- Loads the whole addon (in .toc order) against a small fake of the WoW API and plays through hovering, the
-- missing-word log, saving words for Anki and the /slovar commands.
--   luajit tests/lua/addon_smoke.lua [path/to/Slovar.lua]
-- With a path, also writes SlovarDB there in WoW's SavedVariables format (input for pipeline/anki_export.py).
local ROOT = (arg and arg[0] or ""):match("^(.*)tests/lua/") or "./"
local OUT = arg[1]

-- Fake WoW API ------------------------------------------------------------------------------------------------
local noop = function() end
local function obj(fields)
    return setmetatable(fields or {}, { __index = function() return noop end })
end
local function region(parent)
    local r = obj({ _parent = parent, _shown = true, _font = { "Fonts\\FRIZQT___CYR.TTF", 13, "" } })
    function r:SetText(t) self._text = t end
    function r:GetText() return self._text end
    function r:GetParent() return self._parent end
    function r:SetParent(p) self._parent = p end
    function r:Show() self._shown = true end
    function r:Hide() self._shown = false end
    function r:SetShown(v) self._shown = not not v end
    function r:IsShown() return self._shown end
    function r:GetFont() return unpack(self._font) end
    function r:SetFont(a, b, c) self._font = { a, b, c } end
    function r:GetFontObject() return "QuestFont" end
    function r:SetFontObject(f) self._fontObject = f end
    function r:SetTextColor(_, _, _, a) self._alpha = a end
    return r
end
local function frame(name, parent)
    local f = region(parent)
    f._scripts, f._name, f.questInfoHyperlinksInstalled = {}, name, false
    function f:SetScript(s, fn) self._scripts[s] = fn end
    function f:GetScript(s) return self._scripts[s] end
    function f:GetName() return self._name end
    function f:UnregisterAllEvents() self._unreg = true end
    function f:CreateFontString() local fs = region(self); self._fs = fs; return fs end
    function f:CreateTexture() return obj() end
    f.TitleText = obj()
    return f
end
local function tooltip(name)
    local t = frame(name)
    t._lines, t._shown = {}, false
    function t:SetOwner(o) self.owner = o; self._lines = {} end
    function t:IsOwned(o) return self.owner == o end
    function t:Hide() self.owner = nil; self._shown = false end
    function t:NumLines() return #self._lines end
    local function line(self, l, r)
        local n = #self._lines + 1
        self._lines[n] = { l = l, r = r }
        _G[name .. "TextLeft" .. n] = _G[name .. "TextLeft" .. n] or region(self)
        _G[name .. "TextRight" .. n] = _G[name .. "TextRight" .. n] or region(self)
    end
    function t:AddLine(text) line(self, text) end
    function t:AddDoubleLine(l, r) line(self, l, r) end
    return t
end
local frames = {}
function CreateFrame(kind, name, parent)
    local f = kind == "GameTooltip" and tooltip(name) or frame(name, parent)
    frames[#frames + 1] = f
    if name then _G[name] = f end
    return f
end
UIParent, WorldFrame = frame("UIParent"), frame("WorldFrame")
UISpecialFrames, SlashCmdList, tinsert = {}, {}, table.insert
GameTooltipHeaderText, GameTooltipText, GameTooltipTextSmall = "HeaderFont", "TextFont", "SmallFont"
GameTooltip = obj()
function wipe(t) for k in pairs(t) do t[k] = nil end return t end
local clock = 1763650000
function time() clock = clock + 1; return clock end
function GetQuestID() return 0 end
C_QuestLog = { GetSelectedQuest = function() return 33 end }
function GetBuildInfo() return "1.60.1", "70959", "Nov 2026", 16001 end
function geterrorhandler() return function(e) error(e) end end
local boundKey = nil
function GetBindingKey(action) return action == "SLOVAR_SAVE_WORD" and boundKey or nil end
function GetBindingText(key) return "<" .. key .. ">" end
function hooksecurefunc(a, b, c)
    if type(a) == "string" then
        local orig = _G[a]
        _G[a] = function(...) orig(...) b(...) end
    else
        local orig = a[b]
        a[b] = function(...) local r = { orig(...) }; c(...); return unpack(r) end
    end
end
local chat = {}
print = function(s) chat[#chat + 1] = s end

-- Blizzard's quest UI, reduced to what matters: QuestInfo_Display installs its own link handler (which breaks on
-- links that aren't quest IDs) and moves the FontStrings to the window's scroll child.
local function QuestInfo_OnHyperlinkEnter(_, link)
    assert(tonumber(link:match("^[^:]+:(.*)$")), "Blizzard's handler received one of our links")
end
for _, n in ipairs({ "QuestInfoTitleHeader", "QuestInfoDescriptionText", "QuestInfoObjectivesText",
    "QuestInfoRewardText", "QuestProgressTitleText", "QuestProgressText" }) do
    _G[n] = region(frame("holder"))
end
local detailChild = frame("QuestDetailScrollChildFrame")
local QUEST_TEXT = "Хочешь поохотиться? Убей зараженных молодых волков в долине.\n\n"
    .. "Кобольдов-вредителей тоже. Без волка не возвращайся!"
function QuestInfo_Display(_, parent)
    if not parent.questInfoHyperlinksInstalled then
        parent.questInfoHyperlinksInstalled = true
        assert(parent:GetScript("OnHyperlinkEnter") == nil, "Blizzard's assert")
        parent:SetScript("OnHyperlinkEnter", QuestInfo_OnHyperlinkEnter)
    end
    QuestInfoDescriptionText:SetText(QUEST_TEXT)
    QuestInfoDescriptionText:SetParent(parent)
end

-- Load the addon -----------------------------------------------------------------------------------------------
local ns = {}
for line in io.lines(ROOT .. "addon/Slovar/Slovar.toc") do
    if line ~= "" and not line:match("^##") then
        assert(loadfile(ROOT .. "addon/Slovar/" .. line:gsub("\\", "/")))("Slovar", ns)
    end
end
local events
for _, f in ipairs(frames) do
    events = events or (f._scripts.OnEvent and f)
end
events._scripts.OnEvent(events, "ADDON_LOADED", "Slovar")
assert(ns.db and SlovarDB.enabled == true and events._unreg, "SavedVariables initialised and hooks placed")
assert(BINDING_NAME_SLOVAR_SAVE_WORD and type(Slovar_SaveHoveredWord) == "function", "key binding globals")

-- Play ---------------------------------------------------------------------------------------------------------
QuestInfo_Display("detail", detailChild)
local o = ns.overlays[QuestInfoDescriptionText]
assert(o and o:IsShown(), "hover layer over the quest text")
local tip = SlovarTooltip

local function hover(word)
    o._scripts.OnHyperlinkEnter(o, "addon:slovar:" .. word, word)
end
local function lines()
    local out = {}
    for _, l in ipairs(tip._lines) do
        out[#out + 1] = l.l .. (l.r and (" | " .. l.r) or "")
    end
    return table.concat(out, "\n")
end
local function lastChat()
    return chat[#chat] or ""
end

local failed = 0
local function check(cond, what)
    if not cond then
        failed = failed + 1
        print = io.write
        io.write("FAIL: " .. what .. "\n  tooltip:\n" .. lines() .. "\n  chat: " .. lastChat() .. "\n")
    end
end

hover("волков")
check(tip._lines[1].l == "волк" and SlovarTooltipTextLeft1._fontObject == "HeaderFont", "lemma line, header font")
check(not lines():find("Anki", 1, true), "no Anki hint while no key is bound")
boundKey = "F"
hover("волков")
check(lines():find("<F> — сохранить для Anki", 1, true), "hint with the bound key")

Slovar_SaveHoveredWord()
local card = SlovarDB.saved["волк"]
check(card and card.lemma == "волк" and card.glosses[1] == "wolf", "saved under the dictionary form")
check(card and card.examples[1].form == "волков" and card.examples[1].grammar:find("genitive", 1, true)
    and card.examples[1].sentence == "Убей зараженных молодых волков в долине." and card.examples[1].quest == 33,
    "example: form, grammar, sentence, quest")
check(lastChat():find("★ волк (волков) — сохранено для Anki · 1 слово", 1, true), "chat confirmation")
check(lines():find("★ в списке для Anki", 1, true), "tooltip redrawn with the saved mark")

Slovar_SaveHoveredWord()
check(lastChat():find("уже в списке", 1, true) and #card.examples == 1, "same word again: no duplicate example")
hover("волка")
Slovar_SaveHoveredWord()
check(#card.examples == 2 and card.examples[2].form == "волка", "another form adds an example to the same card")
check(lastChat():find("добавлен пример", 1, true), "chat: example added")

hover("стали")
Slovar_SaveHoveredWord()
local stat = SlovarDB.saved["стать"]
check(stat and stat.others[1] and stat.others[1].lemma == "сталь", "ambiguous word keeps the other reading")

hover("Кобольдов-вредителей")
Slovar_SaveHoveredWord()
check(SlovarDB.saved["кобольдов-вредителей"] and #SlovarDB.saved["кобольдов-вредителей"].others == 2,
    "hyphenated word saved with its parts")

hover("поохотиться")
Slovar_SaveHoveredWord()
check(lastChat():find("нет в словаре", 1, true) and not SlovarDB.saved["поохотиться"], "unknown word not saved")
check(SlovarDB.missing["поохотиться"], "unknown word is in the missing-word log")

o._scripts.OnHyperlinkLeave(o)
Slovar_SaveHoveredWord()
check(lastChat():find("наведи мышь", 1, true), "key without a hovered word: hint")

SlashCmdList.SLOVAR("saved")
check(chat[#chat - 3]:find("сохранено 3 слова", 1, true), "/slovar saved count, with Russian plural")
SlashCmdList.SLOVAR("unsave волков")
check(SlovarDB.saved["волк"] == nil and lastChat():find("«волк» убрано", 1, true), "/slovar unsave by form")
SlashCmdList.SLOVAR("unsave волков")
check(lastChat():find("нет в списке", 1, true), "/slovar unsave of a word not saved")
hover("волков")
Slovar_SaveHoveredWord() -- save it again for the export test
hover("волка")
Slovar_SaveHoveredWord()

SlashCmdList.SLOVAR("off")
check(not o:IsShown() and SlovarDB.enabled == false, "/slovar off hides the hover layer and is saved")
SlashCmdList.SLOVAR("on")
check(o:IsShown() and SlovarDB.enabled == true, "/slovar on")

-- SavedVariables output, the way WoW writes it ---------------------------------------------------------------
if OUT then
    local function dump(v, indent)
        if type(v) == "string" then return ("%q"):format(v) end
        if type(v) ~= "table" then return tostring(v) end
        local parts = { "{" }
        for k, val in pairs(v) do
            if type(k) == "number" then
                parts[#parts + 1] = indent .. dump(val, indent .. "\t") .. ", -- [" .. k .. "]"
            else
                parts[#parts + 1] = indent .. "[" .. ("%q"):format(k) .. "] = " .. dump(val, indent .. "\t") .. ","
            end
        end
        parts[#parts + 1] = indent:sub(2) .. "}"
        return table.concat(parts, "\n")
    end
    io.open(OUT, "w"):write("\nSlovarDB = " .. dump(SlovarDB, "\t") .. "\n")
end

io.write(failed == 0 and "addon smoke test passed\n" or (failed .. " addon smoke checks failed\n"))
os.exit(failed == 0 and 0 or 1)
