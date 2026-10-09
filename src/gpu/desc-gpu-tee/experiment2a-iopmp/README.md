# Experiment 2A: IOPMP data-path latency sensitivity

This isolated experiment connects a stock gem5 `LinearGenerator` or
`GUPSGenerator` through `IopmpTrafficFilter` to the same no-cache DDR4-2400
memory system. Bypass and protected runs traverse the same bounded forwarding
path. Protected runs invoke the existing `RiscvIopmp::authorize()` with fixed
RRID 1, memory domain 0, and one region covering `[0, 256 MiB)`.

Zero cycles is the functional gem5/PMP-style baseline. Nonzero values are
hypothetical, fully pipelined authorization-latency assumptions. They are not
measured, actual, or inherent IOPMP hardware latency. Host C++ execution time
is not a modeled latency or reported performance metric.

The 64-entry bounded FIFO absorbs in-flight checks and uses normal gem5 timing
request/retry semantics. Latency delays eligibility to forward but does not
reduce the checker to one request every N cycles. Linear traffic uses fixed
work (16 MiB of 64-byte, 50/50 requests) over a 256 MiB range; the filter exits
after every response returns. GUPS performs one million stock 8-byte random
read-modify-write updates over 256 MiB. `init_memory` remains disabled.

Prepare, launch, process, and plot a full 42-run campaign:

```sh
./experiments.py --output /path/to/experiment2a-final
/path/to/experiment2a-final/run-all.sh
./process-results.py /path/to/experiment2a-final/manifest.json
./plot-results.py /path/to/experiment2a-final/results.csv
```

The dependency-free plotting helper emits three SVG figures. The processor
fails on missing runs, any valid-run denial, authorization or
forwarding mismatch, mismatched request counts, or any simulated-performance
difference between matched bypass/0 and protected/0 runs. Three repetitions use
explicit seeds 1, 2, and 3; matching configurations use the same seed.
