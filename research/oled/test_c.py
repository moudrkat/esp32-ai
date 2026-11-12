"""Run every program through the C interpreter (runtime/oled_lang.h, host build) and through lang.py, and compare:
the same frames, pixel for pixel, or both refuse. Also mutated programs, the kind of mistakes a small model makes
(a dropped colon, a wrong name, an unknown call, a bad indent, a missing argument, a stray character), where only
the verdict has to agree: both run and draw the same, or both refuse.

    gcc -O2 -o /tmp/ol_host runtime/test/oled_lang_host.c && python -m research.oled.test_c /tmp/ol_host
"""
import json
import random
import subprocess
import sys
from collections import Counter

from .lang import LangError, run


def fnv(px):
    h = 1469598103934665603
    for b in px:
        h ^= b
        h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


def py_verdict(src):
    try:
        s = run(src)
    except LangError as e:
        return "ERR", str(e)
    except (RecursionError, MemoryError) as e:
        return "ERR", type(e).__name__
    return "OK", ",".join(fnv(f) for _, f in s.frames)


def mutate(r, src):
    lines = src.splitlines()
    i = r.randrange(len(lines))
    k = r.randrange(7)
    L = lines[i]
    if k == 0: lines[i] = L.replace(":", "", 1)
    elif k == 1: lines[i] = L.replace("(", "", 1)
    elif k == 2: lines[i] = L.replace("circle", "circel").replace("text", "txt").replace("wait", "sleep")
    elif k == 3: lines[i] = " " + L
    elif k == 4: lines[i] = L.replace(", ", ", ", 1).rsplit(",", 1)[0] + ")" if "," in L else L + "("
    elif k == 5: lines[i] = L.replace("i", "j", 1)
    else: lines[i] = L + r.choice([" $", " +", ".", " 1"])
    return "\n".join(lines) + "\n"


def main():
    exe = sys.argv[1]
    rows = [json.loads(l)["program"] for l in open("data/oled/pairs.jsonl")]
    r = random.Random(0)
    mutants = [mutate(r, r.choice(rows)) for _ in range(20000)]
    for name, progs in (("generated", rows), ("mutated", mutants)):
        out = subprocess.run([exe], input="\n\x01\n".join(progs).encode(), capture_output=True, check=True).stdout.decode()
        c_lines = out.splitlines()
        assert len(c_lines) == len(progs), (len(c_lines), len(progs))
        agree, disagree = Counter(), []
        for src, cl in zip(progs, c_lines):
            pk, pv = py_verdict(src)
            ck, cv = cl.split(" ", 1) if " " in cl else (cl, "")
            if pk == ck == "OK":
                ok = pv == cv
                agree["same frames" if ok else "DIFFERENT FRAMES"] += 1
                if not ok: disagree.append((src, pv[:60], cv[:60]))
            elif pk == ck == "ERR":
                agree["both refuse"] += 1
            else:
                agree[f"python {pk} / c {ck}"] += 1
                disagree.append((src, f"{pk} {pv[:60]}", f"{ck} {cv[:60]}"))
        print(f"{name}: {len(progs):,} programs: {dict(agree)}")
        for src, a, b in disagree[:5]:
            print("  ---\n  " + src.replace("\n", "\n  ") + f"\n  python: {a}\n  c:      {b}")


if __name__ == "__main__":
    main()
