#!/usr/bin/env python3

# This file is Copyright (c) 2015-2016 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from litesata.common import *
from litesata.core.link import LiteSATACONTInserter, LiteSATACONTRemover

from litex.soc.interconnect.stream_sim import *


class ContPacket(list):
    def __init__(self, data=[]):
        self.ongoing = False
        self.done = False
        for d in data:
            self.append(d)


class ContStreamer(PacketStreamer):
    def __init__(self):
        PacketStreamer.__init__(self, phy_description(32), packet_cls=ContPacket)

    @passive
    def generator(self):
        yield self.source.charisk.eq(0)
        # Note: for simplicity we generate charisk by detecting
        # primitives in data
        for k, v in primitives.items():
            try:
                if self.source_data == v:
                    yield self.source.charisk.eq(0b0001)
            except:
                pass
        yield from PacketStreamer.generator(self)

class ContLogger(PacketLogger):
    def __init__(self):
        PacketLogger.__init__(self, phy_description(32), packet_cls=ContPacket)


class TB(Module):
    def __init__(self):
        self.submodules.streamer = ContStreamer()
        self.submodules.streamer_randomizer = Randomizer(phy_description(32), level=50)
        self.submodules.inserter = LiteSATACONTInserter(phy_description(32))
        self.submodules.remover = LiteSATACONTRemover(phy_description(32))
        self.submodules.logger_randomizer = Randomizer(phy_description(32), level=50)
        self.submodules.logger = ContLogger()

        self.submodules.pipeline = Pipeline(
            self.streamer,
            self.streamer_randomizer,
            self.inserter,
            self.remover,
            self.logger_randomizer,
            self.logger
        )

def main_generator(dut):
    test_packet = ContPacket([
        primitives["SYNC"],
        primitives["SYNC"],
        primitives["SYNC"],
        primitives["SYNC"],
        primitives["SYNC"],
        primitives["SYNC"],
        primitives["ALIGN"],
        primitives["ALIGN"],
        primitives["SYNC"],
        primitives["SYNC"],
        #primitives["SYNC"],
        0x00000000,
        0x00000001,
        0x00000002,
        0x00000003,
        0x00000004,
        0x00000005,
        0x00000006,
        0x00000007,
        primitives["SYNC"],
        primitives["SYNC"],
        primitives["SYNC"],
        primitives["SYNC"],
        primitives["ALIGN"],
        primitives["ALIGN"],
        primitives["SYNC"],
        primitives["SYNC"],
        primitives["SYNC"],
        primitives["SYNC"]]*4
        )
    streamer_packet = ContPacket(test_packet)
    yield from dut.streamer.send_blocking(streamer_packet)
    yield from dut.logger.receive(len(test_packet))
    #for d in self.logger.packet:
    #    print("{:08x}".format(d))

    # check results
    s, l, e = check(streamer_packet, dut.logger.packet)
    print("shift " + str(s) + " / length " + str(l) + " / errors " + str(e))

if __name__ == "__main__":
    tb = TB()
    generators = {
        "sys" :   [main_generator(tb),
                   tb.streamer.generator(),
                   tb.streamer_randomizer.generator(),
                   tb.logger.generator(),
                   tb.logger_randomizer.generator()]
    }
    clocks = {"sys": 10}
    run_simulation(tb, generators, clocks, vcd_name="sim.vcd")
