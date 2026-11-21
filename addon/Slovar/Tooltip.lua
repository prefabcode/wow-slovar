-- Tooltip.lua — the word tooltip.
--
-- We use our own tooltip frame (same look as Blizzard's) instead of the shared GameTooltip: we change the font of
-- individual lines (lemma in the large header font), and doing that on GameTooltip would leak into item tooltips
-- and other addons that reuse its lines.
local _, ns = ...

local tip = CreateFrame("GameTooltip", "SlovarTooltip", UIParent, "GameTooltipTemplate")

local GOLD = { 1, 0.82, 0 }
local GREY = { 0.62, 0.62, 0.62 }
local WHITE = { 1, 1, 1 }

-- Fonts of the line just added (lines are created on demand as SlovarTooltipTextLeftN / RightN).
local function Fonts(left, right)
    local n = tip:NumLines()
    _G["SlovarTooltipTextLeft" .. n]:SetFontObject(left)
    _G["SlovarTooltipTextRight" .. n]:SetFontObject(right or left)
end

local function Line(text, color, font)
    tip:AddLine(text, color[1], color[2], color[3], true) -- true: wrap long lines
    Fonts(font)
end

local function Entry(e)
    -- лемма (large, gold) .................. part of speech (small, grey)
    tip:AddDoubleLine(e.l, e.p, GOLD[1], GOLD[2], GOLD[3], GREY[1], GREY[2], GREY[3])
    Fonts(GameTooltipHeaderText, GameTooltipTextSmall)
    if e.g ~= "" then
        Line(e.g, GREY, GameTooltipTextSmall) -- which form: "genitive / accusative plural"
    end
    local glosses = {}
    for i = 1, 3 do
        glosses[#glosses + 1] = e.e[i]
    end
    if #glosses > 0 then
        Line(table.concat(glosses, "; "), WHITE, GameTooltipText)
    end
end

-- Bottom line: ★ if the word is saved for Anki, else which key saves it (only once a key is bound).
local function AnkiLine(word, entries, byParts)
    local saved = ns.db and ns.db.saved[ns.SavedKeyFor(word, entries, byParts)]
    local key = not saved and GetBindingKey and GetBindingKey("SLOVAR_SAVE_WORD")
    if saved or key then
        Line(" ", GREY, GameTooltipTextSmall)
        if saved then
            Line("★ в списке для Anki", GOLD, GameTooltipTextSmall)
        else
            Line(((GetBindingText and GetBindingText(key)) or key) .. " — сохранить для Anki", GREY,
                GameTooltipTextSmall)
        end
    end
end

local current -- { owner, word, context } of the tooltip on screen, for RefreshTooltip

-- owner: the frame the mouse is over; word: as written in the text; context: the whole text it came from.
function ns.ShowTooltip(owner, word, context)
    current = { owner = owner, word = word, context = context }
    tip:SetOwner(owner, "ANCHOR_CURSOR") -- also clears the previous contents
    local entries, byParts = ns.Lookup(word)
    if not entries then
        Line(word, WHITE, GameTooltipHeaderText)
        local logged = ns.LogMissing(word, context)
        Line(logged and "нет в словаре — записано" or "нет в словаре", GREY, GameTooltipTextSmall)
    else
        if byParts then
            Line(word .. " — по частям", GREY, GameTooltipTextSmall)
        end
        for i, e in ipairs(entries) do
            if i > 1 then
                Line(" ", GREY, GameTooltipTextSmall) -- small gap between candidates
            end
            Entry(e)
        end
        AnkiLine(word, entries, byParts)
    end
    tip:Show()
end

function ns.TooltipShownFor(owner)
    return owner ~= nil and tip:IsShown() and tip:IsOwned(owner)
end

-- Redraw the tooltip on screen (after saving a word). Found words only, so the missing-word log isn't touched.
function ns.RefreshTooltip()
    if current and ns.TooltipShownFor(current.owner) and ns.Lookup(current.word) then
        ns.ShowTooltip(current.owner, current.word, current.context)
    end
end

function ns.HideTooltip(owner)
    if tip:IsOwned(owner) then
        tip:Hide()
    end
end

function ns.HideAnyTooltip()
    tip:Hide()
end
