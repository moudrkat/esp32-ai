"""The language the model writes and the chip runs: a small subset of Python for a 128x64 mono OLED.

    clear()                     blank the screen
    text(x, y, s)               s at column x, row y (6x8 pixel characters: 21 per line, 8 lines)
    pixel(x, y)                 one dot
    line(x0, y0, x1, y1)        a line
    rect(x, y, w, h)            an outline
    fill(x, y, w, h)            a filled rectangle
    circle(x, y, r)             a circle outline
    wait(ms)                    show what is drawn and pause; the end of the program shows it too

Plus whole numbers and strings, variables, + - * // %, comparisons, and/or/not, str(), abs(), min(), max(),
`for i in range(...)`, `while`, `if/elif/else`. Nothing else parses: no imports, no attributes, no functions of
its own, no lists. Coordinates outside the screen are clipped, and the run stops after MAX_STEPS steps or
MAX_WAIT_MS of waiting, so whatever the model writes, the chip stays in charge.

This module is the reference interpreter: it checks a program, runs it and records the frames, which is how the
corpus is verified and how the model is scored (same pictures = same program, whatever the spelling).
"""
import ast

W, H = 128, 64
CW, CH = 6, 8
MAX_STEPS = 20_000
MAX_WAIT_MS = 30_000
DRAW = {"clear": 0, "text": 3, "pixel": 2, "line": 4, "rect": 4, "fill": 4, "circle": 3, "wait": 1}
PURE = {"str": str, "abs": abs, "min": min, "max": max}


class LangError(Exception):
    pass


class Screen:
    def __init__(self):
        self.px = bytearray(W * H)
        self.frames = []          # (ms since start, bytes) at every wait and at the end
        self.t = 0
        self.texts = []           # (x, y, s) drawn since the last clear, for checks that read the words

    def set(self, x, y):
        if 0 <= x < W and 0 <= y < H:
            self.px[y * W + x] = 1

    def clear(self):
        self.px = bytearray(W * H)
        self.texts = []

    def text(self, x, y, s):
        s = str(s)
        self.texts.append((x, y, s))
        for i, ch in enumerate(s):
            if ch != " ":
                for dx in range(CW - 1):          # a block per character: the interpreter does not
                    for dy in range(CH - 1):      # need glyphs to compare two programs' pictures
                        if (dx + dy) % 2 == 0:
                            self.set(x + i * CW + dx, y + dy)

    def pixel(self, x, y):
        self.set(x, y)

    def line(self, x0, y0, x1, y1):
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        for _ in range(W + H + 2):
            self.set(x0, y0)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy; x0 += sx
            if e2 <= dx:
                err += dx; y0 += sy

    def rect(self, x, y, w, h):
        if w <= 0 or h <= 0:
            return
        self.line(x, y, x + w - 1, y); self.line(x, y + h - 1, x + w - 1, y + h - 1)
        self.line(x, y, x, y + h - 1); self.line(x + w - 1, y, x + w - 1, y + h - 1)

    def fill(self, x, y, w, h):
        for yy in range(max(0, y), min(H, y + h)):
            for xx in range(max(0, x), min(W, x + w)):
                self.px[yy * W + xx] = 1

    def circle(self, cx, cy, r):
        x, y, err = r, 0, 1 - r
        while x >= y:
            for a, b in ((x, y), (y, x), (-y, x), (-x, y), (-x, -y), (-y, -x), (y, -x), (x, -y)):
                self.set(cx + a, cy + b)
            y += 1
            if err < 0:
                err += 2 * y + 1
            else:
                x -= 1; err += 2 * (y - x) + 1

    def wait(self, ms):
        self.frames.append((self.t, bytes(self.px)))
        self.t += max(0, int(ms))
        if self.t > MAX_WAIT_MS:
            raise LangError("waits too long")


ALLOWED = (ast.Module, ast.Expr, ast.Assign, ast.AugAssign, ast.For, ast.While, ast.If, ast.Call, ast.Name,
           ast.Constant, ast.BinOp, ast.UnaryOp, ast.Compare, ast.BoolOp, ast.Load, ast.Store, ast.Add, ast.Sub,
           ast.Mult, ast.FloorDiv, ast.Mod, ast.USub, ast.Not, ast.And, ast.Or, ast.Eq, ast.NotEq, ast.Lt,
           ast.LtE, ast.Gt, ast.GtE, ast.Pass, ast.Break, ast.Continue)


