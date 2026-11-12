from __future__ import annotations

import argparse
import json
from pathlib import Path

from see_benchmarks.signing import (
    generate_keypair,
    write_private_key,
    write_public_key_set,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Génère une paire de clés Ed25519 de signature.")
    parser.add_argument("key_id")
    parser.add_argument("private_key", type=Path)
    parser.add_argument(
        "--public",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "keys" / "public.json",
    )
    args = parser.parse_args()

    private_payload, public_key = generate_keypair(args.key_id)
    write_private_key(args.private_key, private_payload)
    write_public_key_set(args.public, [public_key])
    print(
        json.dumps(
            {
                "keyId": public_key.key_id,
                "privateKey": str(args.private_key),
                "publicKeySet": str(args.public),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
