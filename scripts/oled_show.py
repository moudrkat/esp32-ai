"""Send a list of requests to the board one after another, for filming: each request waits until the board has
written and run its program, then holds the picture for a moment before the next one.

    uv run --no-project --with pyserial python scripts/oled_show.py [--hold 4] [--port /dev/ttyACM0] [--wait-enter]

--wait-enter waits for Enter before each request instead of running straight through.
"""
import argparse
import re
import sys
import time

import serial

SCENES = [
    "write you prompt and under it I code",
    "bounce a ball twice quickly",
    "countdown 3 then coffee break with a cup",
    "blink inside a tiny chip 3 times",
]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("--hold", type=float, default=4.0, help="seconds the result stays before the next request")
    ap.add_argument("--wait-enter", action="store_true")
    ap.add_argument("--start", type=int, default=1, help="first scene, 1-based")
    args = ap.parse_args()
    s = serial.Serial(args.port, 115200, timeout=0.2)
    time.sleep(0.5)
    s.read(1 << 16)
    for i, req in enumerate(SCENES[args.start - 1:], args.start):
        if args.wait_enter:
            input(f"[{i}/{len(SCENES)}] Enter to send: {req}")
        print(f"[{i}/{len(SCENES)}] {req}", flush=True)
        s.write((req + "\n").encode())
        out, t0 = b"", time.time()
        while time.time() - t0 < 120:
            out += s.read(4096)
            m = re.search(rb"\[program (ran|refused)[^\]]*\]", out)
            if m:
                print("   ", m.group(0).decode(), flush=True)
                break
        else:
            print("    (no answer in 120 s)", flush=True)
        time.sleep(args.hold)
    return 0


if __name__ == "__main__":
    sys.exit(main())
