"""Lavori reali con test nascosti (stile uso quotidiano: bugfix, spec ambigue, classi con stato).
Ogni lavoro: prompt, test (lista di asserzioni indipendenti -> credito parziale), soluzione di riferimento (controllo positivo).
Il modello vede solo il prompt. I test misurano casi limite che un modello debole salta."""

TASKS = []


def add(name, prompt, tests, ref):
    TASKS.append({'name': name, 'prompt': prompt, 'tests': tests, 'ref': ref})


add('fattura_bug', '''Fix the bugs in this Python function and return the complete corrected function (code only).
Spec: items is a list of (name, unit_price_cents:int, qty:int). discount_pct (0-100) applies to the subtotal. Tax (tax_pct) applies AFTER the discount.
All money is integer cents; round half up at the very end only (a single rounding of the final total). Return the total in cents. Negative qty or price must raise ValueError.

def invoice_total(items, discount_pct=0, tax_pct=0):
    total = 0
    for name, price, qty in items:
        total += round(price * qty * (1 + tax_pct / 100))
    total = total - total * discount_pct // 100
    return total
''', [
    "invoice_total([('a',1000,2)],0,0)==2000",
    "invoice_total([('a',1000,2)],10,0)==1800",
    "invoice_total([('a',1000,2)],10,20)==2160",
    "invoice_total([('a',333,3)],0,10)==1099",
    "invoice_total([('a',1,1),('b',1,1)],50,0)==1",
    "invoice_total([('a',5,1)],50,0)==3",
    "invoice_total([],10,10)==0",
    "raises(lambda: invoice_total([('a',-1,1)]))",
    "raises(lambda: invoice_total([('a',1,-1)]))",
], '''
def invoice_total(items, discount_pct=0, tax_pct=0):
    from fractions import Fraction
    sub = Fraction(0)
    for n, p, q in items:
        if p < 0 or q < 0:
            raise ValueError
        sub += p * q
    t = sub * (100 - Fraction(discount_pct)) / 100 * (100 + Fraction(tax_pct)) / 100
    return int((t * 2 + 1) // 2)
''')

add('durata', '''Write a Python function parse_duration(s) -> int returning the total number of seconds.
Accepted: units d, h, m, s with integer values, in any order but each unit at most once, optional spaces between parts, e.g. "1h30m", "2d 3h", "45s", "90m". Case-insensitive.
Invalid input (empty string, unknown unit, repeated unit, missing number, number without unit, negative, decimals) must raise ValueError. Return only code.''', [
    "parse_duration('1h30m')==5400", "parse_duration('2d 3h')==183600", "parse_duration('45s')==45", "parse_duration('90M')==5400",
    "parse_duration(' 1h 1s ')==3601", "parse_duration('1s1h')==3601",
    "raises(lambda: parse_duration(''))", "raises(lambda: parse_duration('5'))", "raises(lambda: parse_duration('1h1h'))",
    "raises(lambda: parse_duration('1.5h'))", "raises(lambda: parse_duration('h'))", "raises(lambda: parse_duration('-1h'))", "raises(lambda: parse_duration('3w'))",
], '''
import re
def parse_duration(s):
    s = s.strip()
    if not s:
        raise ValueError
    parts = re.findall(r'(\\d+)\\s*([dhmsDHMS])', s)
    if re.sub(r'(\\d+)\\s*([dhmsDHMS])|\\s', '', s):
        raise ValueError
    us = [u.lower() for _, u in parts]
    if not parts or len(set(us)) != len(us):
        raise ValueError
    k = {'d': 86400, 'h': 3600, 'm': 60, 's': 1}
    return sum(int(n) * k[u.lower()] for n, u in parts)
''')

