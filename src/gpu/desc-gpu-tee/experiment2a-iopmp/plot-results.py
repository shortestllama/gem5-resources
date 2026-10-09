#!/usr/bin/env python3
"""Dependency-free SVG plots for full Experiment 2A CSV results."""

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def mean(values):
    return sum(values) / len(values)


def svg_plot(path, series, ylabel, baseline=False):
    width, height = 720, 440
    left, right, top, bottom = 90, 25, 35, 70
    xs = sorted({x for values in series.values() for x, _ in values})
    ys = [y for values in series.values() for _, y in values]
    if baseline:
        ys.append(1.0)
    ymin, ymax = min(ys), max(ys)
    padding = max((ymax - ymin) * 0.1, 0.01 if baseline else 1.0)
    ymin, ymax = ymin - padding, ymax + padding
    xscale = lambda x: left + (x - min(xs)) / (max(xs) - min(xs)) * (
        width - left - right
    )
    yscale = lambda y: top + (ymax - y) / (ymax - ymin) * (
        height - top - bottom
    )
    colors = ("#1f77b4", "#d62728", "#2ca02c")
    body = [
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<path d="M {left} {top} V {height-bottom} H {width-right}" '
        'fill="none" stroke="black"/>',
    ]
    for x in xs:
        px = xscale(x)
        body.append(f'<path d="M {px} {height-bottom} v 6" stroke="black"/>')
        body.append(f'<text x="{px}" y="{height-bottom+24}" '
                    f'text-anchor="middle">{x}</text>')
    for i in range(5):
        value = ymin + i * (ymax - ymin) / 4
        py = yscale(value)
        body.append(f'<path d="M {left-6} {py} H {width-right}" '
                    'stroke="#dddddd"/>')
        body.append(f'<text x="{left-10}" y="{py+5}" '
                    f'text-anchor="end">{value:.3g}</text>')
    if baseline:
        py = yscale(1.0)
        body.append(f'<path d="M {left} {py} H {width-right}" '
                    'stroke="#777" stroke-dasharray="6,5"/>')
    for index, (label, values) in enumerate(series.items()):
        color = colors[index % len(colors)]
        points = " ".join(f"{xscale(x):.2f},{yscale(y):.2f}" for x, y in values)
        body.append(f'<polyline points="{points}" fill="none" '
                    f'stroke="{color}" stroke-width="3"/>')
        for x, y in values:
            body.append(f'<circle cx="{xscale(x):.2f}" cy="{yscale(y):.2f}" '
                        f'r="4" fill="{color}"/>')
        body.append(f'<text x="{width-right-5}" y="{top+18*index}" '
                    f'text-anchor="end" fill="{color}">{label}</text>')
    body.extend([
        f'<text x="{(left+width-right)/2}" y="{height-18}" '
        'text-anchor="middle">Assumed fully pipelined IOPMP latency (cycles)</text>',
        f'<text x="20" y="{height/2}" text-anchor="middle" '
        f'transform="rotate(-90 20 {height/2})">{ylabel}</text>',
    ])
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" font-family="sans-serif">' + "".join(body) + "</svg>\n"
    )


def grouped(rows, workload, field):
    values = defaultdict(list)
    for row in rows:
        if row["workload"] == workload and row["mode"] == "protected":
            values[int(row["latency_cycles"])].append(float(row[field]))
    return [(latency, mean(values[latency])) for latency in sorted(values)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    rows = list(csv.DictReader(args.csv.open()))
    if len(rows) != 42:
        raise SystemExit("refusing to plot non-full campaign data")
    out = args.output_dir or args.csv.parent / "figures"
    out.mkdir(parents=True, exist_ok=True)
    svg_plot(
        out / "normalized-linear-bandwidth.svg",
        {"linear": grouped(rows, "linear", "normalized_performance")},
        "Normalized bandwidth", baseline=True,
    )
    svg_plot(
        out / "normalized-gups.svg",
        {"GUPS": grouped(rows, "gups", "normalized_performance")},
        "Normalized GUPS", baseline=True,
    )
    svg_plot(
        out / "average-request-latency.svg",
        {
            workload: [(x, y / 1000) for x, y in grouped(
                rows, workload, "average_request_latency_ticks"
            )]
            for workload in ("linear", "gups")
        },
        "Average request latency (1 GHz cycles)",
    )
    print(out)


if __name__ == "__main__":
    main()
