"""Score a trained model the way it will be used: for each held-out request it writes a program (greedy, as the
board does), the interpreter runs it, and the picture is compared with the reference program's.

Outcomes, worst first, after espcontrol's lesson that exact match hides what matters:
  wrong picture   runs, but draws something else than asked     (the real failure)
  refused         does not parse or breaks a limit: the board says "can't run this" (wrong but harmless)
  same picture    draws exactly what the reference draws, frame by frame (however it is spelled)

    python -m research.oled.eval runs/ple-oled-s0-best.pt --vocab 2048 [--n 600]
"""
import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

import torch
from tokenizers import Tokenizer

from research.oled.lang import LangError, run, same
from model import Config, make_model   # src/ is on the path (pip install -e . or PYTHONPATH=src)

ROOT = Path(__file__).resolve().parents[2]


def load(ckpt, device):
    ck = torch.load(ckpt, map_location=device)
    cfg = ck["cfg"]
    base = Config(**{k: v for k, v in cfg.items() if k in Config.__dataclass_fields__})
    model = make_model("ple", 0, base, verbose=False, fixed_ffn=cfg.get("ffn_hidden"))
    model.load_state_dict(ck["state"])
    return model.to(device).eval(), cfg


@torch.no_grad()
def write(model, tok, eot, prompt, device, seq_len, max_new=240):
    ids = tok.encode(f"# {prompt}\n").ids
    x = torch.tensor([ids], device=device)
    out = []
    for _ in range(max_new):
        if x.shape[1] >= seq_len:
            break
        logits, _ = model(x[:, -seq_len:])
        nxt = int(logits[0, -1].argmax())
        if nxt == eot:
            break
        out.append(nxt)
        x = torch.cat([x, torch.tensor([[nxt]], device=device)], 1)
    return tok.decode(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("ckpt")
    ap.add_argument("--vocab", type=int, default=2048)
    ap.add_argument("--n", type=int, default=600, help="held-out requests to score")
    ap.add_argument("--pairs", default=None, help="score these requests instead of val (e.g. freeform_dev.jsonl)")
    ap.add_argument("--out", default=None, help="jsonl with every request, program and outcome")
    args = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    d = ROOT / "data" / "oled" / f"vocab-{args.vocab}"
    tok = Tokenizer.from_file(str(d / "tokenizer.json"))
    eot = tok.token_to_id("<|endoftext|>")
    model, cfg = load(args.ckpt, device)
    pairs = [json.loads(l) for l in open(args.pairs or d / "val_pairs.jsonl")]
    random.Random(0).shuffle(pairs)
    pairs = pairs[:args.n]
    outcome, by_fam, rows = Counter(), {}, []
    for p in pairs:
        prog = write(model, tok, eot, p["prompt"], device, cfg["seq_len"])
        try:
            got = run(prog)
            ok = same(got, run(p["program"]))
            o = "same picture" if ok else "wrong picture"
        except LangError as e:
            o = "refused"
        outcome[o] += 1
        by_fam.setdefault(p["family"], Counter())[o] += 1
        rows.append({**p, "written": prog, "outcome": o})
    n = len(pairs)
    print(f"{n} held-out requests: " + ", ".join(f"{k} {v / n:.1%}" for k, v in outcome.most_common()))
    for fam, c in sorted(by_fam.items(), key=lambda kv: kv[1]["same picture"] / sum(kv[1].values())):
        t = sum(c.values())
        print(f"  {fam:18s} {c['same picture'] / t:6.1%} same | {c['wrong picture'] / t:6.1%} wrong | {c['refused'] / t:6.1%} refused  (n={t})")
    if args.out:
        with open(args.out, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    sys.exit(main())
