from __future__ import annotations

import argparse
from pathlib import Path

from see_benchmarks.signing import SIGNATURE_SUFFIX, checksum_file, verify_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Vérifie la signature détachée d'un pack.")
    parser.add_argument("pack", type=Path)
    parser.add_argument("--signature", type=Path)
    parser.add_argument(
        "--keys",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "keys" / "public.json",
    )
    args = parser.parse_args()
    signature = args.signature or Path(str(args.pack) + SIGNATURE_SUFFIX)
    key_id = verify_file(args.pack, signature, args.keys)
    print(f"OK keyId={key_id} sha256={checksum_file(args.pack)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
