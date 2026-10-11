"""TEST HARNESS ONLY: actual DESC SM authorizes one native AMD Square."""
import argparse
from m5.objects import AmdProtectedGpu
from gem5.components.devices.gpus.amdgpu import MI210
from gem5.components.memory import HBM2Stack

import m5
from m5.proxy import Parent
from m5.objects import (
    AddrRange,
    RiscvIopmp,
    SimpleMemory,
    TrustedGpuControl,
)

from gem5.components.boards.riscv_board import RiscvBoard
from gem5.components.cachehierarchies.classic.private_l1_private_l2_walk_cache_hierarchy import (
    PrivateL1PrivateL2WalkCacheHierarchy,
)
from gem5.components.memory import DualChannelDDR4_2400
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.components.processors.simple_switchable_processor import (
    SimpleSwitchableProcessor,
)
from gem5.isas import ISA
from gem5.resources.resource import (
    BinaryResource,
    DiskImageResource,
)
from gem5.simulate.simulator import (
    ExitEvent,
    Simulator,
)
from gem5.utils.requires import requires

parser = argparse.ArgumentParser()
parser.add_argument("--kernel", required=True)
parser.add_argument(
    "--bootrom", help="DESC measured-boot ROM ELF (required for attestation)"
)
parser.add_argument("--disk-image", required=True)
parser.add_argument("--readfile")
parser.add_argument(
    "--run-protected-suite",
    action="store_true",
    help="run the packaged DESC Phase 6 protected GPU suite and exit",
)
parser.add_argument(
    "--cpu-type",
    choices=("timing", "atomic", "atomic-timing"),
    default="timing",
    help=(
        "CPU model; atomic-timing fast-forwards excluded initialization "
        "and switches to TimingSimpleCPU for annotated ROIs"
    ),
)
parser.add_argument(
    "--security-mode", choices=("protected", "unsecured"), default="protected"
)
parser.add_argument("--compute-latency", default="100ns")
parser.add_argument("--copy-byte-latency", default="1ns")
parser.add_argument("--vadd-element-latency", default="1ns")
parser.add_argument("--gemm-mac-latency", default="1ns")
parser.add_argument(
    "--max-ticks",
    type=int,
    help="optional positive bound for configuration smoke checks",
)
parser.add_argument("--gpu-diagnostics", action="store_true",
                    help="TEST HARNESS: GPU-only trace within the single ROI")
args = parser.parse_args()
if args.max_ticks is not None and args.max_ticks <= 0:
    parser.error("--max-ticks must be positive")
if args.readfile and args.run_protected_suite:
    parser.error("--readfile and --run-protected-suite are mutually exclusive")
readfile_contents = ""
if args.readfile:
    with open(args.readfile, encoding="utf-8") as script:
        readfile_contents = script.read()
elif args.run_protected_suite:
    readfile_contents = "/root/run-desc-gpu-tee.sh\n/sbin/m5 exit\n"

cpu_type = CPUTypes.ATOMIC if args.cpu_type == "atomic" else CPUTypes.TIMING

requires(isa_required=ISA.RISCV)


class DescGpuBoard(RiscvBoard):
    def get_pci_host(self):
        return self.platform.pci_host

    def _pre_instantiate(self, full_system=None):
        root = super()._pre_instantiate(full_system)
        # Explicit host memories avoid Parent.all traversing AMD memories.
        self.memories = list(self.get_memory().get_mem_interfaces())
        if args.bootrom:
            self.memories = list(self.memories) + [self.bootrom]
        if args.bootrom:
            self.workload.bootloader_filename = args.bootrom
            self.workload.bootloader_addr = 0x1000
            self.workload.entry_point = 0x1000
        return root


processor = (
    SimpleSwitchableProcessor(
        starting_core_type=CPUTypes.ATOMIC,
        switch_core_type=CPUTypes.TIMING,
        isa=ISA.RISCV,
        num_cores=2,
    )
    if args.cpu_type == "atomic-timing"
    else SimpleProcessor(cpu_type=cpu_type, isa=ISA.RISCV, num_cores=2)
)

board = DescGpuBoard(
    clk_freq="3GHz",
    processor=processor,
    memory=DualChannelDDR4_2400(size="3GiB"),
    cache_hierarchy=PrivateL1PrivateL2WalkCacheHierarchy(
        l1d_size="16KiB", l1i_size="16KiB", l2_size="256KiB"
    ),
)

board.set_kernel_disk_workload(
    kernel=BinaryResource(args.kernel),
    disk_image=DiskImageResource(args.disk_image, root_partition=""),
    readfile_contents=readfile_contents,
    kernel_args=[
        "rw",
        "root=/dev/vda",
        "console=ttyS0",
        "earlyprintk=ttyS0",
        "norandmaps",
        "cma=64M",
        "init=/sbin/init.gem5",
    ],
)

if args.bootrom:
    board.bootrom = SimpleMemory(
        range=AddrRange(0x1000, size=0xF000),
        writeable=False,
        conf_table_reported=False,
    )
    board.bootrom.port = board.get_cache_hierarchy().get_mem_side_port()