add('secchio', '''Write a Python class TokenBucket(capacity, refill_per_sec, now=0.0) with method allow(n=1, now) -> bool (time is passed in as `now` seconds, a float, never read from the clock).
It starts full. Tokens refill continuously at refill_per_sec up to capacity. allow consumes n tokens and returns True only if at least n are available, otherwise returns False and consumes nothing.
If now goes backwards, do not refill (never negative elapsed). n<=0 raises ValueError. n larger than capacity always returns False. Return only code.''', [
    "(lambda b: [b.allow(1,0.0) for _ in range(5)])(TokenBucket(5,1.0))==[True]*5",
    "(lambda b: [b.allow(1,0.0) for _ in range(6)])(TokenBucket(5,1.0))[-1] is False",
    "(lambda b: (b.allow(5,0.0), b.allow(1,0.5), b.allow(1,1.0)))(TokenBucket(5,1.0))==(True,False,True)",
    "(lambda b: (b.allow(5,0.0), b.allow(5,100.0), b.allow(1,100.0)))(TokenBucket(5,1.0))==(True,True,False)",
    "(lambda b: (b.allow(3,0.0), b.allow(2,10.0), b.allow(1,10.0)))(TokenBucket(3,0.1))==(True,False,True)",
    "(lambda b: (b.allow(4,10.0), b.allow(1,5.0)))(TokenBucket(5,0.0,now=10.0))==(True,True)",
    "(lambda b: b.allow(6,0.0))(TokenBucket(5,1.0)) is False",
    "raises(lambda: TokenBucket(5,1.0).allow(0,0.0))",
    "(lambda b: (b.allow(2,0.0), b.allow(2,0.0), b.allow(2,0.0)))(TokenBucket(5,1.0))==(True,True,False)",
], '''
class TokenBucket:
    def __init__(self, capacity, refill_per_sec, now=0.0):
        self.c = capacity; self.r = refill_per_sec; self.t = now; self.tok = float(capacity)
    def allow(self, n=1, now=None):
        if n <= 0:
            raise ValueError
        if now is not None and now > self.t:
            self.tok = min(self.c, self.tok + (now - self.t) * self.r); self.t = now
        if n > self.c or self.tok + 1e-9 < n:
            return False
        self.tok -= n
        return True
''')

add('lru_ttl', '''Write a Python class TTLCache(capacity, ttl) with get(key, now) -> value or None, put(key, value, now), and __len__ counting only live entries given the last `now` seen.
Entries expire when now - inserted_at >= ttl (the put time is refreshed on overwrite). When over capacity, first drop expired entries, then evict the least recently used (a get of a live key counts as use). time is passed explicitly as `now`. Return only code.''', [
    "(lambda c: (c.put('a',1,0), c.get('a',5)))(TTLCache(2,10))[1]==1",
    "(lambda c: (c.put('a',1,0), c.get('a',10)))(TTLCache(2,10))[1] is None",
    "(lambda c: (c.put('a',1,0), c.put('b',2,1), c.get('a',2), c.put('c',3,3), c.get('a',3), c.get('b',3), c.get('c',3)))(TTLCache(2,100))[4:]==(1,None,3)",
    "(lambda c: (c.put('a',1,0), c.put('a',2,9), c.get('a',15)))(TTLCache(2,10))[2]==2",
    "(lambda c: (c.put('a',1,0), c.put('b',2,5), c.put('c',3,11), c.get('b',11), c.get('a',11), c.get('c',11)))(TTLCache(2,10))[3:]==(2,None,3)",
    "(lambda c: (c.put('a',1,0), c.put('b',2,0), c.get('a',20), len(c)))(TTLCache(5,10))[3]==0",
    "(lambda c: (c.put('a',1,0), c.put('b',2,1), len(c)))(TTLCache(5,10))[2]==2",
    "(lambda c: (c.put('a',1,0), c.put('b',2,1), c.put('c',3,2), c.get('a',2)))(TTLCache(2,100))[3] is None",
], '''
class TTLCache:
    def __init__(self, capacity, ttl):
        self.cap = capacity; self.ttl = ttl; self.d = {}; self.now = 0
    def _purge(self, now):
        self.now = max(self.now, now)
        for k in [k for k, (v, t) in self.d.items() if now - t >= self.ttl]:
            del self.d[k]
    def get(self, key, now):
        self._purge(now)
        if key not in self.d:
            return None
        v, t = self.d.pop(key); self.d[key] = (v, t)
        return v
    def put(self, key, value, now):
        self._purge(now)
        self.d.pop(key, None); self.d[key] = (value, now)
        while len(self.d) > self.cap:
            self.d.pop(next(iter(self.d)))
    def __len__(self):
        self._purge(self.now)
        return len(self.d)
''')

