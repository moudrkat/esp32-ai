"""Pack this sketch's BPE encoder tables into a C header.

The tinystories sketch encodes typed prompts on the device with the same
runtime/bpe_tokenizer.h as Barista, and the BTK1 asset format is the same, so
the packer is Barista's. This entry point exists so deploy.sh addresses the
sketch it is building and the generated header records which tool wrote it.

  uv run --no-project python firmware/esp32_tinystories/tools/generate_tokenizer_header.py \\
      --tokenizer <tokenizer.json> --out firmware/esp32_tinystories/generated/tokenizer_encoder.h
"""

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
BARISTA_TOOLS = TOOLS.parent.parent / "esp32_barista" / "tools"
sys.path.insert(0, str(BARISTA_TOOLS))

import generate_tokenizer_header as packer  # noqa: E402

if __name__ == "__main__":
    packer.main()
