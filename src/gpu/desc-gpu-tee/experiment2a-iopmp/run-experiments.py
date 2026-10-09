#!/usr/bin/env python3
"""Bounded, fail-fast launcher for a prepared Experiment 2A manifest."""

import argparse
import json
import subprocess
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--timeout", type=int, default=1800,
                        help="wall-clock seconds allowed per run")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    for index, run in enumerate(manifest["runs"], 1):
        out = Path(run["output_dir"])
        out.mkdir(parents=True, exist_ok=True)
        done = out / "RUN_COMPLETE"
        if done.exists():
            print(f"[{index}/{len(manifest['runs'])}] already complete {run['id']}")
            continue
        print(f"[{index}/{len(manifest['runs'])}] {run['id']}", flush=True)
        started = time.monotonic()
        with (out / "run.log").open("w") as log:
            result = subprocess.run(
                run["command"], stdout=log, stderr=subprocess.STDOUT,
                timeout=args.timeout,
            )
        if result.returncode:
            raise SystemExit(f"{run['id']} failed with {result.returncode}")
        if not (out / "stats.txt").is_file():
            raise SystemExit(f"{run['id']} produced no stats.txt")
        done.write_text(f"wall_seconds={time.monotonic() - started:.6f}\n")


if __name__ == "__main__":
    main()