def check(src):
    """Parse and refuse anything outside the language. Returns the tree."""
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        raise LangError(f"syntax: {e.msg}")
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED):
            raise LangError(f"not in the language: {type(node).__name__}")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, str)) or \
                isinstance(node, ast.Constant) and isinstance(node.value, bool):
            raise LangError("only whole numbers and strings")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.keywords:
                raise LangError("calls are name(args)")
            f = node.func.id
            if f == "range":
                if not 1 <= len(node.args) <= 3:
                    raise LangError("range takes 1 to 3 numbers")
            elif f in DRAW:
                if len(node.args) != DRAW[f]:
                    raise LangError(f"{f} takes {DRAW[f]} arguments")
            elif f not in PURE:
                raise LangError(f"unknown function {f}")
        if isinstance(node, ast.For):
            if not (isinstance(node.target, ast.Name) and isinstance(node.iter, ast.Call)
                    and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range") or node.orelse:
                raise LangError("for only as: for i in range(...)")
        if isinstance(node, (ast.Assign,)) and not all(isinstance(t, ast.Name) for t in node.targets):
            raise LangError("assign to names only")
    return tree


class _Break(Exception): pass
class _Continue(Exception): pass


class Machine:
    def __init__(self):
        self.screen, self.vars, self.steps = Screen(), {}, 0

    def tick(self):
        self.steps += 1
        if self.steps > MAX_STEPS:
            raise LangError("too many steps")

    def ev(self, n):
        self.tick()
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.Name):
            if n.id not in self.vars:
                raise LangError(f"unknown name {n.id}")
            return self.vars[n.id]
        if isinstance(n, ast.BinOp):
            a, b = self.ev(n.left), self.ev(n.right)
            try:
                if isinstance(n.op, ast.Add): return a + b
                if isinstance(n.op, ast.Sub): return a - b
                if isinstance(n.op, ast.Mult):
                    r = a * b
                    if isinstance(r, str) and len(r) > 200: raise LangError("string too long")
                    return r
                if isinstance(n.op, ast.FloorDiv): return a // b
                if isinstance(n.op, ast.Mod): return a % b
            except (TypeError, ZeroDivisionError) as e:
                raise LangError(str(e))
        if isinstance(n, ast.UnaryOp):
            v = self.ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else (not v)
        if isinstance(n, ast.BoolOp):
            vals = n.values
            if isinstance(n.op, ast.And):
                r = True
                for v in vals:
                    r = self.ev(v)
                    if not r: return r
                return r
            r = False
            for v in vals:
                r = self.ev(v)
                if r: return r
            return r
        if isinstance(n, ast.Compare):
            left = self.ev(n.left)
            for op, right in zip(n.ops, n.comparators):
                r = self.ev(right)
                ok = {ast.Eq: left == r, ast.NotEq: left != r}.get(type(op))
                if ok is None:
                    try:
                        ok = {ast.Lt: left < r, ast.LtE: left <= r, ast.Gt: left > r, ast.GtE: left >= r}[type(op)]
                    except TypeError as e:
                        raise LangError(str(e))
                if not ok: return False
                left = r
            return True
        if isinstance(n, ast.Call):
            f, args = n.func.id, [self.ev(a) for a in n.args]
            if f in PURE:
                try:
                    return PURE[f](*args)
                except (TypeError, ValueError) as e:
                    raise LangError(str(e))
            if f in DRAW:
                if f != "text" and not all(isinstance(a, int) for a in args):
                    raise LangError(f"{f} takes whole numbers")
                if f == "text" and not (isinstance(args[0], int) and isinstance(args[1], int)):
                    raise LangError("text takes x, y and a string")
                getattr(self.screen, f)(*args)
                return None
            raise LangError(f"range only in a for loop")
        raise LangError(f"cannot evaluate {type(n).__name__}")

    def run_block(self, body):
        for s in body:
            self.ex(s)

    def ex(self, s):
        self.tick()
        if isinstance(s, ast.Expr):
            self.ev(s.value)
        elif isinstance(s, ast.Assign):
            v = self.ev(s.value)
            for t in s.targets:
                self.vars[t.id] = v
        elif isinstance(s, ast.AugAssign):
            fake = ast.BinOp(left=ast.Name(id=s.target.id, ctx=ast.Load()), op=s.op, right=s.value)
            self.vars[s.target.id] = self.ev(fake)
        elif isinstance(s, ast.If):
            self.run_block(s.body if self.ev(s.test) else s.orelse)
        elif isinstance(s, ast.For):
            args = [self.ev(a) for a in s.iter.args]
            if not all(isinstance(a, int) for a in args):
                raise LangError("range takes whole numbers")
            for i in range(*args):
                self.vars[s.target.id] = i
                try:
                    self.run_block(s.body)
                except _Break:
                    break
                except _Continue:
                    continue
        elif isinstance(s, ast.While):
            while self.ev(s.test):
                try:
                    self.run_block(s.body)
                except _Break:
                    break
                except _Continue:
                    continue
        elif isinstance(s, ast.Break):
            raise _Break
        elif isinstance(s, ast.Continue):
            raise _Continue
        elif isinstance(s, ast.Pass):
            pass
        else:
            raise LangError(f"cannot run {type(s).__name__}")


def run(src):
    """Check and run a program. Returns the Screen: .frames is [(ms, pixels)], the last one the final picture."""
    tree = check(src)
    m = Machine()
    try:
        m.run_block(tree.body)
    except (_Break, _Continue):
        raise LangError("break outside a loop")
    m.screen.frames.append((m.screen.t, bytes(m.screen.px)))
    return m.screen


def same(a, b):
    """Do two programs draw the same thing? Same frames in the same order, ignoring how long each stays."""
    fa, fb = [f for _, f in a.frames], [f for _, f in b.frames]
    dedup = lambda fs: [f for i, f in enumerate(fs) if i == 0 or f != fs[i - 1]]
    return dedup(fa) == dedup(fb)


def png(screen, path, scale=4, frame=-1):
    """A preview of one frame, white on black like the panel (text drawn as blocks, not glyphs)."""
    from PIL import Image
    px = screen.frames[frame][1]
    img = Image.new("1", (W, H))
    img.putdata([255 if p else 0 for p in px])
    img.resize((W * scale, H * scale), Image.NEAREST).save(path)


def gif(screen, path, scale=3):
    from PIL import Image
    frames, durs = [], []
    for i, (t, px) in enumerate(screen.frames):
        img = Image.new("L", (W, H)); img.putdata([230 if p else 10 for p in px])
        frames.append(img.resize((W * scale, H * scale), Image.NEAREST))
        nxt = screen.frames[i + 1][0] if i + 1 < len(screen.frames) else t + 1500
        durs.append(max(60, nxt - t))
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=durs, loop=0)