add('csv', '''Write a Python function parse_csv(text) -> list[list[str]] WITHOUT using the csv module.
Rules: comma separated; fields may be quoted with double quotes; inside quotes commas and newlines are literal and "" is an escaped quote; records end at newline (\\n or \\r\\n) outside quotes; a final trailing newline does not create an empty record; empty input returns []; an unterminated quote raises ValueError. Return only code.''', [
    "parse_csv('a,b,c')==[['a','b','c']]", "parse_csv('a,b\\nc,d\\n')==[['a','b'],['c','d']]", "parse_csv('a,,c')==[['a','','c']]",
    "parse_csv('\"a,b\",c')==[['a,b','c']]", "parse_csv('\"he said \"\"hi\"\"\",x')==[['he said \"hi\"','x']]",
    "parse_csv('\"line1\\nline2\",z')==[['line1\\nline2','z']]", "parse_csv('a,b\\r\\nc,d')==[['a','b'],['c','d']]",
    "parse_csv('')==[]", "parse_csv('a,\\n')==[['a','']]", "raises(lambda: parse_csv('\"abc'))",
], '''
def parse_csv(text):
    rows, row, f, i, q, n = [], [], '', 0, False, len(text)
    started = False
    while i < n:
        ch = text[i]
        if q:
            if ch == '"':
                if i + 1 < n and text[i + 1] == '"':
                    f += '"'; i += 1
                else:
                    q = False
            else:
                f += ch
        else:
            if ch == '"' and f == '':
                q = True; started = True
            elif ch == ',':
                row.append(f); f = ''; started = True
            elif ch == '\\r' and i + 1 < n and text[i + 1] == '\\n':
                pass
            elif ch == '\\n':
                row.append(f); rows.append(row); row, f, started = [], '', False
            else:
                f += ch; started = True
        i += 1
    if q:
        raise ValueError
    if started or f or row:
        row.append(f); rows.append(row)
    return rows
''')

add('semver', '''Write a Python function satisfies(version, rng) -> bool for semantic versions "MAJOR.MINOR.PATCH" (integers, no prerelease tags).
rng is one or more space-separated comparators ALL of which must hold: ">=1.2.3", ">1.0.0", "<=2.0.0", "<3.0.0", "=1.2.3" or plain "1.2.3", "^1.2.3" (>=1.2.3 and <2.0.0; for 0.x.y: ^0.2.3 means >=0.2.3 <0.3.0; ^0.0.3 means exactly 0.0.3), "~1.2.3" (>=1.2.3 and <1.3.0). Compare numerically (1.10.0 > 1.9.0). Malformed version or comparator raises ValueError. Return only code.''', [
    "satisfies('1.2.3','>=1.2.3')", "not satisfies('1.2.2','>=1.2.3')", "satisfies('1.10.0','>1.9.0')", "satisfies('1.5.0','^1.2.3')",
    "not satisfies('2.0.0','^1.2.3')", "satisfies('0.2.9','^0.2.3')", "not satisfies('0.3.0','^0.2.3')", "satisfies('0.0.3','^0.0.3')",
    "not satisfies('0.0.4','^0.0.3')", "satisfies('1.2.9','~1.2.3')", "not satisfies('1.3.0','~1.2.3')", "satisfies('1.5.0','>=1.0.0 <2.0.0')",
    "not satisfies('2.5.0','>=1.0.0 <2.0.0')", "satisfies('1.2.3','1.2.3')", "satisfies('1.2.3','=1.2.3')", "raises(lambda: satisfies('1.2','>=1.0.0'))",
    "raises(lambda: satisfies('1.2.3','>>1.0.0'))",
], '''
import re
def _v(s):
    m = re.fullmatch(r'(\\d+)\\.(\\d+)\\.(\\d+)', s)
    if not m:
        raise ValueError
    return tuple(int(x) for x in m.groups())
def satisfies(version, rng):
    v = _v(version)
    for c in rng.split():
        m = re.fullmatch(r'(>=|<=|>|<|=|\\^|~)?(\\d+\\.\\d+\\.\\d+)', c)
        if not m:
            raise ValueError
        op, t = m.group(1) or '=', _v(m.group(2))
        if op == '>=': ok = v >= t
        elif op == '<=': ok = v <= t
        elif op == '>': ok = v > t
        elif op == '<': ok = v < t
        elif op == '=': ok = v == t
        elif op == '~': ok = t <= v < (t[0], t[1] + 1, 0)
        else:
            if t[0] > 0: hi = (t[0] + 1, 0, 0)
            elif t[1] > 0: hi = (0, t[1] + 1, 0)
            else: hi = (0, 0, t[2] + 1)
            ok = t <= v < hi
        if not ok:
            return False
    return True
''')

