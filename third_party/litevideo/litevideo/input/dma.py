from migen import *
from migen.genlib.fsm import FSM, NextState

from litex.soc.interconnect.csr import *
from litex.soc.interconnect.csr_eventmanager import *
from litex.soc.interconnect import stream

from litedram.frontend.dma import LiteDRAMDMAWriter

# Slot status: EMPTY=0 LOADED=1 PENDING=2
class _Slot(Module, AutoCSR):
    def __init__(self, addr_bits, alignment_bits):
        self.ev_source = EventSourceLevel()
        self.address = Signal(addr_bits)
        self.address_reached = Signal(addr_bits)
        self.address_valid = Signal()
        self.address_done = Signal()

        self._status = CSRStorage(2, write_from_dev=True)
        self._address = CSRStorage(addr_bits + alignment_bits, write_from_dev=True)

        # # #

        self.comb += [
            self.address.eq(self._address.storage[alignment_bits:]),
            self.address_valid.eq(self._status.storage[0]),
            self._status.dat_w.eq(2),
            self._status.we.eq(self.address_done),
            self._address.dat_w[alignment_bits:].eq(self.address_reached),
            self._address.we.eq(self.address_done),
            self.ev_source.trigger.eq(self._status.storage[1])
        ]


class _SlotArray(Module, AutoCSR):
    def __init__(self, nslots, addr_bits, alignment_bits):
        self.submodules.ev = EventManager()
        self.address = Signal(addr_bits)
        self.address_reached = Signal(addr_bits)
        self.address_valid = Signal()
        self.address_done = Signal()

        # # #

        slots = [_Slot(addr_bits, alignment_bits) for i in range(nslots)]
        for n, slot in enumerate(slots):
            setattr(self.submodules, "slot"+str(n), slot)
            setattr(self.ev, "slot"+str(n), slot.ev_source)
        self.ev.finalize()

        change_slot = Signal()
        current_slot = Signal(max=nslots)
        self.sync += If(change_slot, [If(slot.address_valid, current_slot.eq(n))
                         for n, slot in reversed(list(enumerate(slots)))])
        self.comb += change_slot.eq(~self.address_valid | self.address_done)

        self.comb += [
            self.address.eq(Array(slot.address for slot in slots)[current_slot]),
            self.address_valid.eq(Array(slot.address_valid for slot in slots)[current_slot])
        ]
        self.comb += [slot.address_reached.eq(self.address_reached) for slot in slots]
        self.comb += [slot.address_done.eq(self.address_done & (current_slot == n))
                          for n, slot in enumerate(slots)]


class DMA(Module):
    def __init__(self, dram_port, nslots):
        bus_aw = dram_port.aw
        bus_dw = dram_port.dw
        alignment_bits = bits_for(bus_dw//8) - 1

        fifo_word_width = bus_dw
        self.frame = stream.Endpoint([("sof", 1), ("pixels", fifo_word_width)])
        self._frame_size = CSRStorage(bus_aw + alignment_bits)
        self.submodules._slot_array = _SlotArray(nslots, bus_aw, alignment_bits)
        self.ev = self._slot_array.ev

        # # #

        # address generator + maximum memory word count to prevent DMA buffer
        # overrun
        reset_words = Signal()
        count_word = Signal()
        last_word = Signal()
        current_address = Signal(bus_aw)
        mwords_remaining = Signal(bus_aw)
        self.comb += [
            self._slot_array.address_reached.eq(current_address),
            last_word.eq(mwords_remaining == 1)
        ]
        self.sync += [
            If(reset_words,
                current_address.eq(self._slot_array.address),
                mwords_remaining.eq(self._frame_size.storage[alignment_bits:])
            ).Elif(count_word,
                current_address.eq(current_address + 1),
                mwords_remaining.eq(mwords_remaining - 1)
            )
        ]

        memory_word = Signal(bus_dw)
        pixbits = []
        for i in range(bus_dw//16):
            pixbits.append(self.frame.pixels)
        self.comb += memory_word.eq(Cat(*pixbits))

        # bus accessor
        self.submodules._bus_accessor = LiteDRAMDMAWriter(dram_port)
        self.comb += [
            self._bus_accessor.sink.address.eq(current_address),
            self._bus_accessor.sink.data.eq(memory_word)
        ]

        # control FSM
        fsm = FSM()
        self.submodules += fsm

        fsm.act("WAIT_SOF",
            reset_words.eq(1),
            self.frame.ready.eq(~self._slot_array.address_valid |
                                ~self.frame.sof),
            If(self._slot_array.address_valid &
               self.frame.sof &
               self.frame.valid,
               NextState("TRANSFER_PIXELS")
            )
        )
        fsm.act("TRANSFER_PIXELS",
            self.frame.ready.eq(self._bus_accessor.sink.ready),
            If(self.frame.valid,
                self._bus_accessor.sink.valid.eq(1),
                If(self._bus_accessor.sink.ready,
                    count_word.eq(1),
                    If(last_word,
                        NextState("EOF")
                    )
                )
            )
        )
        fsm.act("EOF",
            If(~dram_port.wdata.valid,
                self._slot_array.address_done.eq(1),
                NextState("WAIT_SOF")
            )
        )

    def get_csrs(self):
        return [self._frame_size] + self._slot_array.get_csrs()
