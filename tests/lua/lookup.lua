-- Look words up in the generated dictionary from the command line, using the addon's own Lua code:
--   luajit tests/lua/lookup.lua волков стали Штормграде
-- With no arguments, runs the built-in checks.
local root = (arg and arg[0] or ""):match("^(.*)tests/lua/") or "./"
local ns = {}
for _, file in ipairs({ "Text.lua", "Data/Lemmas.lua", "Data/Forms.lua", "Lookup.lua", "Dict.lua" }) do
    assert(loadfile(root .. "addon/Slovar/" .. file))("Slovar", ns)
end

local function Show(word)
    local entries, byParts = ns.Lookup(word)
    print(word .. (byParts and "  (по частям)" or ""))
    if not entries then
        print("   (нет в словаре)")
        return
    end
    for _, e in ipairs(entries) do
        local glosses = {}
        for i = 1, 3 do
            glosses[#glosses + 1] = e.e[i]
        end
        print(("   %s — %s\n      %s\n      %s"):format(e.l, e.p, e.g, table.concat(glosses, "; ")))
    end
end

if arg[1] then
    for _, w in ipairs(arg) do
        Show(w)
    end
    return
end

local failed = 0
local function expect(word, lemma, grammarPart)
    local entries = ns.Lookup(word) or {}
    for _, e in ipairs(entries) do
        if e.l == lemma and (not grammarPart or e.g:find(grammarPart, 1, true)) then
            return
        end
    end
    failed = failed + 1
    print(("FAIL %s: expected %s %s"):format(word, lemma, grammarPart or ""))
    Show(word)
end
expect("волков", "волк", "genitive / accusative plural")
expect("стали", "сталь")
expect("стали", "стать", "past")
expect("принеси", "принести", "imperative singular")
expect("Штормграда", "Штормград", "genitive singular")
expect("ещё", "ещё")
expect("лесу", "лес")
expect("убей", "убить", "imperative")
expect("найдётся", "найтись")
expect("кобольдов-вредителей", "вредитель", "genitive / accusative plural") -- by parts
print(failed == 0 and "lookup checks passed" or (failed .. " lookup checks failed"))
os.exit(failed == 0 and 0 or 1)