board.iopmp = RiscvIopmp(pio_addr=0x10204000)
iopmp = board.iopmp
# Isolated A-lite vertical test: one native GPU and one DSM-owned reservation.
board.amd = MI210(gpu_memory=HBM2Stack(size="16MiB"),
                  num_cus=1, cu_per_sqc=1, tcc_count=1)
board.amd.device.Command = 0
if isinstance(processor, SimpleSwitchableProcessor):
    # Only connectGPU's CPU lookup needs adaptation; all buses remain board's.
    from types import SimpleNamespace

    class AmdConnectionBoard:
        def get_processor(self):
            return SimpleNamespace(cores=processor._switchable_cores["switch"])

        def __getattr__(self, name):
            return getattr(board, name)

    board.amd.connectGPU(AmdConnectionBoard())
    assert board.amd.shader.cpu_pointer is processor._switchable_cores["switch"][0].get_simobject()
else:
    board.amd.connectGPU(board)
for port in board.amd.get_cpu_dma_ports():
    board.get_io_bus().cpu_side_ports = port
board.amd_backend = AmdProtectedGpu(
    pio_addr=0x10010000, gpu=board.amd.device, system=Parent.any,
    reservation_base=0, reservation_size=0x200000, test_harness=True,
    code_object="/home/jfford/gpu-smoke-mi200/mixed-isa-prototype/square-gfx90a.hsaco",
    load_image="/home/jfford/gpu-smoke-mi200/mixed-isa-prototype/square-image.bin")
board.amd_backend.pio = board.get_io_bus().mem_side_ports
board.trusted_gpu_control = TrustedGpuControl(
    pio_addr=0x10200000, gpu=board.amd_backend)
iopmp.pio = board.get_io_bus().mem_side_ports
board.trusted_gpu_control.pio = board.get_io_bus().mem_side_ports
trusted_ranges = [
    AddrRange(0x10010000, size=0x4000),
    AddrRange(0x10200000, size=0x4000),
    AddrRange(0x10204000, size=0x4000),
]
board.bridge.ranges.extend(trusted_ranges)
all_cores = (
    list(processor._all_cores())
    if isinstance(processor, SimpleSwitchableProcessor)
    else processor.get_cores()
)
for core in all_cores:
    core.get_mmu().pma_checker.uncacheable += trusted_ranges
    # One extra entry protects the evaluated 32 KiB trusted aperture.
    core.get_simobject().mmu.pmp.pmp_entries = 17
if isinstance(processor, SimpleSwitchableProcessor):

    diagnostic_flags = (
        "GPUTLB", "GPUMem", "GPUPort", "GPUCommandProc",
        "AMDGPUSystemHub", "GPUDisp", "GPUWgLatency", "RubySequencer",
    )
    roi_started = False
    roi_completed = False

    def workbegin_handler():
        global roi_started
        while True:
            if roi_started:
                raise RuntimeError("Unexpected repeated A-lite WORKBEGIN")
            # No trusted GPU operation has occurred: marker precedes GEI CREATE.
            if args.gpu_diagnostics:
                for name in diagnostic_flags:
                    m5.debug.flags[name].enable()
            print(f"ALITE_SWITCH_BEFORE Atomic->Timing tick={m5.curTick()}", flush=True)
            processor.switch()
            print(f"ALITE_SWITCH_AFTER Atomic->Timing tick={m5.curTick()}", flush=True)
            assert processor.get_cores()[0].get_simobject() is board.amd.shader.cpu_pointer
            roi_started = True
            m5.stats.reset()
            print("ALITE_ROI_TIMING_BEGIN: full enclave creation completed", flush=True)
            yield False

    def workend_handler():
        global roi_completed
        while True:
            if not roi_started or roi_completed:
                raise RuntimeError("Unexpected A-lite WORKEND")
            print(f"ALITE_WORKEND_ENTRY tick={m5.curTick()} cause={simulator.get_last_exit_event_cause()}", flush=True)
            m5.stats.dump()
            # ROI is finished; stay on TimingCPU for natural guest termination.
            if args.gpu_diagnostics:
                for name in diagnostic_flags:
                    m5.debug.flags[name].disable()
            roi_completed = True
            print(f"ALITE_ROI_END_STAY_TIMING tick={m5.curTick()}: trusted GPU completion observed", flush=True)
            yield False

    exit_handlers = {
        ExitEvent.WORKBEGIN: workbegin_handler(),
        ExitEvent.WORKEND: workend_handler(),
    }
else:
    exit_handlers = None

simulator = Simulator(board=board, on_exit_event=exit_handlers)
simulator.show_exit_event_messages()
simulator.run(max_ticks=args.max_ticks)
print(f"ALITE_SIMULATOR_RETURN tick={m5.curTick()} "
      f"cause={simulator.get_last_exit_event_cause()} "
      f"code={simulator.get_last_exit_event_code()}", flush=True)
