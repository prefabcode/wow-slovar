-- Dict.lua — word as it appears in the text -> dictionary entries (data: Data/*.lua, decoding: Lookup.lua).
local _, ns = ...

-- Returns entries ({ l = lemma, p = label, g = grammar, e = { glosses } } list) and whether they come from the
-- word's parts. Hyphenated words that aren't in the dictionary as a whole (кобольдов-вредителей) are looked up
-- part by part, showing the best match for each part.
function ns.Lookup(word)
    local key = ns.Normalize(word)
    local entries = ns.LookupKey(key)
    if entries or not key:find("-", 1, true) then
        return entries, false
    end
    local parts, shown = {}, {}
    for part in word:gmatch("[^-]+") do
        shown[#shown + 1] = part
    end
    local i = 0
    for part in key:gmatch("[^-]+") do
        i = i + 1
        local found = ns.LookupKey(part)
        if found then
            found[1].part = shown[i]
            parts[#parts + 1] = found[1]
        end
    end
    if #parts > 0 then
        return parts, true
    end
    return nil, false
end
