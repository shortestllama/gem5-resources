#!/bin/bash
set -euo pipefail
# MANUAL ONLY: fresh multi-ISA build may exceed five minutes.
cd /home/jfford/gem5
scons defconfig build/ALITE_AMD build_opts/ALL
scons build/ALITE_AMD/gem5.opt -j4
