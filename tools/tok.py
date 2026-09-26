"""Applesoft BASIC tokenizer: plain text -> tokenized program image at $0801."""
TOKENS = """END FOR NEXT DATA INPUT DEL DIM READ GR TEXT PR# IN# CALL PLOT HLIN VLIN
HGR2 HGR HCOLOR= HPLOT DRAW XDRAW HTAB HOME ROT= SCALE= SHLOAD TRACE NOTRACE
NORMAL INVERSE FLASH COLOR= POP VTAB HIMEM: LOMEM: ONERR RESUME RECALL STORE
SPEED= LET GOTO RUN IF RESTORE & GOSUB RETURN REM STOP ON WAIT LOAD SAVE DEF
POKE PRINT CONT LIST CLEAR GET NEW TAB( TO FN SPC( THEN AT NOT STEP + - * / ^
AND OR > = < SGN INT ABS USR FRE SCRN( PDL POS SQR RND LOG EXP COS SIN TAN ATN
PEEK LEN STR$ VAL ASC CHR$ LEFT$ RIGHT$ MID$""".split()
assert len(TOKENS) == 107, len(TOKENS)           # $80..$EA
TOKVAL = {k: 0x80 + i for i, k in enumerate(TOKENS)}
REM, DATA = TOKVAL['REM'], TOKVAL['DATA']
BYLEN = sorted(TOKENS, key=len, reverse=True)    # longest first: ATN beats AT


def tok_line(text):
    out, i, n = bytearray(), 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':                                  # string literal: verbatim
            out.append(ord('"')); i += 1
            while i < n:
                out.append(ord(text[i]))
                if text[i] == '"':
                    i += 1; break
                i += 1
            continue
        if c == ' ':                                  # Applesoft strips blanks
            i += 1; continue
        up = text[i:].upper()
        for kw in BYLEN:
            if up.startswith(kw):
                t = TOKVAL[kw]; out.append(t); i += len(kw)
                if t == REM:                          # rest of line verbatim
                    out += text[i:].encode('ascii'); i = n
                elif t == DATA:                       # verbatim to end of stmt
                    q = False
                    while i < n:
                        if text[i] == '"': q = not q
                        if text[i] == ':' and not q: break
                        out.append(ord(text[i])); i += 1
                break
        else:
            out.append(ord(c.upper())); i += 1
    return bytes(out)


def tokenize(src, base=0x0801):
    lines = []
    for raw in src.splitlines():
        s = raw.strip()
        if not s:
            continue
        j = 0
        while j < len(s) and s[j].isdigit():
            j += 1
        if j == 0:
            raise ValueError('no line number: %r' % raw)
        lines.append((int(s[:j]), tok_line(s[j:])))
    nums = [n for n, _ in lines]
    if nums != sorted(nums):
        raise ValueError('line numbers out of order')
    out, addr = bytearray(), base
    for num, body in lines:
        addr += 4 + len(body) + 1
        out += addr.to_bytes(2, 'little') + num.to_bytes(2, 'little') + body + b'\0'
    out += b'\0\0'
    return bytes(out)


def check_variables(src):
    """Variable names Applesoft would tokenise as keywords (e.g. TO, AT, ON)."""
    import re
    bad = set()
    for line in src.splitlines():
        m = re.match(r'\s*\d+\s*(.*)', line)
        if not m:
            continue
        body = re.sub(r'"[^"]*"', '""', m.group(1))
        if 'REM' in body:
            body = body[:body.index('REM')]
        names = set(re.findall(r'(?:^|:)\s*([A-Za-z][A-Za-z0-9]*\$?)\s*=', body))
        names |= set(re.findall(r'FOR\s+([A-Za-z][A-Za-z0-9]*)\s*=', body))
        names |= set(re.findall(r'DIM\s+([A-Za-z][A-Za-z0-9]*)\s*\(', body))
        for n in names:
            if any(b >= 0x80 for b in tok_line(n)):
                bad.add(n)
    return sorted(bad)
