from __future__ import annotations

import argparse
from pathlib import Path

from see_benchmarks.signing import SIGNATURE_SUFFIX, sign_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Signe un pack avec une clé Ed25519 locale.")
    parser.add_argument("pack", type=Path)
    parser.add_argument("private_key", type=Path)
    parser.add_argument("--signature", type=Path)
    args = parser.parse_args()
    signature = args.signature or Path(str(args.pack) + SIGNATURE_SUFFIX)
    envelope = sign_file(args.pack, args.private_key, signature_path=signature)
    print(f"{signature} (keyId={envelope.key_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
