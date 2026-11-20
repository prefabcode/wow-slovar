-- Offline tests for addon/Slovar/Text.lua. Run from anywhere:  luajit tests/lua/test_text.lua
-- (LuaJIT implements Lua 5.1, the same dialect as WoW.)
local root = (arg and arg[0] or ""):match("^(.*)tests/lua/") or "./"
local ns = {}
assert(loadfile(root .. "addon/Slovar/Text.lua"))("Slovar", ns) -- same `...` the WoW client passes

local passed, failed = 0, 0
local function eq(name, got, want)
    if got == want then
        passed = passed + 1
    else
        failed = failed + 1
        print(("FAIL %s\n  got:  %q\n  want: %q"):format(name, tostring(got), tostring(want)))
    end
end

local function L(w) return "|Haddon:slovar:" .. w .. "|h" .. w .. "|h" end
local function count(s) local _, n = s:gsub("|Haddon:slovar:", "") return n end
local function roundtrip(name, s)
    local linked = ns.Linkify(s)
    eq(name .. " / roundtrip", ns.StripLinks(linked), s)
    eq(name .. " / idempotent", ns.Linkify(linked), linked)
    return linked
end

-- Normalize
eq("upper", ns.Normalize("ШТОРМГРАДА"), "штормграда")
eq("mixed case", ns.Normalize("ПриВЕТ"), "привет")
eq("all upper letters", ns.Normalize("АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"), "абвгдежзийклмнопрстуфхцчшщъыьэюя")
eq("yo lower", ns.Normalize("ещё"), "еще")
eq("yo upper", ns.Normalize("Ёж"), "еж")
eq("stress mark", ns.Normalize("молоко\204\129"), "молоко")
eq("ascii", ns.Normalize("Hello"), "hello")

-- Linkify: words
eq("single word", ns.Linkify("волк"), L("волк"))
eq("two words", ns.Linkify("серый волк"), L("серый") .. " " .. L("волк"))
eq("hyphenated", ns.Linkify("кто-нибудь"), L("кто-нибудь"))
eq("hyphen compound", ns.Linkify("Северо-Западный"), L("Северо-Западный"))
eq("trailing hyphen", ns.Linkify("что- то"), L("что") .. "- " .. L("то"))
eq("dash with spaces", ns.Linkify("волк - лис"), L("волк") .. " - " .. L("лис"))
eq("em dash glued", ns.Linkify("волк—лис"), L("волк") .. "—" .. L("лис"))
eq("guillemets", ns.Linkify("«Волки»,"), "«" .. L("Волки") .. "»,")
eq("latin+digits", ns.Linkify("Принеси 8 шкур (Elwynn)."), L("Принеси") .. " 8 " .. L("шкур") .. " (Elwynn).")
eq("newlines", ns.Linkify("Да.\n\nНет!"), L("Да") .. ".\n\n" .. L("Нет") .. "!")
eq("yo kept in display", ns.Linkify("ещё"), L("ещё"))

-- Linkify: escape sequences pass through
eq("colour", ns.Linkify("|cffff0000Красный|r"), "|cffff0000" .. L("Красный") .. "|r")
eq("named colour", ns.Linkify("|cnNORMAL_FONT_COLOR:Текст|r"), "|cnNORMAL_FONT_COLOR:" .. L("Текст") .. "|r")
eq("existing link", ns.Linkify("|Hitem:123|h[Меч]|h"), "|Hitem:123|h[Меч]|h")
eq("link then word", ns.Linkify("|Hitem:1|h[Меч]|h воина"), "|Hitem:1|h[Меч]|h " .. L("воина"))
eq("texture", ns.Linkify("|TInterface\\Иконка:16|t"), "|TInterface\\Иконка:16|t")
eq("pipe", ns.Linkify("да||нет"), L("да") .. "||" .. L("нет"))
eq("newline escape", ns.Linkify("|nНовая"), "|n" .. L("Новая"))
eq("lone pipe at end", ns.Linkify("текст|"), L("текст") .. "|")
eq("unclosed link", ns.Linkify("|Hitem:1|h[Меч"), "|Hitem:1|h[Меч")

-- Edge cases
eq("empty", ns.Linkify(""), "")
eq("nil", ns.Linkify(nil), nil)
eq("no cyrillic", ns.Linkify("Hello, world! 42"), "Hello, world! 42")
eq("truncated utf8", ns.Linkify("а\208"), L("а") .. "\208")

-- A realistic quest text
local quest = "Привет, $N! Волки из Элвиннского леса нападают на путников у Златоземья. "
    .. "Убей 10 молодых волков и принеси мне 8 кусков мяса — я заплачу тебе 5 серебряных монет.\n\n"
    .. "Кто-нибудь же должен это сделать, верно?"
local linked = roundtrip("quest", quest)
eq("quest word count", count(linked), 29)

-- StripColors (the invisible overlay copy must not contain anything that renders visibly)
eq("strip hex colour", ns.StripColors("|cffffd100Внимание|r: волки"), "Внимание: волки")
eq("strip named colour", ns.StripColors("|cnNORMAL_FONT_COLOR:Текст|r"), "Текст")
eq("strip keeps links", ns.StripColors("|cff0070dd|Hitem:1|h[Меч]|h|r"), "|Hitem:1|h[Меч]|h")
eq("strip keeps textures", ns.StripColors("|TInterface\\X:16|t слово"), "|TInterface\\X:16|t слово")

print(("%d passed, %d failed"):format(passed, failed))
os.exit(failed == 0 and 0 or 1)
