#!/usr/bin/env python3
"""Strict accounting and CSV generation for Experiment 2A."""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


PREFIX = "board.cache_hierarchy.iopmp_filter.filter."
LINEAR = "board.processor.cores.generator."
GUPS = "board.processor.cores.generator."


def stats(path):
    values = {}
    for line in path.read_text().splitlines():
        fields = line.split()
        if len(fields) >= 2:
            try:
                values[fields[0]] = float(fields[1])
            except ValueError:
                pass
    return values


def need(values, name):
    if name not in values:
        raise ValueError(f"missing statistic {name}")
    return values[name]


def check_equal(label, *values):
    if len(set(values)) != 1:
        raise ValueError(f"{label} mismatch: {values}")


def row_for(run):
    out = Path(run["output_dir"])
    if not (out / "RUN_COMPLETE").is_file():
        raise ValueError(f"incomplete run {run['id']}")
    log = (out / "run.log").read_text()
    if "EXP2A_DONE" not in log:
        raise ValueError(f"missing completion marker in {run['id']}")
    v = stats(out / "stats.txt")
    get = lambda name: need(v, PREFIX + name)
    received = int(get("requestsReceived"))
    checks = int(get("authorizationChecks"))
    authorized = int(get("authorized"))
    denied = int(get("denied"))
    forwarded = int(get("forwarded"))
    responses = int(get("responsesDelivered"))
    reads = int(get("reads"))
    writes = int(get("writes"))
    configured_latency = int(get("configuredLatencyCycles"))
    if configured_latency != run["latency_cycles"]:
        raise ValueError(
            f"{run['id']} configured latency {configured_latency} != manifest"
        )
    check_equal("request type accounting", received, reads + writes)
    check_equal("forward/response accounting", received, forwarded, responses)
    if run["mode"] == "protected":
        check_equal("protected authorization accounting",
                    received, checks, authorized)
        if denied:
            raise ValueError(f"{run['id']} denied {denied} valid requests")
    elif any((checks, authorized, denied)):
        raise ValueError(f"{run['id']} bypass unexpectedly authorized")

    if run["workload"] == "linear":
        check_equal("linear read bytes", int(get("bytesRead")), reads * 64)
        check_equal("linear write bytes", int(get("bytesWritten")), writes * 64)
        generated = int(need(v, LINEAR + "numPackets"))
        completed_reads = int(need(v, LINEAR + "totalReads"))
        completed_writes = int(need(v, LINEAR + "totalWrites"))
        check_equal("linear generated requests", received, generated)
        check_equal("linear completed requests", received,
                    completed_reads + completed_writes)
        performance = need(v, LINEAR + "readBW") + need(v, LINEAR + "writeBW")
        total_latency = (
            need(v, LINEAR + "totalReadLatency")
            + need(v, LINEAR + "totalWriteLatency")
        )
        updates = 0
    else:
        check_equal("GUPS read bytes", int(get("bytesRead")), reads * 8)
        check_equal("GUPS write bytes", int(get("bytesWritten")), writes * 8)
        updates = int(need(v, GUPS + "totalUpdates"))
        completed_reads = int(need(v, GUPS + "totalReads"))
        completed_writes = int(need(v, GUPS + "totalWrites"))
        check_equal("GUPS reads/writes", updates, completed_reads,
                    completed_writes)
        check_equal("GUPS request accounting", received, 2 * updates)
        performance = need(v, GUPS + "GUPS")
        total_latency = (
            need(v, GUPS + "totalReadLat")
            + need(v, GUPS + "totalWriteLat")
        )

    return {
        "run_id": run["id"], "workload": run["workload"],
        "mode": run["mode"], "latency_cycles": run["latency_cycles"],
        "repetition": run["repetition"], "seed": run["seed"],
        "requests": received, "authorized": authorized, "denied": denied,
        "forwarded": forwarded, "responses": responses,
        "reads": reads, "writes": writes,
        "bytes_read": int(get("bytesRead")),
        "bytes_written": int(get("bytesWritten")),
        "downstream_retries": int(get("downstreamRetries")),
        "upstream_retries": int(get("upstreamRetries")),
        "max_queue_occupancy": int(get("maxRequestQueueOccupancy")),
        "accepted_before_first_forward": int(
            get("requestsAcceptedBeforeFirstForward")
        ),
        "first_accept_tick": int(get("firstAcceptedTick")),
        "first_forward_tick": int(get("firstForwardedTick")),
        "minimum_forward_spacing_ticks": int(
            get("minimumForwardSpacingTicks")
        ),
        "sim_ticks": int(need(v, "simTicks")),
        "sim_seconds": need(v, "simSeconds"),
        "updates": updates, "performance": performance,
        "average_request_latency_ticks": total_latency / received,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    expected = 6 if manifest["campaign_type"] == "smoke" else 42
    if len(manifest["runs"]) != expected:
        raise SystemExit(f"expected {expected} runs, found {len(manifest['runs'])}")
    try:
        rows = [row_for(run) for run in manifest["runs"]]
        groups = defaultdict(list)
        for row in rows:
            groups[(row["workload"], row["repetition"])].append(row)
        for key, group in groups.items():
            check_equal(f"matched request count {key}",
                        *(row["requests"] for row in group))
        for workload in ("linear", "gups"):
            for repetition in range(manifest["configuration"]["repetitions"]):
                base = next(r for r in rows if r["workload"] == workload and
                            r["mode"] == "bypass" and
                            r["repetition"] == repetition)
                zero = next(r for r in rows if r["workload"] == workload and
                            r["mode"] == "protected" and
                            r["latency_cycles"] == 0 and
                            r["repetition"] == repetition)
                for field in ("sim_ticks", "performance",
                              "average_request_latency_ticks"):
                    check_equal(f"zero-latency checkpoint {workload} {field}",
                                base[field], zero[field])
                for row in (r for r in rows if r["workload"] == workload and
                            r["mode"] == "protected" and
                            r["repetition"] == repetition and
                            r["latency_cycles"] > 0):
                    expected = zero["first_forward_tick"] + (
                        row["latency_cycles"] * 1000
                    )
                    check_equal(f"modeled first-forward delay {row['run_id']}",
                                row["first_forward_tick"], expected)
                    if row["accepted_before_first_forward"] <= 1:
                        raise ValueError(
                            f"{row['run_id']} did not overlap authorization"
                        )
                    check_equal(f"pipeline throughput {row['run_id']}",
                                row["minimum_forward_spacing_ticks"], 1000)
    except (ValueError, StopIteration) as error:
        raise SystemExit(f"processing failed: {error}")

    baselines = {(r["workload"], r["repetition"]): r["performance"]
                 for r in rows if r["mode"] == "bypass"}
    for row in rows:
        row["normalized_performance"] = (
            row["performance"] / baselines[(row["workload"], row["repetition"])]
        )
    output = args.output or args.manifest.parent / "results.csv"
    with output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"PASS: {len(rows)} complete, matched, authorized runs -> {output}")


if __name__ == "__main__":
    main()
