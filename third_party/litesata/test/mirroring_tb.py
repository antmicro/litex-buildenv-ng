#!/usr/bin/env python3

# This file is Copyright (c) 2015-2016 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from litesata.common import *
from litesata.core import LiteSATACore
from litesata.frontend.arbitration import LiteSATACrossbar
from litesata.frontend.bist import LiteSATABISTGenerator, LiteSATABISTChecker
from litesata.frontend.raid import LiteSATAMirroring

from litex.soc.interconnect.stream_sim import *

from model.hdd import *


class TB(Module):
    def __init__(self):
        self.submodules.hdd0 = HDD(n=0,
                link_debug=False, link_random_level=0,
                transport_debug=False, transport_loopback=False,
                hdd_debug=True)
        self.submodules.core0 = LiteSATACore(self.hdd0.phy)

        self.submodules.hdd1 = HDD(n=1,
                link_debug=False, link_random_level=0,
                transport_debug=False, transport_loopback=False,
                hdd_debug=True)
        self.submodules.core1 = LiteSATACore(self.hdd1.phy)

        self.submodules.mirroring = LiteSATAMirroring([self.core0, self.core1])

        self.submodules.crossbar0 = LiteSATACrossbar(self.mirroring.ports[0])
        self.submodules.generator0 = LiteSATABISTGenerator(self.crossbar0.get_port())
        self.submodules.checker0 = LiteSATABISTChecker(self.crossbar0.get_port())

        self.submodules.crossbar1 = LiteSATACrossbar(self.mirroring.ports[1])
        self.submodules.generator1 = LiteSATABISTGenerator(self.crossbar1.get_port())
        self.submodules.checker1 = LiteSATABISTChecker(self.crossbar1.get_port())

def main_generator(dut):
    dut.hdd0.malloc(0, 64)
    dut.hdd1.malloc(0, 64)
    sector = 0
    count = 1

    for i in range(2):
        for dut_generator in [dut.generator0, dut.generator1]:
            # write data (alternate generators)
            yield dut_generator.sector.eq(sector)
            yield dut_generator.count.eq(count)
            yield dut_generator.start.eq(1)
            yield
            yield dut_generator.start.eq(0)
            yield
            while not (yield dut_generator.done):
                yield

            # verify data on the 2 hdds in //
            yield dut.checker0.sector.eq(sector)
            yield dut.checker0.count.eq(count)
            yield dut.checker0.start.eq(1)
            yield dut.checker1.sector.eq(sector)
            yield dut.checker1.count.eq(count)
            yield dut.checker1.start.eq(1)
            yield
            yield dut.checker0.start.eq(0)
            yield dut.checker1.start.eq(0)
            yield
            while not (yield dut.checker0.done) or not (yield dut.checker1.done):
                yield
            print("errors {}".format((yield dut.checker0.errors) +
                                     (yield dut.checker1.errors)))

            # prepare next iteration
            sector += 1

if __name__ == "__main__":
    tb = TB()
    generators = {
        "sys" :   [main_generator(tb),
                   tb.hdd0.link.generator(),
                   tb.hdd0.phy.rx.generator(),
                   tb.hdd0.phy.tx.generator(),
                   tb.hdd1.link.generator(),
                   tb.hdd1.phy.rx.generator(),
                   tb.hdd1.phy.tx.generator()]
    }
    clocks = {"sys": 10}
    run_simulation(tb, generators, clocks, vcd_name="sim.vcd")
