-- Lookup.lua — reads the generated dictionary (Data/Lemmas.lua, Data/Forms.lua). Pure Lua, no WoW API.
--
-- Data layout (written by pipeline/build.py):
--   ns.Data.lemmas[id] = "display\tlabel\tgloss1\tgloss2\tgloss3"
--   ns.Data.forms[first letter] = "\nform\tid:tagset,tagset;id:tagset\n..."   one text block per first letter
-- A tagset is a few one-char grammar codes, e.g. "Gp" = genitive plural (see pipeline/slovar/tags.py).
local _, ns = ...

local find, sub, gmatch, gsub, byte, concat = string.find, string.sub, string.gmatch, string.gsub, string.byte,
    table.concat

local CASE = {
    N = "nominative", G = "genitive", D = "dative", A = "accusative", I = "instrumental",
    P = "prepositional", L = "locative", V = "vocative", R = "partitive",
}
local PERSON = { ["1"] = "1st person", ["2"] = "2nd person", ["3"] = "3rd person" }
local TENSE = { r = "present", t = "past", u = "future" }
local GENDERS = { "m", "f", "n" }
local GENDER = { m = "masculine", f = "feminine", n = "neuter" }

-- Everything except the case, e.g. "pm" -> "plural", "1su" -> "future, 1st person singular".
local function Describe(rest)
    local has = {}
    for c in gmatch(rest, ".") do
        has[c] = true
    end
    local number = has.s and "singular" or has.p and "plural" or nil
    local genders = {}
    for _, g in ipairs(GENDERS) do
        if has[g] then
            genders[#genders + 1] = GENDER[g]
        end
    end
    local gender = #genders > 0 and concat(genders, "/") or nil
    local tense = has.r and TENSE.r or has.t and TENSE.t or has.u and TENSE.u or nil
    local person = has["1"] and PERSON["1"] or has["2"] and PERSON["2"] or has["3"] and PERSON["3"] or nil
    local out = {}
    local function add(s)
        if s then
            out[#out + 1] = s
        end
    end
    if has.i then
        add("infinitive")
    elseif has.o then
        add("imperative")
        add(number)
    elseif has.c or has.w then -- participle / gerund (verb table entries)
        add(has.h and "short")
        add(tense)
        add(has.a and "active" or has.e and "passive" or nil)
        add(has.c and "participle" or "gerund")
        if gender or number then
            out[#out] = out[#out] .. ","
            add(gender)
            add(number)
        end
    elseif tense then -- finite verb: "future, 1st person singular" / "past, feminine singular"
        add(tense .. ((person or number or gender) and "," or ""))
        add(person)
        add(gender)
        add(number)
    else -- nouns, adjectives, pronouns
        add(has.h and "short form" .. ((gender or number) and "," or "") or nil)
        add(gender)
        add(number or (gender and "singular") or nil)
        add(has.k and "comparative" or has.x and "superlative" or nil)
        add(has.y and "(animate)" or has.z and "(inanimate)" or nil)
    end
    return concat(out, " ")
end

-- "Gp,Ap" -> "genitive / accusative plural"
function ns.RenderGrammar(tagsets)
    local order, cases = {}, {}
    for ts in gmatch(tagsets, "[^,]+") do
        local c = sub(ts, 1, 1)
        local rest = ts
        if CASE[c] then
            rest = sub(ts, 2)
        else
            c = nil
        end
        if not cases[rest] then
            cases[rest] = {}
            order[#order + 1] = rest
        end
        if c then
            table.insert(cases[rest], CASE[c])
        end
    end
    local lines, seen = {}, {}
    for _, rest in ipairs(order) do
        local text = Describe(rest)
        if #cases[rest] > 0 then
            text = concat(cases[rest], " / ") .. (text ~= "" and " " .. text or "")
        end
        if text ~= "" and not seen[text] then
            seen[text] = true
            lines[#lines + 1] = text
        end
    end
    return concat(lines, "; ")
end

local function Split(record)
    local fields = {}
    for field in gmatch(record, "[^\t]+") do
        fields[#fields + 1] = field
    end
    return fields
end

-- Normalized form (see ns.Normalize) -> list of { l = lemma, p = label, g = grammar, e = { glosses } } or nil.
function ns.LookupKey(key)
    local data = ns.Data
    local block = data and data.forms[sub(key, 1, 2)] -- first Cyrillic letter = first 2 bytes
    if not block then
        return nil
    end
    local _, e = find(block, "\n" .. key .. "\t", 1, true)
    if not e then
        return nil
    end
    local value = sub(block, e + 1, find(block, "\n", e + 1, true) - 1)
    local result = {}
    for id, tagsets in gmatch(value, "(%d+):([^;]*)") do
        local f = Split(data.lemmas[tonumber(id)])
        result[#result + 1] = { l = f[1], p = f[2], g = ns.RenderGrammar(tagsets), e = { f[3], f[4], f[5] } }
    end
    return result
end
