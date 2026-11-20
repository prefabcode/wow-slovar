-- Text.lua — UTF-8 helpers for Russian text (pure functions, no WoW API; tested offline by tests/lua/test_text.lua).
--
-- WoW runs Lua 5.1: strings are byte arrays, string.lower ignores Cyrillic, and patterns can't repeat a
-- multi-byte group. In UTF-8 every Cyrillic letter is 2 bytes: a lead byte 208 or 209 (0xD0/0xD1) followed by
-- a continuation byte 128..191. So we walk bytes by hand instead of using patterns for words.

-- Every file listed in the .toc receives two arguments via `...`: the addon's folder name and a private table
-- shared by all files of this addon (think "module scope"). We hang our functions on that table, not on _G.
local _, ns = ...

local byte, char, sub, find, gsub, lower, concat = string.byte, string.char, string.sub, string.find, string.gsub,
    string.lower, table.concat

-- Hyperlink payload prefix. "addon:" is the link type modern clients reserve for addons: Blizzard's SetItemRef
-- ignores it instead of erroring with "unknown link type" if something ever routes a click on it.
local LINK_PREFIX = "addon:slovar:"
ns.LINK_PREFIX = LINK_PREFIX

-- Lowercase map: uppercase 2-byte letter -> lowercase 2-byte letter, plus ё -> е (dictionary keys use е).
local LOWER = {}
for c = 144, 159 do LOWER[char(208, c)] = char(208, c + 32) end -- А..П (D0 90..9F) -> а..п (D0 B0..BF)
for c = 160, 175 do LOWER[char(208, c)] = char(209, c - 32) end -- Р..Я (D0 A0..AF) -> р..я (D1 80..8F)
LOWER["\208\129"] = "\208\181" -- Ё -> е
LOWER["\209\145"] = "\208\181" -- ё -> е

-- Dictionary key for a word: lowercase, ё -> е, no stress marks.
function ns.Normalize(word)
    word = gsub(word, "\204[\128\129]", "") -- combining grave/acute accents U+0300/U+0301 (stress marks)
    word = gsub(word, "[\208\209][\128-\191]", LOWER) -- letters missing from the map stay as they are
    return lower(word) -- ASCII only; leaves bytes >= 128 alone
end

local function IsLetterAt(s, i)
    local b = byte(s, i)
    if b == 208 or b == 209 then
        local c = byte(s, i + 1)
        return c ~= nil and c >= 128 and c <= 191
    end
    return false
end

-- WoW escape sequences start with "|". Returns the index of the last byte of the sequence starting at s[i].
-- Their contents (texture paths, link data, colour codes) must never be split into words.
local CLOSERS = { T = "|t", A = "|a", K = "|k" }
local function EscapeEnd(s, i)
    local code = sub(s, i + 1, i + 1)
    if code == "c" then
        if sub(s, i + 2, i + 2) == "n" then -- |cnCOLOR_NAME:   (named colour, modern clients)
            local e = find(s, ":", i + 3, true)
            return e or #s
        end
        return i + 9 -- |cAARRGGBB
    elseif code == "H" then -- |Hdata|htext|h   (keep the whole link, including its text)
        local _, dataEnd = find(s, "|h", i + 2, true)
        if dataEnd then
            local _, textEnd = find(s, "|h", dataEnd + 1, true)
            if textEnd then
                return textEnd
            end
        end
        return #s
    end
    local closer = CLOSERS[code]
    if closer then -- |T...|t texture, |A...|a atlas, |K...|k Battle.net name
        local _, e = find(s, closer, i + 2, true)
        return e or #s
    end
    return i + 1 -- ||, |r, |n and anything unknown: two bytes
end

-- Wrap every Cyrillic word in an invisible hyperlink: |Haddon:slovar:слово|hслово|h.
-- No colour code, so it renders exactly like the surrounding text. Everything else is copied byte for byte.
function ns.Linkify(text)
    if type(text) ~= "string" or text == "" then
        return text
    end
    if find(text, "|H" .. LINK_PREFIX, 1, true) then
        return text -- already done (makes Linkify idempotent)
    end
    local out, n = {}, 0
    local i, len, plainStart = 1, #text, 1
    while i <= len do
        local b = byte(text, i)
        if b == 124 then -- "|": skip the escape sequence; it stays part of the plain run
            i = EscapeEnd(text, i) + 1
        elseif IsLetterAt(text, i) then
            if plainStart < i then
                n = n + 1
                out[n] = sub(text, plainStart, i - 1)
            end
            local j = i
            while true do
                if IsLetterAt(text, j) then
                    j = j + 2
                elseif byte(text, j) == 45 and IsLetterAt(text, j + 1) then -- "-" between letters: кто-нибудь
                    j = j + 1
                else
                    break
                end
            end
            local word = sub(text, i, j - 1)
            n = n + 1
            out[n] = "|H" .. LINK_PREFIX .. word .. "|h" .. word .. "|h"
            i, plainStart = j, j
        else
            i = i + 1
        end
    end
    if n == 0 then
        return text
    end
    if plainStart <= len then
        n = n + 1
        out[n] = sub(text, plainStart)
    end
    return concat(out)
end

-- Remove colour codes (|cAARRGGBB, |cnNAME:, |r). They don't affect layout, and our invisible copy of the text must
-- not contain anything that would render visibly.
function ns.StripColors(text)
    text = gsub(text, "|c%x%x%x%x%x%x%x%x", "")
    text = gsub(text, "|cn[%w_]+:", "")
    return (gsub(text, "|r", ""))
end

-- Inverse of Linkify: the plain text back (for logging context sentences later, and for tests).
function ns.StripLinks(text)
    return (gsub(text, "|H" .. LINK_PREFIX .. "[^|]*|h(.-)|h", "%1"))
end
