from __future__ import annotations

import argparse
import os

from l5k_sim.l5k_parser import parse_l5k
from l5k_sim.server import serve


def _resolve_web_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", "..", "web"))


def main() -> None:
    ap = argparse.ArgumentParser(prog="l5k_sim", description="L5K Logic Sim web UI")
    ap.add_argument("l5k_file")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    project = parse_l5k(args.l5k_file)
    serve(project, _resolve_web_dir(), port=args.port)


if __name__ == "__main__":
    main()
