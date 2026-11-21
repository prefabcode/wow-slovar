-- Slovar.lua — startup and the /slovar command.
local addonName, ns = ...

ns.enabled = true -- replaced by the saved setting (/slovar on|off) once SavedVariables are loaded

local function Print(msg)
    print("|cffd4af37Slovar|r: " .. msg)
end

-- Russian plural agreement: 1 слово, 2 слова, 5 слов, 21 слово, 11 слов.
local function Plural(n, one, few, many)
    local n10, n100 = n % 10, n % 100
    if n10 == 1 and n100 ~= 11 then
        return one
    elseif n10 >= 2 and n10 <= 4 and (n100 < 10 or n100 >= 20) then
        return few
    end
    return many
end

-- Startup ------------------------------------------------------------------------------------------------------
-- Addons react to game events through a frame. ADDON_LOADED fires once for each addon (including Blizzard's own
-- load-on-demand UI modules); for ours, our SavedVariables are loaded by then. PLAYER_LOGIN fires once the UI is
-- up. Keep retrying until every hook is placed.
local events = CreateFrame("Frame")
events:RegisterEvent("ADDON_LOADED")
events:RegisterEvent("PLAYER_LOGIN")
events:SetScript("OnEvent", function(self, event, name)
    if event == "ADDON_LOADED" and name == addonName then
        ns.InitDB()
    end
    if ns.TryHook() and ns.db then
        self:UnregisterAllEvents()
    end
end)

local function SetEnabled(on)
    ns.enabled = on
    if ns.db then
        ns.db.enabled = on
    end
    ns.RefreshAll() -- re-render (or hide) the hover layer of every quest text
    if not on then
        ns.HideAnyTooltip()
    end
    Print(on and "включено" or "выключено")
end

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
    Print(("client %s (%s), Interface %s, %s, debug %s"):format(tostring(version), tostring(build),
        tostring(interface), ns.enabled and "on" or "OFF", ns.debug and "on" or "off"))
    Print(("dictionary: %d words; missing-word log: %d words"):format(
        ns.Data and #ns.Data.lemmas or 0, #ns.MissingSummary()))
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
    if cmd == "on" or cmd == "off" then
        SetEnabled(cmd == "on")
    elseif cmd == "missing" then
        local list = ns.MissingSummary()
        Print(("в журнале %d %s (сохраняется при выходе или /reload)"):format(#list,
            Plural(#list, "слово", "слова", "слов")))
        for i = 1, math.min(10, #list) do
            local e = list[i]
            print(("  %s ×%d  %s"):format(e.word, e.count, e.contexts[1] or ""))
        end
    elseif cmd == "clear" then
        if ns.db then
            wipe(ns.db.missing)
        end
        Print("журнал очищен")
    elseif cmd == "test" then
        ShowTest()
    elseif cmd == "status" then
        PrintStatus()
    elseif cmd == "debug" then
        ns.debug = not ns.debug
        ns.RefreshAll()
        Print("debug " .. (ns.debug and "on: the hover layer is drawn in red" or "off"))
    else
        Print("/slovar on|off — включить/выключить, /slovar missing — журнал незнакомых слов, "
            .. "/slovar clear — очистить журнал, /slovar test, /slovar status, /slovar debug")
    end
end
