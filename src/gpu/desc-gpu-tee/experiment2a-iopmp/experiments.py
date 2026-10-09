#!/usr/bin/env python3
"""Prepare (but do not run) Experiment 2A manifests."""

import argparse
import hashlib
import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path


LATENCIES = (0, 1, 2, 4, 8, 16)
WORKLOADS = ("linear", "gups")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, text=True,
        stdout=subprocess.PIPE,
    ).stdout.rstrip()


def repo_state(repo):
    diff = subprocess.run(
        ["git", "-C", str(repo), "diff", "--binary", "HEAD"],
        check=True, stdout=subprocess.PIPE,
    ).stdout
    return {
        "path": str(repo),
        "head": git(repo, "rev-parse", "HEAD"),
        "status": git(repo, "status", "--short"),
        "tracked_diff_sha256": hashlib.sha256(diff).hexdigest(),
    }


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gem5-repo", type=Path, default=Path("/home/jfford/gem5"))
    parser.add_argument("--gem5-bin", type=Path,
                        default=Path("/home/jfford/gem5/build/RISCV/gem5.opt"))
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"refusing non-empty output directory: {output}")
    output.mkdir(parents=True, exist_ok=True)

    gem5_repo = args.gem5_repo.resolve()
    gem5_bin = args.gem5_bin.resolve()
    config = gem5_repo / "configs/example/gem5_library/iopmp-traffic.py"
    repetitions = 1 if args.smoke else 3
    linear_limit = 1 << 20 if args.smoke else 16 << 20
    gups_limit = 10_000 if args.smoke else 1_000_000

    runs = []
    for workload in WORKLOADS:
        configurations = [("bypass", 0), ("protected", 0)]
        if args.smoke:
            configurations.append(("protected", 1))
        else:
            configurations.extend(("protected", n) for n in LATENCIES[1:])
        for mode, latency in configurations:
            for repetition in range(repetitions):
                seed = repetition + 1
                run_id = f"{workload}-{mode}-l{latency}-r{repetition}"
                run_dir = output / "runs" / run_id
                command = [
                    str(gem5_bin), f"--outdir={run_dir}", str(config),
                    "--workload", workload, "--mode", mode,
                    "--latency", str(latency), "--queue-capacity", "64",
                    "--linear-data-limit", str(linear_limit),
                    "--gups-update-limit", str(gups_limit),
                    "--seed", str(seed),
                ]
                runs.append({
                    "id": run_id, "workload": workload, "mode": mode,
                    "latency_cycles": latency, "repetition": repetition,
                    "seed": seed, "output_dir": str(run_dir),
                    "command": command,
                })

    sources = [
        gem5_bin, config,
        gem5_repo / "src/dev/gpu_tee/IopmpTrafficFilter.py",
        gem5_repo / "src/dev/gpu_tee/iopmp_traffic_filter.hh",
        gem5_repo / "src/dev/gpu_tee/iopmp_traffic_filter.cc",
        Path(__file__).resolve(), here / "run-experiments.py",
        here / "process-results.py", here / "plot-results.py",
        here / "README.md",
    ]
    manifest = {
        "experiment": "Experiment 2A: IOPMP data-path latency sensitivity",
        "interpretation": (
            "Zero cycles is gem5-style functional authorization. Nonzero "
            "values are hypothetical fully pipelined sensitivity parameters, "
            "not measured or inherent IOPMP hardware latency."
        ),
        "campaign_type": "smoke" if args.smoke else "full",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "run_count": len(runs),
        "configuration": {
            "working_set": "256MiB", "memory": "512MiB DDR4-2400",
            "clock": "1GHz", "rrid": 1, "memory_domain": 0,
            "authorized_region": "[0, 256MiB)", "queue_capacity": 64,
            "linear_request_bytes": 64, "linear_read_percent": 50,
            "linear_rate": "64GiB/s", "linear_data_limit": linear_limit,
            "gups_request_bytes": 8, "gups_update_limit": gups_limit,
            "gups_init_memory": False, "repetitions": repetitions,
        },
        "repositories": {
            "gem5": repo_state(gem5_repo),
            "gem5-resources": repo_state(here.parents[3]),
        },
        "source_sha256": {str(path): sha256(path) for path in sources},
        "runs": runs,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    launch = output / "run-all.sh"
    launch.write_text(
        "#!/bin/sh\nset -eu\nexec "
        + shlex.join([str(here / "run-experiments.py"), str(manifest_path)])
        + "\n"
    )
    launch.chmod(0o755)
    print(f"prepared {len(runs)} runs: {manifest_path}")


if __name__ == "__main__":
    main()
