-- Slovar.lua — startup and the /slovar diagnostics used at the Phase 1 checkpoint.
local _, ns = ...

ns.enabled = true -- Phase 3 turns this into /slovar on|off (saved between sessions)

local function Print(msg)
    print("|cffd4af37Slovar|r: " .. msg)
end

-- Startup ------------------------------------------------------------------------------------------------------
-- Addons react to game events through a frame. ADDON_LOADED fires once for each addon (including Blizzard's own
-- load-on-demand UI modules) and PLAYER_LOGIN once the UI is up. Keep retrying until every hook is placed.
local events = CreateFrame("Frame")
events:RegisterEvent("ADDON_LOADED")
events:RegisterEvent("PLAYER_LOGIN")
events:SetScript("OnEvent", function(self)
    if ns.TryHook() then
        self:UnregisterAllEvents()
    end
end)

-- /slovar status -----------------------------------------------------------------------------------------------
local function FrameName(f)
    if not f then
        return "nil"
    end
    local ok, name = pcall(function()
        return f.GetDebugName and f:GetDebugName() or f:GetName()
    end)
    return (ok and name) or tostring(f)
end

local function Call(obj, method)
    if not (obj and obj[method]) then
        return "?"
    end
    local ok, value = pcall(obj[method], obj)
    return ok and tostring(value) or "?"
end

local function Shown(region)
    return region:IsShown() and "shown" or "hidden"
end

local function PrintStatus()
    local version, build, _, interface = GetBuildInfo()
    Print(("client %s (%s), Interface %s, debug %s"):format(tostring(version), tostring(build), tostring(interface),
        ns.debug and "on" or "off"))
    for _, name in ipairs(ns.TARGETS) do
        local fs = _G[name]
        local o = fs and ns.overlays[fs]
        if not fs then
            Print(name .. ": NOT FOUND")
        elseif not ns.hooked[name] then
            Print(name .. ": NOT hooked")
        elseif not o then
            Print(name .. ": hooked, no Russian text seen yet")
        else
            -- "lines 7/7": Blizzard's text vs our invisible copy. Different numbers = the copy wraps differently.
            Print(("%s: text %s, overlay %s | parent %s | lines %s/%s | width %s/%s"):format(
                name, Shown(fs), Shown(o), FrameName(fs:GetParent()),
                Call(fs, "GetNumLines"), Call(o.text, "GetNumLines"),
                Call(fs, "GetWidth"):sub(1, 5), Call(o.text, "GetWidth"):sub(1, 5)))
        end
    end
end

-- /slovar test -------------------------------------------------------------------------------------------------
-- A standalone window with an ordinary visible FontString, made hoverable by ns.Attach: exactly the same path as
-- quest text. If hovering works here but not in quest text, the trick is fine and only the targets need fixing.
local SAMPLE = "Кто-нибудь, помогите! Стаи волков бродят в лесу к востоку от Штормграда, а шайки кобольдов "
    .. "крадут свечи из шахты. Принеси мне ещё 8 шкур — эти земли нужно защитить. Тролли стали сильнее; "
    .. "ты сможешь помочь их убить? (Latin text and «кавычки» stay untouched.)"

local testFrame

local function ShowTest()
    if testFrame then
        testFrame:SetShown(not testFrame:IsShown())
        return
    end
    local ok, f = pcall(CreateFrame, "Frame", "SlovarTestFrame", UIParent, "BasicFrameTemplateWithInset")
    if not ok then -- template missing in this client: plain dark box instead
        f = CreateFrame("Frame", "SlovarTestFrame", UIParent)
        local bg = f:CreateTexture(nil, "BACKGROUND")
        bg:SetAllPoints()
        bg:SetColorTexture(0, 0, 0, 0.85)
    end
    f:SetSize(460, 200)
    f:SetPoint("CENTER")
    f:SetFrameStrata("DIALOG")
    f:SetMovable(true)
    f:EnableMouse(true)
    f:RegisterForDrag("LeftButton")
    f:SetScript("OnDragStart", f.StartMoving)
    f:SetScript("OnDragStop", f.StopMovingOrSizing)
    local title = f.TitleText or (f.TitleContainer and f.TitleContainer.TitleText)
    if title then
        title:SetText("Slovar — тест")
    end
    tinsert(UISpecialFrames, "SlovarTestFrame") -- Esc closes it

    local fs = f:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    fs:SetPoint("TOPLEFT", 18, -36)
    fs:SetPoint("RIGHT", -18, 0)
    fs:SetJustifyH("LEFT")
    ns.Attach(fs)
    fs:SetText(SAMPLE) -- plain text; the overlay picks it up through the SetText hook
    testFrame = f
end

-- Slash commands: WoW registers /slovar from the global SLASH_SLOVAR1 and calls SlashCmdList.SLOVAR(argString).
SLASH_SLOVAR1 = "/slovar"
SlashCmdList.SLOVAR = function(msg)
    local cmd = (msg or ""):match("^%s*(%S*)"):lower()
    if cmd == "test" then
        ShowTest()
    elseif cmd == "status" then
        PrintStatus()
    elseif cmd == "debug" then
        ns.debug = not ns.debug
        ns.RefreshAll()
        Print("debug " .. (ns.debug and "on: the hover layer is drawn in red" or "off"))
    else
        Print("/slovar test — тестовое окно, /slovar status — диагностика, /slovar debug — показать слой наведения")
    end
end
