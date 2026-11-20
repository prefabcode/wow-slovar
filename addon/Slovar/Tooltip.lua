-- Tooltip.lua — fills Blizzard's shared GameTooltip for a word. Phase 3 makes it pretty; this proves the data flow.
local _, ns = ...

local GOLD = { 1, 0.82, 0 }
local GREY = { 0.62, 0.62, 0.62 }
local WHITE = { 1, 1, 1 }

local function Line(tip, text, color)
    tip:AddLine(text, color[1], color[2], color[3], true) -- last arg: wrap long lines
end

function ns.ShowTooltip(owner, word)
    local tip = GameTooltip
    tip:SetOwner(owner, "ANCHOR_CURSOR") -- SetOwner also clears the previous contents
    Line(tip, word, WHITE)
    local entries = ns.Lookup(word)
    if not entries then
        Line(tip, "нет в словаре", GREY)
    else
        for i, entry in ipairs(entries) do
            if i > 1 then
                tip:AddLine(" ")
            end
            Line(tip, entry.l .. "  —  " .. entry.p, GOLD)
            Line(tip, entry.g, GREY)
            Line(tip, table.concat(entry.e, "; "), WHITE)
        end
    end
    tip:Show()
end

function ns.HideTooltip(owner)
    if GameTooltip:IsOwned(owner) then
        GameTooltip:Hide()
    end
end
