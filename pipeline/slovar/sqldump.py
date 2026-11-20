"""Minimal reader for MySQL dump files (INSERT INTO ... VALUES (...),(...);) as shipped by AzerothCore."""

_ESCAPES = {"n": "\n", "r": "\r", "t": "\t", "0": "\0", "Z": "\x1a"}


def rows(path):
    """Yield every row of every INSERT statement as a list of str|None."""
    data = open(path, encoding="utf-8").read()
    i, n = 0, len(data)
    while True:
        i = data.find("INSERT INTO", i)
        if i < 0:
            return
        i = data.find("VALUES", i) + len("VALUES")
        while i < n:
            while data[i] in " \n\r\t,":
                i += 1
            if data[i] == ";":
                break
            assert data[i] == "(", f"unexpected {data[i:i + 40]!r} in {path}"
            i += 1
            row = []
            while True:
                if data[i] == "'":
                    i += 1
                    buf = []
                    while True:
                        c = data[i]
                        if c == "\\":
                            nxt = data[i + 1]
                            buf.append(_ESCAPES.get(nxt, nxt))
                            i += 2
                        elif c == "'":
                            if data[i + 1] == "'":
                                buf.append("'")
                                i += 2
                            else:
                                i += 1
                                break
                        else:
                            buf.append(c)
                            i += 1
                    row.append("".join(buf))
                else:
                    j = i
                    while data[j] not in ",)":
                        j += 1
                    tok = data[i:j].strip()
                    row.append(None if tok == "NULL" else tok)
                    i = j
                if data[i] == ",":
                    i += 1
                    continue
                i += 1  # ")"
                break
            yield row
