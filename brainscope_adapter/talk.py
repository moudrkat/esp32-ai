"""Chat REPL: every line you type goes to the matchbox AND brainscope at once.

    sg dialout -c 'python3 brainscope_adapter/talk.py'

Type a story opening, hit enter: the box writes it on the OLED with its own
silicon while the paced twin in the open brainscope tab thinks the same story
layer by layer. Ctrl+C to leave. ASCII only - the device tokenizer has no
diacritics.
"""

import json
import subprocess
import threading
import urllib.request

PORT = "/dev/ttyACM0"
BRAINSCOPE = "http://localhost:8010/v1/chat/completions"
UNPLUGGED = "http://localhost:8011/v1/chat/completions"

subprocess.run(["stty", "-F", PORT, "115200", "raw", "-echo"], check=True)
print("chatting with the matchbox - type a story opening, Ctrl+C to quit")
while True:
    try:
        line = input("story> ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        break
    if not line:
        continue
    if not line.isascii():
        print("(ascii only, please)")
        continue
    with open(PORT, "wb", buffering=0) as ser:
        ser.write(line.encode("ascii") + b"\n")

    def ask(url, label):
        req = urllib.request.Request(
            url,
            data=json.dumps({"messages": [{"role": "user", "content": line}],
                             "max_tokens": 200, "temperature": 0}).encode(),
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                text = json.load(r)["choices"][0]["message"]["content"]
            print(f"\n{label}: {text[:110]}...")
        except Exception as e:
            print(f"\n({label} not reachable: {e})")

    # both twins stream at once, each into its own open tab
    threads = [threading.Thread(target=ask, args=(BRAINSCOPE, "twin")),
               threading.Thread(target=ask, args=(UNPLUGGED, "unplugged"))]
    for t in threads: t.start()
    for t in threads: t.join()
