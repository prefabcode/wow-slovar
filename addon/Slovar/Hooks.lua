-- Hooks.lua — makes words in Blizzard's quest text hoverable without modifying Blizzard's text or frames.
--
-- For each quest FontString we put our own small frame exactly on top of it, holding an INVISIBLE copy of the text
-- in which every Cyrillic word is a hyperlink (same font, same width -> same line wrapping). The mouse hits our
-- copy, we show the tooltip. Blizzard's FontString keeps its original text, so:
--   * Blizzard's own hyperlink handler on the quest frames (QuestInfo_OnHyperlinkEnter, which treats every link
--     as a quest ID) never sees our links;
--   * the NPC window's typewriter fade (SetAlphaGradient on QuestInfoDescriptionText) runs on unchanged text;
--   * other addons calling GetText() get clean text.
--
-- Taint, briefly: Blizzard's own UI code runs "secure"; addon code is "tainted". If tainted code replaces Blizzard
-- functions or values, the taint spreads and protected actions can get blocked ("Interface action failed because
-- of an AddOn"). hooksecurefunc avoids that: our function runs AFTER the original, which stays secure. The only
-- thing we do to Blizzard objects is post-hook a few methods on the quest FontStrings to learn about changes.
local _, ns = ...

-- Global FontString names from Blizzard's QuestInfo / QuestFrame UI.
local TARGETS = {
    "QuestInfoTitleHeader", -- quest title (NPC window and quest log)
    "QuestInfoDescriptionText", -- quest text (NPC detail window and quest log description)
    "QuestInfoObjectivesText", -- objectives summary
    "QuestInfoRewardText", -- completion text (turn-in window)
    "QuestProgressTitleText", -- title on the "progress" page (turn-in before it's complete)
    "QuestProgressText", -- progress text
}
ns.TARGETS = TARGETS

ns.hooked = {} -- target name -> true once attached
ns.overlays = {} -- Blizzard FontString -> our overlay frame (created on first Russian text)
local attached = {} -- FontString -> true

-- Hover handlers on OUR overlay frame ----------------------------------------------------------------------------
local function OnHyperlinkEnter(self, link, text, ...)
    if type(link) == "string" and link:sub(1, #ns.LINK_PREFIX) == ns.LINK_PREFIX then
        -- self.target = the Blizzard FontString under our overlay: its plain text gives the sentence for the log
        ns.ShowTooltip(self, link:sub(#ns.LINK_PREFIX + 1), self.target and self.target:GetText())
        return
    end
    -- Someone else's link inside the text (e.g. the quest-type icon in a quest title). Our overlay covers it, so
    -- pass the hover on to the handler of the frame underneath.
    local parent = self:GetParent()
    local handler = parent and parent:GetScript("OnHyperlinkEnter")
    if handler then
        self.forwarded = true
        handler(parent, link, text, ...)
    end
end

local function OnHyperlinkLeave(self, ...)
    ns.HideTooltip(self)
    if self.forwarded then
        self.forwarded = nil
        local parent = self:GetParent()
        local handler = parent and parent:GetScript("OnHyperlinkLeave")
        if handler then
            handler(parent, ...)
        end
    end
end

-- Overlay --------------------------------------------------------------------------------------------------------
-- FontString properties that affect layout; copied from Blizzard's FontString to ours whenever its text changes.
local COPY = {
    { "GetSpacing", "SetSpacing" },
    { "GetJustifyH", "SetJustifyH" },
    { "GetJustifyV", "SetJustifyV" },
    { "GetWordWrap", "SetWordWrap" },
    { "GetNonSpaceWrap", "SetNonSpaceWrap" },
    { "GetIndentedWordWrap", "SetIndentedWordWrap" },
    { "GetMaxLines", "SetMaxLines" },
    { "GetTextScale", "SetTextScale" },
}

local function CopyStyle(shadow, fs)
    local fontObject = fs:GetFontObject()
    if fontObject then
        shadow:SetFontObject(fontObject) -- keeps the font family's Cyrillic glyph mapping
    end
    local file, size, flags = fs:GetFont()
    local sFile, sSize, sFlags = shadow:GetFont()
    if file and (file ~= sFile or size ~= sSize or (flags or "") ~= (sFlags or "")) then
        shadow:SetFont(file, size, flags or "") -- Blizzard overrode the font object's font directly
    end
    for _, pair in ipairs(COPY) do
        local get, set = fs[pair[1]], shadow[pair[2]]
        if get and set then
            local ok, value = pcall(get, fs)
            if ok and value ~= nil then
                pcall(set, shadow, value)
            end
        end
    end
end

local function ApplyColor(overlay)
    if ns.debug then
        overlay.text:SetTextColor(1, 0.15, 0.15, 0.85) -- /slovar debug: show the copy in red to check alignment
    else
        overlay.text:SetTextColor(0, 0, 0, 0) -- invisible, but laid out and hoverable
    end
    overlay.text:SetShadowColor(0, 0, 0, 0)
end

local function CreateOverlay(fs)
    -- A child of the FontString's parent frame: same scroll clipping, same fade, drawn above the parent's text.
    local o = CreateFrame("Frame", nil, fs:GetParent())
    o:SetAllPoints(fs) -- mouse hit area = Blizzard's text area
    o:SetHyperlinksEnabled(true)
    o:SetMouseMotionEnabled(true) -- hover only; clicks pass through
    o:SetScript("OnHyperlinkEnter", OnHyperlinkEnter)
    o:SetScript("OnHyperlinkLeave", OnHyperlinkLeave)
    local text = o:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    -- Pin the left and right edges only: same width as Blizzard's text, height grows with the text (never clipped).
    text:SetPoint("TOPLEFT", o, "TOPLEFT")
    text:SetPoint("TOPRIGHT", o, "TOPRIGHT")
    o.text = text
    o.target = fs
    ns.overlays[fs] = o
    return o
end

-- Keep the overlay on the same parent and with the same visibility as Blizzard's FontString.
-- (QuestInfo_Display moves the quest FontStrings between the NPC window and the map quest log with SetParent.)
local function Sync(fs)
    local o = ns.overlays[fs]
    if not o then
        return
    end
    local parent = fs:GetParent()
    if parent and o:GetParent() ~= parent then
        o:SetParent(parent)
    end
    o:SetShown(o.hasLinks and fs:IsShown() or false)
end

local function Update(fs)
    local raw = fs:GetText()
    local linked = ns.enabled and type(raw) == "string" and ns.Linkify(ns.StripColors(raw)) or ""
    local hasLinks = linked:find("|H" .. ns.LINK_PREFIX, 1, true) ~= nil
    local o = ns.overlays[fs]
    if not o then
        if not hasLinks then
            return
        end
        o = CreateOverlay(fs)
    end
    CopyStyle(o.text, fs)
    ApplyColor(o)
    o.text:SetText(linked)
    o.hasLinks = hasLinks
    Sync(fs)
end

-- Make any FontString hoverable. Also used by /slovar test, and later for gossip and book text.
function ns.Attach(fs)
    if attached[fs] then
        return
    end
    attached[fs] = true
    -- hooksecurefunc(object, "Method", fn) hooks this one object only; fn gets the same arguments as the method.
    hooksecurefunc(fs, "SetText", Update)
    if fs.SetFormattedText then
        hooksecurefunc(fs, "SetFormattedText", Update)
    end
    hooksecurefunc(fs, "SetParent", Sync)
    hooksecurefunc(fs, "Show", Sync)
    hooksecurefunc(fs, "Hide", Sync)
    hooksecurefunc(fs, "SetShown", Sync)
    Update(fs)
end

-- Re-render every overlay (after /slovar debug, and later /slovar on|off).
function ns.RefreshAll()
    for fs in pairs(ns.overlays) do
        Update(fs)
    end
end

-- Attach to whatever quest FontStrings exist yet. Returns true when all are attached.
function ns.TryHook()
    local done = true
    for _, name in ipairs(TARGETS) do
        if not ns.hooked[name] then
            local fs = _G[name]
            if type(fs) == "table" and fs.SetText then
                ns.Attach(fs)
                ns.hooked[name] = true
            else
                done = false
            end
        end
    end
    return done
end