add('topo', '''Write a Python function topo_order(n, edges) -> list[int] for a directed graph with nodes 0..n-1 and edges (u, v) meaning u must come before v.
Return the lexicographically smallest valid topological order (always pick the smallest available node). If there is a cycle raise ValueError. Duplicate edges are allowed. A self-loop is a cycle. Edges with a node outside 0..n-1 raise ValueError. Return only code.''', [
    "topo_order(3,[])==[0,1,2]", "topo_order(4,[(3,0),(1,2)])==[1,2,3,0]", "topo_order(4,[(0,1),(0,1),(1,2)])==[0,1,2,3]",
    "topo_order(5,[(4,0),(4,1),(0,2),(1,2),(2,3)])==[4,0,1,2,3]", "topo_order(0,[])==[]", "topo_order(3,[(2,1),(1,0)])==[2,1,0]",
    "raises(lambda: topo_order(2,[(0,1),(1,0)]))", "raises(lambda: topo_order(2,[(1,1)]))", "raises(lambda: topo_order(2,[(0,5)]))",
    "topo_order(6,[(5,2),(5,0),(4,0),(4,1),(2,3),(3,1)])==[4,5,0,2,3,1]",
], '''
import heapq
def topo_order(n, edges):
    adj = [[] for _ in range(n)]; indeg = [0] * n
    for u, v in edges:
        if not (0 <= u < n and 0 <= v < n):
            raise ValueError
        adj[u].append(v); indeg[v] += 1
    h = [i for i in range(n) if indeg[i] == 0]; heapq.heapify(h); out = []
    while h:
        u = heapq.heappop(h); out.append(u)
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(h, v)
    if len(out) != n:
        raise ValueError
    return out
''')

add('espressione', '''Write a Python function calc(expr) -> float or int evaluating an arithmetic expression string WITHOUT eval/exec/ast.literal_eval.
Support: integers and decimals, + - * / ** (right associative, binds tighter than unary minus on its left: -2**2 == -4), parentheses, unary minus/plus, spaces. Division by zero raises ZeroDivisionError. Any invalid syntax (unbalanced parentheses, two operators in a row except unary, empty, letters) raises ValueError. Return only code.''', [
    "calc('1+2*3')==7", "calc('(1+2)*3')==9", "calc('2**3**2')==512", "calc('-2**2')==-4", "calc('2*-3')==-6", "calc('10/4')==2.5",
    "calc(' 7 - 2 - 1 ')==4", "calc('-(1+2)')==-3", "calc('1.5*2')==3", "calc('2**-1')==0.5", "calc('+3')==3",
    "raises(lambda: calc('1/0'), ZeroDivisionError)", "raises(lambda: calc('(1+2'))", "raises(lambda: calc('1++'))", "raises(lambda: calc(''))",
    "raises(lambda: calc('a+1'))", "raises(lambda: calc('1 2'))",
], '''
import re
def calc(expr):
    toks = re.findall(r'\\d+\\.?\\d*|\\.\\d+|\\*\\*|[-+*/()]|\\S', expr)
    for t in toks:
        if not re.fullmatch(r'\\d+\\.?\\d*|\\.\\d+|\\*\\*|[-+*/()]', t):
            raise ValueError
    if not toks:
        raise ValueError
    pos = [0]
    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None
    def eat():
        pos[0] += 1; return toks[pos[0] - 1]
    def expr_():
        v = term()
        while peek() in ('+', '-'):
            o = eat(); r = term(); v = v + r if o == '+' else v - r
        return v
    def term():
        v = unary()
        while peek() in ('*', '/'):
            o = eat(); r = unary(); v = v * r if o == '*' else v / r
        return v
    def unary():
        if peek() == '-':
            eat(); return -unary()
        if peek() == '+':
            eat(); return unary()
        return power()
    def power():
        b = atom()
        if peek() == '**':
            eat(); return b ** unary()
        return b
    def atom():
        t = peek()
        if t is None:
            raise ValueError
        if t == '(':
            eat(); v = expr_()
            if peek() != ')':
                raise ValueError
            eat(); return v
        if re.fullmatch(r'\\d+\\.?\\d*|\\.\\d+', t):
            eat(); return float(t) if '.' in t else int(t)
        raise ValueError
    v = expr_()
    if pos[0] != len(toks):
        raise ValueError
    return v
''')

HEAD = '''
def raises(f, exc=ValueError):
    try:
        f()
    except exc:
        return True
    except Exception:
        return False
    return False
'''


def grade_src(code, task):
    """Sorgente python che stampa 'N/M' (asserzioni passate / totali)."""
    body = ['import sys', HEAD, code, 'ok = 0', 'T = %r' % (task['tests'],)]
    body.append('for t in T:\n    try:\n        ok += 1 if eval(t) else 0\n    except Exception:\n        pass\nprint("SCORE", ok, len(T))')
    return '\n'.join(body)
