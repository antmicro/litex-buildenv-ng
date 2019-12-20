# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from litesata.common import *

from migen.genlib.cdc import PulseSynchronizer, MultiReg
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.misc import WaitTimer


class _PulseSynchronizer(PulseSynchronizer):
    def __init__(self, i, idomain, o, odomain):
        PulseSynchronizer.__init__(self, idomain, odomain)
        self.comb += [
            self.i.eq(i),
            o.eq(self.o)
        ]


class _RisingEdge(Module):
    def __init__(self, i, o):
        i_d = Signal()
        self.sync += i_d.eq(i)
        self.comb += o.eq(i & ~i_d)

# --------------------------------------------------------------------------------------------------

class A7LiteSATAPHYCRG(Module):
    def __init__(self, clock_pads_or_refclk, pads, gtp, revision, clk_freq):
        self.tx_reset = Signal()
        self.rx_reset = Signal()
        self.ready = Signal()
        self.qplllock = Signal()

        self.clock_domains.cd_sata_refclk = ClockDomain()
        self.clock_domains.cd_sata_tx = ClockDomain()
        self.clock_domains.cd_sata_rx = ClockDomain()

        # CPLL -------------------------------------------------------------------------------------
        #   (sata_gen3) 150MHz / VCO @ 3GHz / Line rate @ 6Gbps
        #   (sata_gen2 & sata_gen1) VCO still @ 3 GHz, Line rate is
        #   decreased with output dividers.
        if isinstance(clock_pads_or_refclk, Signal):
            self.refclk = clock_pads_or_refclk
        else:
            self.refclk = Signal()
            clock_pads = clock_pads_or_refclk
            self.specials += Instance("IBUFDS_GTE2",
                i_CEB=0,
                i_I=clock_pads.refclk_p,
                i_IB=clock_pads.refclk_n,
                o_O=self.refclk
            )

        self.comb += gtp.gtrefclk0.eq(self.refclk)
        self.comb += self.cd_sata_refclk.clk.eq(self.refclk)

        # TX clocking ------------------------------------------------------------------------------
        #   (sata_gen3) 150MHz from CPLL TXOUTCLK, sata_tx clk @ 300MHz (16-bits) /  150MHz (32-bits)
        #   (sata_gen2) 150MHz from CPLL TXOUTCLK, sata_tx clk @ 150MHz (16-bits) /   75MHz (32-bits)
        #   (sata_gen1) 150MHz from CPLL TXOUTCLK, sata_tx clk @ 75MHz  (16-bits) / 37.5MHz (32-bits)
        mmcm_mult = 8.0
        mmcm_div_config = {
            "sata_gen1":   16.0*gtp.data_width/16,
            "sata_gen2":    8.0*gtp.data_width/16,
            "sata_gen3":    4.0*gtp.data_width/16
        }
        mmcm_div = mmcm_div_config[revision]
        use_mmcm = mmcm_mult/mmcm_div != 1.0

        if use_mmcm:
            mmcm_reset = Signal()
            mmcm_locked_async = Signal()
            mmcm_locked = Signal()
            mmcm_fb = Signal()
            mmcm_clk_i = Signal()
            mmcm_clk0_o = Signal()
            self.specials += [
                Instance("BUFG", i_I=gtp.txoutclk, o_O=mmcm_clk_i),
                Instance("MMCME2_ADV",
                     p_BANDWIDTH="HIGH", p_COMPENSATION="ZHOLD", i_RST=mmcm_reset, o_LOCKED=mmcm_locked_async,

                     # DRP
                     i_DCLK=0, i_DEN=0, i_DWE=0, #o_DRDY=,
                     i_DADDR=0, i_DI=0, #o_DO=,

                     # VCO
                     p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=6.66667,
                     p_CLKFBOUT_MULT_F=mmcm_mult, p_CLKFBOUT_PHASE=0.000, p_DIVCLK_DIVIDE=1,
                     i_CLKIN1=mmcm_clk_i, i_CLKFBIN=mmcm_fb, o_CLKFBOUT=mmcm_fb,

                     # CLK0
                     p_CLKOUT0_DIVIDE_F=mmcm_div, p_CLKOUT0_PHASE=0.000, o_CLKOUT0=mmcm_clk0_o,
                ),
                Instance("BUFG", i_I=mmcm_clk0_o, o_O=self.cd_sata_tx.clk),
                MultiReg(mmcm_locked_async, mmcm_locked, "sys"),
            ]
        else:
            mmcm_locked = Signal(reset=1)
            mmcm_reset = Signal()
            self.specials += Instance("BUFG", i_I=gtp.txoutclk, o_O=self.cd_sata_tx.clk)

        self.comb += [
            gtp.txusrclk.eq(self.cd_sata_tx.clk),
            gtp.txusrclk2.eq(self.cd_sata_tx.clk)
        ]

        # RX clocking ------------------------------------------------------------------------------
        #   (sata_gen3) sata_rx recovered clk @  @ 300MHz (16-bits) /  150MHz (32-bits) from GTP RXOUTCLK
        #   (sata_gen2) sata_rx recovered clk @  @ 150MHz (16-bits) /   75MHz (32-bits) from GTP RXOUTCLK
        #   (sata_gen1) sata_rx recovered clk @  @ 75MHz  (16-bits) / 37.5MHz (32-bits) from GTP RXOUTCLK
        self.specials += [
            Instance("BUFG", i_I=gtp.rxoutclk, o_O=self.cd_sata_rx.clk),
        ]
        self.comb += [
            gtp.rxusrclk.eq(self.cd_sata_rx.clk),
            gtp.rxusrclk2.eq(self.cd_sata_rx.clk)
        ]

        # Configuration Reset ----------------------------------------------------------------------

        # PLL reset must be at least 500us
        pll_reset_cycles = ceil(500e-9*clk_freq)
        pll_reset_timer = WaitTimer(pll_reset_cycles)
        self.submodules += pll_reset_timer


        # TX Startup FSM ---------------------------------------------------------------------------
        self.tx_ready = Signal()
        self.gttxreset = Signal()
        self.qpllreset = Signal()
        self.txuserrdy = Signal()
        self.tx_startup_fsm = tx_startup_fsm = ResetInserter()(FSM(reset_state="PLL_RESET"))
        self.submodules += tx_startup_fsm

        txphaligndone = Signal(reset=1)
        txphaligndone_rising = Signal()
        self.sync += txphaligndone.eq(gtp.txphaligndone)
        self.sync += gtp.gttxreset.eq(self.gttxreset)
        self.sync += gtp.qpllreset.eq(self.qpllreset)
        self.sync += gtp.txuserrdy.eq(self.txuserrdy)
        self.comb += txphaligndone_rising.eq(gtp.txphaligndone & ~txphaligndone)

        tx_startup_fsm.act("PLL_RESET",
            mmcm_reset.eq(1),
            self.qpllreset.eq(1),
            pll_reset_timer.wait.eq(1),
            If(pll_reset_timer.done,
                NextState("GTP_RESET")
            )
        )
        tx_startup_fsm.act("GTP_RESET",
            mmcm_reset.eq(1),
            self.gttxreset.eq(1),
            If(self.qplllock,
                NextState("WAIT_MMCM")
            )
        )
        tx_startup_fsm.act("WAIT_MMCM",
            self.gttxreset.eq(1),
            If(mmcm_locked,
                NextState("WAIT_GTP_RESET_DONE")
            )
        )
        # Release GTP reset and wait for GTP resetdone
        # (from UG482, GTP is reset on falling edge
        # of gttxreset)
        tx_startup_fsm.act("WAIT_GTP_RESET_DONE",
            self.txuserrdy.eq(1),
            If(gtp.txresetdone,
                NextState("ALIGN")
            )
        )
        # Start delay alignment
        tx_startup_fsm.act("ALIGN",
            self.txuserrdy.eq(1),
            gtp.txdlysreset.eq(1),
            If(gtp.txdlysresetdone,
                NextState("READY"), # FIXME
                #NextState("PHALIGN")
            )
        )
        # Start phase alignment
        tx_startup_fsm.act("PHALIGN",
            self.txuserrdy.eq(1),
            gtp.txphinit.eq(1),
            If(gtp.txphinitdone,
                NextState("WAIT_FIRST_ALIGN_DONE")
            )
        )
        # Wait 2 rising edges of Xxphaligndone
        # (from UG482 in TX Buffer Bypass in Single-Lane Auto Mode)
        tx_startup_fsm.act("WAIT_FIRST_ALIGN_DONE",
            self.txuserrdy.eq(1),
            gtp.txphalign.eq(1),
            If(txphaligndone_rising,
                NextState("WAIT_SECOND_ALIGN_DONE")
            )
        )
        tx_startup_fsm.act("WAIT_SECOND_ALIGN_DONE",
            self.txuserrdy.eq(1),
            gtp.txdlyen.eq(1),
            If(txphaligndone_rising,
                NextState("READY")
            )
        )
        tx_startup_fsm.act("READY",
            self.txuserrdy.eq(1),
            gtp.txdlyen.eq(1),
            self.tx_ready.eq(1),
        )


        tx_ready_timer = WaitTimer(int(2e-3*clk_freq))
        self.submodules += tx_ready_timer
        self.comb += [
            tx_ready_timer.wait.eq(~self.tx_ready & ~tx_startup_fsm.reset),
            tx_startup_fsm.reset.eq(self.tx_reset | tx_ready_timer.done),
        ]


        # RX Startup FSM ---------------------------------------------------------------------------
        self.rx_ready = Signal()
        self.gtrxreset = Signal()
        self.rxuserrdy = Signal()
        self.rx_startup_fsm = rx_startup_fsm = ResetInserter()(FSM(reset_state="IDLE"))
        self.submodules += rx_startup_fsm

        cdr_stable_timer = WaitTimer(1024)
        self.submodules += cdr_stable_timer

        self.sync += gtp.gtrxreset.eq(self.gtrxreset)
        self.sync += gtp.rxuserrdy.eq(self.rxuserrdy)
        rx_startup_fsm.act("IDLE",
            If(self.tx_ready,
                NextState("RESET_GTP")
            )
        )
        # FIXME: missing DRP reconfig
        # Reset GTP
        rx_startup_fsm.act("RESET_GTP",
            self.gtrxreset.eq(1),
            NextState("RELEASE_GTP")
        )
        # Release GTP reset and wait for GTP resetdone
        # (from UG482, GTP is reset on falling edge
        # of gtrxreset)
        rx_startup_fsm.act("RELEASE_GTP",
            self.rxuserrdy.eq(1),
            cdr_stable_timer.wait.eq(1),
            If(gtp.rxresetdone &  cdr_stable_timer.done,
                NextState("ALIGN")
            )
        )
        # Start Delay alignment
        rx_startup_fsm.act("ALIGN",
            self.rxuserrdy.eq(1),
            gtp.rxdlyreset.eq(1),
            If(gtp.rxdlyresetdone,
                NextState("WAIT_ALIGN_DONE")
            )
        )
        # Wait Delay alignment
        rx_startup_fsm.act("WAIT_ALIGN_DONE",
            self.rxuserrdy.eq(1),
            If(gtp.rxsyncdone,
                NextState("READY")
            )
        )
        rx_startup_fsm.act("READY",
            self.rxuserrdy.eq(1),
            self.rx_ready.eq(1)
        )

        rx_ready_timer = WaitTimer(int(2e-3*clk_freq))
        self.submodules += rx_ready_timer
        self.comb += [
            rx_ready_timer.wait.eq(~self.rx_ready & ~rx_startup_fsm.reset),
            rx_startup_fsm.reset.eq(self.rx_reset | rx_ready_timer.done),
        ]

        # Ready ------------------------------------------------------------------------------------
        self.comb += self.ready.eq(self.tx_ready & self.rx_ready)

        # Reset for SATA TX/RX clock domains -------------------------------------------------------
        self.specials += [
            AsyncResetSynchronizer(self.cd_sata_tx, ~(gtp.qplllock & mmcm_locked) | self.tx_reset),
            AsyncResetSynchronizer(self.cd_sata_rx, ~gtp.qplllock | self.rx_reset),
            MultiReg(gtp.qplllock, self.qplllock, "sys"),
        ]

# --------------------------------------------------------------------------------------------------

class GTPQuadPLL(Module):
    def __init__(self, refclk, refclk_freq, linerate):
        self.pd = Signal()
        self.clk = Signal()
        self.refclk = Signal()
        self.reset = Signal()
        self.lock = Signal()
        self.config = config = self.compute_config(refclk_freq, linerate)

        # # #

        gtpe2_common_params = dict(
            # common
            i_GTREFCLK0=refclk,
            i_BGBYPASSB=1,
            i_BGMONITORENB=1,
            i_BGPDB=1,
            i_BGRCALOVRD=0b11111,
            i_RCALENB=1,

            # pll0
            p_PLL0_FBDIV=config["n2"],
            p_PLL0_FBDIV_45=config["n1"],
            p_PLL0_REFCLK_DIV=config["m"],
            i_PLL0LOCKEN=1,
            i_PLL0PD=self.pd,
            i_PLL0REFCLKSEL=0b001,
            i_PLL0RESET=self.reset,
            o_PLL0LOCK=self.lock,
            o_PLL0OUTCLK=self.clk,
            o_PLL0OUTREFCLK=self.refclk,

            # pll1 (not used: power down)
            i_PLL1PD=1,
        )
        self.specials += Instance("GTPE2_COMMON", **gtpe2_common_params)

    @staticmethod
    def compute_config(refclk_freq, linerate):
        for n1 in 4, 5:
            for n2 in 1, 2, 3, 4, 5:
                for m in 1, 2:
                    vco_freq = refclk_freq*(n1*n2)/m
                    if 1.6e9 <= vco_freq <= 3.3e9:
                        for d in 1, 2, 4, 8, 16:
                            current_linerate = vco_freq*2/d
                            if current_linerate == linerate:
                                return {"n1": n1, "n2": n2, "m": m, "d": d,
                                        "vco_freq": vco_freq,
                                        "clkin": refclk_freq,
                                        "linerate": linerate}
        msg = "No config found for {:3.2f} MHz refclk / {:3.2f} Gbps linerate."
        raise ValueError(msg.format(refclk_freq/1e6, linerate/1e9))

    def __repr__(self):
        config = self.config
        r = """
GTPQuadPLL
==============
  overview:
  ---------
       +--------------------------------------------------+
       |                                                  |
       |   +-----+  +---------------------------+ +-----+ |
       |   |     |  | Phase Frequency Detector  | |     | |
CLKIN +----> /M  +-->       Charge Pump         +-> VCO +---> CLKOUT
       |   |     |  |       Loop Filter         | |     | |
       |   +-----+  +---------------------------+ +--+--+ |
       |              ^                              |    |
       |              |    +-------+    +-------+    |    |
       |              +----+  /N2  <----+  /N1  <----+    |
       |                   +-------+    +-------+         |
       +--------------------------------------------------+
                            +-------+
                   CLKOUT +->  2/D  +-> LINERATE
                            +-------+
  config:
  -------
    CLKIN    = {clkin}MHz
    CLKOUT   = CLKIN x (N1 x N2) / M = {clkin}MHz x ({n1} x {n2}) / {m}
             = {vco_freq}GHz
    LINERATE = CLKOUT x 2 / D = {vco_freq}GHz x 2 / {d}
             = {linerate}GHz
""".format(clkin=config["clkin"]/1e6,
           n1=config["n1"],
           n2=config["n2"],
           m=config["m"],
           vco_freq=config["vco_freq"]/1e9,
           d=config["d"],
           linerate=config["linerate"]/1e9)
        return r

# --------------------------------------------------------------------------------------------------

class A7LiteSATAPHY(Module):
    def __init__(self, pads, revision, data_width=16):
        assert data_width in [16, 32]
        # Common signals
        self.data_width = data_width

        # control
        self.tx_idle = Signal()         #i

        self.tx_cominit_stb = Signal()  #i
        self.tx_cominit_ack = Signal()  #o
        self.tx_comwake_stb = Signal()  #i
        self.tx_comwake_ack = Signal()  #o

        self.rx_idle = Signal()         #o
        self.rx_cdrhold = Signal()      #i

        self.rx_cominit_stb = Signal()  #o
        self.rx_comwake_stb = Signal()  #o

        self.rxdisperr = Signal(data_width//8)      #o
        self.rxnotintable = Signal(data_width//8)   #o

        # datapath
        self.sink = stream.Endpoint(phy_description(data_width))
        self.source = stream.Endpoint(phy_description(data_width))

        # K7 specific signals
        # Channel - Ref Clock Ports
        self.gtrefclk0 = Signal()

        # Quad PLL
        self.qplllock = Signal()
        self.qpllreset = Signal()

        # Receive Ports
        self.rxuserrdy = Signal()

        # Receive Ports - 8b10b Decoder
        self.rxcharisk = Signal(data_width//8)

        # Receive Ports - RX Data Path interface
        self.gtrxreset = Signal()
        self.rxdata = Signal(data_width)
        self.rxoutclk = Signal()
        self.rxusrclk = Signal()
        self.rxusrclk2 = Signal()

        # Receive Ports - RX PLL Ports
        self.rxresetdone = Signal()
        self.rxdlyreset = Signal()
        self.rxdlyresetdone = Signal()
        self.rxsyncdone = Signal()

        # Receive Ports - RX Ports for SATA
        self.rxcominitdet = Signal()
        self.rxcomwakedet = Signal()

        # Transmit Ports
        self.txuserrdy = Signal()

        # Transmit Ports - 8b10b Encoder Control Ports
        self.txcharisk = Signal(data_width//8)

        # Transmit Ports - TX Data Path interface
        self.gttxreset = Signal()
        self.txdata = Signal(data_width)
        self.txoutclk = Signal()
        self.txusrclk = Signal()
        self.txusrclk2 = Signal()

        # Transmit Ports - TX PLL Ports
        self.txresetdone = Signal()
        self.txdlyen = Signal()
        self.txdlysreset = Signal()
        self.txdlysresetdone = Signal()
        self.txphalign = Signal()
        self.txphaligndone = Signal()
        self.txphinit = Signal()
        self.txphinitdone = Signal()

        # Transmit Ports - TX Ports for PCI Express
        self.txelecidle = Signal(reset=1)

        # Transmit Ports - TX Ports for SATA
        self.txcomfinish = Signal()
        self.txcominit = Signal()
        self.txcomwake = Signal()

        # Power-down signals
        self.qpllpd = Signal()
        self.rxpd   = Signal()
        self.txpd   = Signal()

        # Config at startup
        div_config = {
            "sata_gen1": 4,
            "sata_gen2": 2,
            "sata_gen3": 1
            }
        rxout_div = div_config[revision]
        txout_div = div_config[revision]

        cdr_config = {
            "sata_gen1": 0x0000047FE106024481010,
            "sata_gen2": 0x0000047FE206024481010,
            "sata_gen3": 0x0000087FE206024441010
        }
        rxcdr_cfg = cdr_config[revision]

        # Specific / Generic signals encoding/decoding ---------------------------------------------
        self.comb += [
            self.txelecidle.eq(self.tx_idle | self.txpd),
            self.tx_cominit_ack.eq(self.tx_cominit_stb & self.txcomfinish),
            self.tx_comwake_ack.eq(self.tx_comwake_stb & self.txcomfinish),
            self.rx_cominit_stb.eq(self.rxcominitdet),
            self.rx_comwake_stb.eq(self.rxcomwakedet),
        ]
        self.submodules += [
            _RisingEdge(self.tx_cominit_stb, self.txcominit),
            _RisingEdge(self.tx_comwake_stb, self.txcomwake),
        ]

        self.sync.sata_rx += [
            self.source.valid.eq(1),
            self.source.charisk.eq(self.rxcharisk),
            self.source.data.eq(self.rxdata)
        ]

        self.sync.sata_tx += [
            self.txcharisk.eq(self.sink.charisk),
            self.txdata.eq(self.sink.data),
            self.sink.ready.eq(1),
        ]

        # Internals and clock domain crossing ------------------------------------------------------
        # sys_clk --> sata_tx clk
        txuserrdy = Signal()
        txpd = Signal()
        txelecidle = Signal(reset=1)
        txcominit = Signal()
        txcomwake = Signal()
        txdlyen = Signal()
        txdlysreset = Signal()
        txdlysresetdone = Signal()
        txphalign = Signal()
        txphaligndone = Signal()
        txphinit = Signal()
        txphinitdone = Signal()
        gttxreset = Signal()

        self.specials += [
            MultiReg(self.txuserrdy, txuserrdy, "sata_tx"),
            MultiReg(self.txpd, txpd, "sata_tx"),
            MultiReg(self.txelecidle, txelecidle, "sata_tx"),
            MultiReg(self.gttxreset, gttxreset, "sata_tx")
        ]
        self.submodules += [
            _PulseSynchronizer(self.txcominit, "sys", txcominit, "sata_tx"),
            _PulseSynchronizer(self.txcomwake, "sys", txcomwake, "sata_tx"),
            _PulseSynchronizer(self.txdlyen, "sys", txdlyen, "sata_tx"),
            _PulseSynchronizer(self.txdlysreset, "sys", txdlysreset, "sata_tx"),
            _PulseSynchronizer(self.txphalign, "sys", txphalign, "sata_tx"),
            _PulseSynchronizer(self.txphinit, "sys", txphinit, "sata_tx"),
        ]

        # sata_tx clk --> sys clk
        txresetdone = Signal()
        txcomfinish = Signal()

        self.specials += [
            MultiReg(txresetdone, self.txresetdone, "sys"),
            MultiReg(txdlysresetdone, self.txdlysresetdone, "sys"),
            MultiReg(txphaligndone, self.txphaligndone, "sys"),
            MultiReg(txphinitdone, self.txphinitdone, "sys")
        ]

        self.submodules += [
            _PulseSynchronizer(txcomfinish, "sata_tx", self.txcomfinish, "sys")
        ]

        # sys clk --> sata_rx clk
        rxuserrdy = Signal()
        rxdlyreset = Signal()

        self.specials += [
            MultiReg(self.rxuserrdy, rxuserrdy, "sata_rx")
        ]

        self.submodules += [
            _PulseSynchronizer(self.rxdlyreset, "sys", rxdlyreset, "sata_rx")
        ]

        # sata_rx clk --> sys clk
        rxresetdone = Signal()
        rxcominitdet = Signal()
        rxcomwakedet = Signal()
        rxratedone = Signal()
        rxdlyresetdone = Signal()
        rxsyncdone = Signal()
        rxdisperr = Signal(data_width//8)
        rxnotintable = Signal(data_width//8)

        self.specials += [
            MultiReg(rxresetdone, self.rxresetdone, "sys"),
            MultiReg(rxcominitdet, self.rxcominitdet, "sys"),
            MultiReg(rxcomwakedet, self.rxcomwakedet, "sys"),
            MultiReg(rxdlyresetdone, self.rxdlyresetdone, "sys"),
            MultiReg(rxsyncdone, self.rxsyncdone, "sys"),
            MultiReg(rxdisperr, self.rxdisperr, "sys"),
            MultiReg(rxnotintable, self.rxnotintable, "sys")
        ]

        # QPLL ------------------------------------------------------------------------------------
        linerate_config = {
            "sata_gen1": 1.5e9,
            "sata_gen2": 3.0e9,
            "sata_gen3": 6.0e9
        }
        self.submodules.qpll = GTPQuadPLL(self.gtrefclk0, 150e6, linerate_config[revision])
        self.comb += [
            self.qpll.pd.eq(self.qpllpd),
            self.qpll.reset.eq(self.qpllreset),
            self.qplllock.eq(self.qpll.lock)
        ]

        # OOB clock (75MHz) ------------------------------------------------------------------------
        oobclk = Signal()
        self.specials += \
            Instance("FDPE",
                p_INIT=1, i_CE=1, i_PRE=0,
                i_C=self.gtrefclk0,
                i_D=~oobclk, o_Q=oobclk)

        # GTPE2_CHANNEL Instance -------------------------------------------------------------------
        tx_buffer_enable = False
        rx_buffer_enable = False
        rxphaligndone = Signal()
        gtp_params = dict(
            # Simulation-Only Attributes
            p_SIM_RECEIVER_DETECT_PASS               ="TRUE",
            p_SIM_TX_EIDLE_DRIVE_LEVEL               ="X",
            p_SIM_RESET_SPEEDUP                      ="FALSE",
            p_SIM_VERSION                            ="2.0",

            # RX Byte and Word Alignment Attributes
            p_ALIGN_COMMA_DOUBLE                     ="FALSE",
            p_ALIGN_COMMA_ENABLE                     =0b1111111111,
            p_ALIGN_COMMA_WORD                       =2 if data_width == 16 else 4,
            p_ALIGN_MCOMMA_DET                       ="TRUE",
            p_ALIGN_MCOMMA_VALUE                     =0b1010000011,
            p_ALIGN_PCOMMA_DET                       ="TRUE",
            p_ALIGN_PCOMMA_VALUE                     =0b0101111100,
            p_SHOW_REALIGN_COMMA                     ="TRUE",
            p_RXSLIDE_AUTO_WAIT                      =7,
            p_RXSLIDE_MODE                           ="OFF" if rx_buffer_enable else "PCS",
            p_RX_SIG_VALID_DLY                       =10,

            # RX 8B/10B Decoder Attributes
            p_RX_DISPERR_SEQ_MATCH                   ="TRUE",
            p_DEC_MCOMMA_DETECT                      ="TRUE",
            p_DEC_PCOMMA_DETECT                      ="TRUE",
            p_DEC_VALID_COMMA_ONLY                   ="TRUE",

            # RX Clock Correction Attributes
            p_CBCC_DATA_SOURCE_SEL                   ="DECODED",
            p_CLK_COR_SEQ_2_USE                      ="FALSE",
            p_CLK_COR_KEEP_IDLE                      ="FALSE",
            p_CLK_COR_MAX_LAT                        =9 if data_width == 16 else 20,
            p_CLK_COR_MIN_LAT                        =7 if data_width == 16 else 16,
            p_CLK_COR_PRECEDENCE                     ="TRUE",
            p_CLK_COR_REPEAT_WAIT                    =0,
            p_CLK_COR_SEQ_LEN                        =1,
            p_CLK_COR_SEQ_1_ENABLE                   =0b1111,
            p_CLK_COR_SEQ_1_1                        =0b0100000000,
            p_CLK_COR_SEQ_1_2                        =0b0000000000,
            p_CLK_COR_SEQ_1_3                        =0b0000000000,
            p_CLK_COR_SEQ_1_4                        =0b0000000000,
            p_CLK_CORRECT_USE                        ="FALSE",
            p_CLK_COR_SEQ_2_ENABLE                   =0b1111,
            p_CLK_COR_SEQ_2_1                        =0b0100000000,
            p_CLK_COR_SEQ_2_2                        =0b0000000000,
            p_CLK_COR_SEQ_2_3                        =0b0000000000,
            p_CLK_COR_SEQ_2_4                        =0b0000000000,

            # RX Channel Bonding Attributes
            p_CHAN_BOND_KEEP_ALIGN                   ="FALSE",
            p_CHAN_BOND_MAX_SKEW                     =1,
            p_CHAN_BOND_SEQ_LEN                      =1,
            p_CHAN_BOND_SEQ_1_1                      =0b0000000000,
            p_CHAN_BOND_SEQ_1_2                      =0b0000000000,
            p_CHAN_BOND_SEQ_1_3                      =0b0000000000,
            p_CHAN_BOND_SEQ_1_4                      =0b0000000000,
            p_CHAN_BOND_SEQ_1_ENABLE                 =0b1111,
            p_CHAN_BOND_SEQ_2_1                      =0b0000000000,
            p_CHAN_BOND_SEQ_2_2                      =0b0000000000,
            p_CHAN_BOND_SEQ_2_3                      =0b0000000000,
            p_CHAN_BOND_SEQ_2_4                      =0b0000000000,
            p_CHAN_BOND_SEQ_2_ENABLE                 =0b1111,
            p_CHAN_BOND_SEQ_2_USE                    ="FALSE",
            p_FTS_DESKEW_SEQ_ENABLE                  =0b1111,
            p_FTS_LANE_DESKEW_CFG                    =0b1111,
            p_FTS_LANE_DESKEW_EN                     ="FALSE",

            # RX Margin Analysis Attributes
            p_ES_CONTROL                             =0b000000,
            p_ES_ERRDET_EN                           ="FALSE",
            p_ES_EYE_SCAN_EN                         ="TRUE",
            p_ES_HORZ_OFFSET                         =0x000,
            p_ES_PMA_CFG                             =0b0000000000,
            p_ES_PRESCALE                            =0b00000,
            p_ES_QUALIFIER                           =0x00000000000000000000,
            p_ES_QUAL_MASK                           =0x00000000000000000000,
            p_ES_SDATA_MASK                          =0x00000000000000000000,
            p_ES_VERT_OFFSET                         =0b000000000,

            # FPGA RX Interface Attributes
            p_RX_DATA_WIDTH                          = 20 if data_width == 16 else 40,

            # PMA Attributes
            p_OUTREFCLK_SEL_INV                      =0b11,
            p_PMA_RSV                                =0x00000333,
            p_PMA_RSV2                               =0x00002040,
            p_PMA_RSV3                               =0b00,
            p_PMA_RSV4                               =0b0000,
            p_RX_BIAS_CFG                            =0b0000111100110011,
            p_DMONITOR_CFG                           =0x000A00,
            p_RX_CM_SEL                              =0b11,
            p_RX_CM_TRIM                             =0b1010,
            p_RX_DEBUG_CFG                           =0b00000000000000,
            p_RX_OS_CFG                              =0b0000010000000,
            p_TERM_RCAL_CFG                          =0b100001000010000,
            p_TERM_RCAL_OVRD                         =0b000,
            p_TST_RSV                                =0x00000000,
            p_RX_CLK25_DIV                           =6,
            p_TX_CLK25_DIV                           =6,
            p_UCODEER_CLR                            =0b0,

            # PCI Express Attributes
            p_PCS_PCIE_EN                            ="FALSE",

            # PCS Attributes
            p_PCS_RSVD_ATTR                          =0x000000000000,

            # RX Buffer Attributes
            p_RXBUF_ADDR_MODE                        ="FAST",
            p_RXBUF_EIDLE_HI_CNT                     =0b1000,
            p_RXBUF_EIDLE_LO_CNT                     =0b0000,
            p_RXBUF_EN                               ="TRUE" if rx_buffer_enable else "FALSE",
            p_RX_BUFFER_CFG                          =0b000000,
            p_RXBUF_RESET_ON_CB_CHANGE               ="TRUE",
            p_RXBUF_RESET_ON_COMMAALIGN              ="FALSE",
            p_RXBUF_RESET_ON_EIDLE                   ="FALSE",
            p_RXBUF_RESET_ON_RATE_CHANGE             ="TRUE",
            p_RXBUFRESET_TIME                        =0b00001,
            p_RXBUF_THRESH_OVFLW                     =61,
            p_RXBUF_THRESH_OVRD                      ="FALSE",
            p_RXBUF_THRESH_UNDFLW                    =4,
            p_RXDLY_CFG                              =0x001F,
            p_RXDLY_LCFG                             =0x030,
            p_RXDLY_TAP_CFG                          =0x0000,
            p_RXPH_CFG                               =0xC00002,
            p_RXPHDLY_CFG                            =0x084020,
            p_RXPH_MONITOR_SEL                       =0b00000,
            p_RX_XCLK_SEL                            ="RXREC" if rx_buffer_enable else "RXUSR",
            p_RX_DDI_SEL                             =0b000000,
            p_RX_DEFER_RESET_BUF_EN                  ="TRUE",

            # CDR Attributes
            p_RXCDR_CFG                              =rxcdr_cfg,
            p_RXCDR_FR_RESET_ON_EIDLE                =0b0,
            p_RXCDR_HOLD_DURING_EIDLE                =0b0,
            p_RXCDR_PH_RESET_ON_EIDLE                =0b0,
            p_RXCDR_LOCK_CFG                         =0b001001,

            # RX Initialization and Reset Attributes
            p_RXCDRFREQRESET_TIME                    =0b00001,
            p_RXCDRPHRESET_TIME                      =0b00001,
            p_RXISCANRESET_TIME                      =0b00001,
            p_RXPCSRESET_TIME                        =0b00001,
            p_RXPMARESET_TIME                        =0b00011,

            # RX OOB Signaling Attributes
            p_RXOOB_CFG                              =0b0000110,

            # RX Gearbox Attributes
            p_RXGEARBOX_EN                           ="FALSE",
            p_GEARBOX_MODE                           =0b000,

            # PRBS Detection Attribute
            p_RXPRBS_ERR_LOOPBACK                    =0b0,

            # Power-Down Attributes
            p_PD_TRANS_TIME_FROM_P2                  =0x03c,
            p_PD_TRANS_TIME_NONE_P2                  =0x3c,
            p_PD_TRANS_TIME_TO_P2                    =0x64,

            # RX OOB Signaling Attributes
            p_SAS_MAX_COM                            =64,
            p_SAS_MIN_COM                            =36,
            p_SATA_BURST_SEQ_LEN                     =0b0101,
            p_SATA_BURST_VAL                         =0b111,
            p_SATA_EIDLE_VAL                         =0b111,
            p_SATA_MAX_BURST                         =8,
            p_SATA_MAX_INIT                          =21,
            p_SATA_MAX_WAKE                          =7,
            p_SATA_MIN_BURST                         =4,
            p_SATA_MIN_INIT                          =12,
            p_SATA_MIN_WAKE                          =4,

            # RX Fabric Clock Output Control Attributes
            p_TRANS_TIME_RATE                        =0x0E,

            # TX Buffer Attributes
            p_TXBUF_EN                               ="TRUE" if tx_buffer_enable else "FALSE",
            p_TXBUF_RESET_ON_RATE_CHANGE             ="TRUE",
            p_TXDLY_CFG                              =0x001F,
            p_TXDLY_LCFG                             =0x030,
            p_TXDLY_TAP_CFG                          =0x0000,
            p_TXPH_CFG                               =0x0780,
            p_TXPHDLY_CFG                            =0x084020,
            p_TXPH_MONITOR_SEL                       =0b00000,
            p_TX_XCLK_SEL                            ="TXOUT" if tx_buffer_enable else "TXUSR",

            # FPGA TX Interface Attributes
            p_TX_DATA_WIDTH                          = 20 if data_width == 16 else 40,

            # TX Configurable Driver Attributes
            p_TX_DEEMPH0                             =0b000000,
            p_TX_DEEMPH1                             =0b000000,
            p_TX_EIDLE_ASSERT_DELAY                  =0b110,
            p_TX_EIDLE_DEASSERT_DELAY                =0b100,
            p_TX_LOOPBACK_DRIVE_HIZ                  ="FALSE",
            p_TX_MAINCURSOR_SEL                      =0b0,
            p_TX_DRIVE_MODE                          ="DIRECT",
            p_TX_MARGIN_FULL_0                       =0b1001110,
            p_TX_MARGIN_FULL_1                       =0b1001001,
            p_TX_MARGIN_FULL_2                       =0b1000101,
            p_TX_MARGIN_FULL_3                       =0b1000010,
            p_TX_MARGIN_FULL_4                       =0b1000000,
            p_TX_MARGIN_LOW_0                        =0b1000110,
            p_TX_MARGIN_LOW_1                        =0b1000100,
            p_TX_MARGIN_LOW_2                        =0b1000010,
            p_TX_MARGIN_LOW_3                        =0b1000000,
            p_TX_MARGIN_LOW_4                        =0b1000000,

            # TX Gearbox Attributes
            p_TXGEARBOX_EN                           ="FALSE",

            # TX Initialization and Reset Attributes
            p_TXPCSRESET_TIME                        =0b00001,
            p_TXPMARESET_TIME                        =0b00001,

            # TX Receiver Detection Attributes
            p_TX_RXDETECT_CFG                        =0x1832,
            p_TX_RXDETECT_REF                        =0b100,

            # JTAG Attributes
            p_ACJTAG_DEBUG_MODE                      =0b0,
            p_ACJTAG_MODE                            =0b0,
            p_ACJTAG_RESET                           =0b0,

            # CDR Attributes
            p_CFOK_CFG                               =0x49000040E80,
            p_CFOK_CFG2                              =0b0100000,
            p_CFOK_CFG3                              =0b0100000,
            p_CFOK_CFG4                              =0b0,
            p_CFOK_CFG5                              =0x0,
            p_CFOK_CFG6                              =0b0000,
            p_RXOSCALRESET_TIME                      =0b00011,
            p_RXOSCALRESET_TIMEOUT                   =0b00000,

            # PMA Attributes
            p_CLK_COMMON_SWING                       =0b0,
            p_RX_CLKMUX_EN                           =0b1,
            p_TX_CLKMUX_EN                           =0b1,
            p_ES_CLK_PHASE_SEL                       =0b0,
            p_USE_PCS_CLK_PHASE_SEL                  =0b0,
            p_PMA_RSV6                               =0b0,
            p_PMA_RSV7                               =0b0,

            # TX Configuration Driver Attributes
            p_TX_PREDRIVER_MODE                      =0b0,
            p_PMA_RSV5                               =0b0,
            p_SATA_PLL_CFG                           ="VCO_3000MHZ",

            # RX Fabric Clock Output Control Attributes
            p_RXOUT_DIV                              =rxout_div,

            # TX Fabric Clock Output Control Attributes
            p_TXOUT_DIV                              =txout_div,

            # RX Phase Interpolator Attributes
            p_RXPI_CFG0                              =0b000,
            p_RXPI_CFG1                              =0b1,
            p_RXPI_CFG2                              =0b1,

            # RX Equalizer Attributes
            p_ADAPT_CFG0                             =0x00000,
            p_RXLPMRESET_TIME                        =0b0001111,
            p_RXLPM_BIAS_STARTUP_DISABLE             =0b0,
            p_RXLPM_CFG                              =0b0110,
            p_RXLPM_CFG1                             =0b0,
            p_RXLPM_CM_CFG                           =0b0,
            p_RXLPM_GC_CFG                           =0b111100010,
            p_RXLPM_GC_CFG2                          =0b001,
            p_RXLPM_HF_CFG                           =0b00001111110000,
            p_RXLPM_HF_CFG2                          =0b01010,
            p_RXLPM_HF_CFG3                          =0b0000,
            p_RXLPM_HOLD_DURING_EIDLE                =0b0,
            p_RXLPM_INCM_CFG                         =0b1,
            p_RXLPM_IPCM_CFG                         =0b0,
            p_RXLPM_LF_CFG                           =0b000000001111110000,
            p_RXLPM_LF_CFG2                          =0b01010,
            p_RXLPM_OSINT_CFG                        =0b100,

            # TX Phase Interpolator PPM Controller Attributes
            p_TXPI_CFG0                              =0b00,
            p_TXPI_CFG1                              =0b00,
            p_TXPI_CFG2                              =0b00,
            p_TXPI_CFG3                              =0b0,
            p_TXPI_CFG4                              =0b0,
            p_TXPI_CFG5                              =0b000,
            p_TXPI_GREY_SEL                          =0b0,
            p_TXPI_INVSTROBE_SEL                     =0b0,
            p_TXPI_PPMCLK_SEL                        ="TXUSRCLK2",
            p_TXPI_PPM_CFG                           =0x00,
            p_TXPI_SYNFREQ_PPM                       =0b001,

            # LOOPBACK Attributes
            p_LOOPBACK_CFG                           =0b0,
            p_PMA_LOOPBACK_CFG                       =0b0,

            # RX OOB Signalling Attributes
            p_RXOOB_CLK_CFG                          ="PMA",

            # TX OOB Signalling Attributes
            p_TXOOB_CFG                              =0b0,

            # RX Buffer Attributes
            p_RXSYNC_MULTILANE                       =0b0,
            p_RXSYNC_OVRD                            =0b0,
            p_RXSYNC_SKIP_DA                         =0b0,

            # TX Buffer Attributes
            p_TXSYNC_MULTILANE                       =0b0,
            p_TXSYNC_OVRD                            =0b1,
            p_TXSYNC_SKIP_DA                         =0b0
        )
        gtp_params.update(
            # CPLL Ports
            i_GTRSVD                         =0b0000000000000000,
            i_PCSRSVDIN                      =0b0000000000000000,
            i_TSTIN                          =0b11111111111111111111,

            # Channel - DRP Ports
            i_DRPADDR                        =0,
            i_DRPCLK                         =0,
            i_DRPDI                          =0,
            #o_DRPDO                          =,
            i_DRPEN                          =0,
            #o_DRPRDY                         =,
            i_DRPWE                          =0,

            # Clocking Ports
            i_RXSYSCLKSEL                    =0b00,
            i_TXSYSCLKSEL                    =0b00,

            # FPGA TX Interface Datapath Configuration
            i_TX8B10BEN                      =1,

            # GTPE2_CHANNEL Clocking Ports
            i_PLL0CLK                        =self.qpll.clk,
            i_PLL0REFCLK                     =self.qpll.refclk,
            i_PLL1CLK                        =0,
            i_PLL1REFCLK                     =0,

            # Loopback Ports
            i_LOOPBACK                       =0,

            # PCI Express Ports
            #o_PHYSTATUS                      =,
            i_RXRATE                         =0b000,
            #o_RXVALID                        =,

            # PMA Reserved Ports
            i_PMARSVDIN3                     =0b0,
            i_PMARSVDIN4                     =0b0,

            # Power-Down Ports
            i_RXPD                           =Replicate(self.rxpd, 2),
            i_TXPD                           =Replicate(txpd, 2),

            # RX 8B/10B Decoder Ports
            i_SETERRSTATUS                   =0,

            # RX Initialization and Reset Ports
            i_EYESCANRESET                   =0,
            i_RXUSERRDY                      =rxuserrdy,

            # RX Margin Analysis Ports
            #o_EYESCANDATAERROR               =,
            i_EYESCANMODE                    =0,
            i_EYESCANTRIGGER                 =0,

            # Receive Ports
            i_CLKRSVD0                       =oobclk,
            i_CLKRSVD1                       =oobclk,
            i_DMONFIFORESET                  =0,
            i_DMONITORCLK                    =0,
            #o_RXPMARESETDONE                 =, FIXME
            i_SIGVALIDCLK                    =0,

            # Receive Ports - CDR Ports
            i_RXCDRFREQRESET                 =0,
            i_RXCDRHOLD                      =self.rx_cdrhold,
            #o_RXCDRLOCK                      =,
            i_RXCDROVRDEN                    =0,
            i_RXCDRRESET                     =0,
            i_RXCDRRESETRSV                  =0,
            i_RXOSCALRESET                   =0,
            i_RXOSINTCFG                     =0b0010,
            #o_RXOSINTDONE                    =,
            i_RXOSINTHOLD                    =0,
            i_RXOSINTOVRDEN                  =0,
            i_RXOSINTPD                      =0,
            #o_RXOSINTSTARTED                 =,
            i_RXOSINTSTROBE                  =0,
            #o_RXOSINTSTROBESTARTED           =,
            i_RXOSINTTESTOVRDEN              =0,

            # Receive Ports - Clock Correction Ports
            #o_RXCLKCORCNT                    =,

            # Receive Ports - FPGA RX Interface Datapath Configuration
            i_RX8B10BEN                      =1,

            # Receive Ports - FPGA RX Interface Ports
            o_RXDATA                         =self.rxdata,
            i_RXUSRCLK                       =self.rxusrclk,
            i_RXUSRCLK2                      =self.rxusrclk2,

            # Receive Ports - Pattern Checker Ports
            #o_RXPRBSERR                      =,
            i_RXPRBSSEL                      =0b000,

            # Receive Ports - Pattern Checker ports
            i_RXPRBSCNTRESET                 =0,

            # Receive Ports - RX 8B/10B Decoder Ports
            #o_RXCHARISCOMMA                  =,
            o_RXCHARISK                      =self.rxcharisk,
            o_RXDISPERR                      =rxdisperr,
            o_RXNOTINTABLE                   =rxnotintable,

            # Receive Ports - RX AFE Ports
            i_GTPRXN                         =pads.rxn,
            i_GTPRXP                         =pads.rxp,
            i_PMARSVDIN2                     =0b0,
            #o_PMARSVDOUT0                    =,
            #o_PMARSVDOUT1                    =,

            # Receive Ports - RX Buffer Bypass Ports
            i_RXBUFRESET                     =0,
            #o_RXBUFSTATUS                    =,
            i_RXDDIEN                        =0 if rx_buffer_enable else 1,
            i_RXDLYBYPASS                    =1 if rx_buffer_enable else 0,
            i_RXDLYEN                        =0,
            i_RXDLYOVRDEN                    =0,
            i_RXDLYSRESET                    =rxdlyreset,
            o_RXDLYSRESETDONE                =rxdlyresetdone,
            i_RXPHALIGN                      =0,
            o_RXPHALIGNDONE                  =rxphaligndone,
            i_RXPHALIGNEN                    =0,
            i_RXPHDLYPD                      =0,
            i_RXPHDLYRESET                   =0,
            #o_RXPHMONITOR                    =,
            i_RXPHOVRDEN                     =0,
            #o_RXPHSLIPMONITOR                =,
            #o_RXSTATUS                       =,
            i_RXSYNCALLIN                    =rxphaligndone,
            o_RXSYNCDONE                     =rxsyncdone,
            i_RXSYNCIN                       =0,
            i_RXSYNCMODE                     =0 if rx_buffer_enable else 1,
            #o_RXSYNCOUT                      =,

            # Receive Ports - RX Byte and Word Alignment Ports
            #o_RXBYTEISALIGNED                =,
            #o_RXBYTEREALIGN                  =,
            #o_RXCOMMADET                     =,
            i_RXCOMMADETEN                   =1,
            i_RXMCOMMAALIGNEN                =1,
            i_RXPCOMMAALIGNEN                =1,
            i_RXSLIDE                        =0,

            # Receive Ports - RX Channel Bonding Ports
            #o_RXCHANBONDSEQ                  =,
            i_RXCHBONDEN                     =0,
            i_RXCHBONDI                      =0b0000,
            i_RXCHBONDLEVEL                  =0,
            i_RXCHBONDMASTER                 =0,
            #o_RXCHBONDO                      =,
            i_RXCHBONDSLAVE                  =0,

            # Receive Ports - RX Channel Bonding Ports
            #o_RXCHANISALIGNED                =,
            #o_RXCHANREALIGN                  =,

            # Receive Ports - RX Decision Feedback Equalizer
            #o_DMONITOROUT                    =,
            i_RXADAPTSELTEST                 =0,
            i_RXDFEXYDEN                     =0,
            i_RXOSINTEN                      =0b1,
            i_RXOSINTID0                     =0,
            i_RXOSINTNTRLEN                  =0,
            #o_RXOSINTSTROBEDONE              =,

            # Receive Ports - RX Driver,OOB signalling,Coupling and Eq.,CDR
            i_RXLPMLFOVRDEN                  =0,
            i_RXLPMOSINTNTRLEN               =0,

            # Receive Ports - RX Equalizer Ports
            i_RXLPMHFHOLD                    =0,
            i_RXLPMHFOVRDEN                  =0,
            i_RXLPMLFHOLD                    =0,
            i_RXOSHOLD                       =0,
            i_RXOSOVRDEN                     =0,

            # Receive Ports - RX Fabric ClocK Output Control Ports
            #o_RXRATEDONE                     =,

            # Receive Ports - RX Fabric Clock Output Control Ports
            i_RXRATEMODE                     =0b0,

            # Receive Ports - RX Fabric Output Control Ports
            o_RXOUTCLK                       =self.rxoutclk,
            #o_RXOUTCLKFABRIC                 =,
            #o_RXOUTCLKPCS                    =,
            i_RXOUTCLKSEL                    =0b010,

            # Receive Ports - RX Gearbox Ports
            #o_RXDATAVALID                    =,
            #o_RXHEADER                       =,
            #o_RXHEADERVALID                  =,
            #o_RXSTARTOFSEQ                   =,

            # Receive Ports - RX Gearbox Ports
            i_RXGEARBOXSLIP                  =0,

            # Receive Ports - RX Initialization and Reset Ports
            i_GTRXRESET                      =self.gtrxreset,
            i_RXOOBRESET                     =0,
            i_RXPCSRESET                     =0,
            i_RXPMARESET                     =0,

            # Receive Ports - RX OOB Signaling ports
            #o_RXCOMSASDET                    =,
            o_RXCOMWAKEDET                   =rxcomwakedet,

            # Receive Ports - RX OOB Signaling ports
            o_RXCOMINITDET                   =rxcominitdet,

            # Receive Ports - RX OOB signalling Ports
            #o_RXELECIDLE                     =,
            i_RXELECIDLEMODE                 =0b00,

            # Receive Ports - RX Polarity Control Ports
            i_RXPOLARITY                     =0,

            # Receive Ports -RX Initialization and Reset Ports
            o_RXRESETDONE                    =rxresetdone,

            # TX Buffer Bypass Ports
            i_TXPHDLYTSTCLK                  =0,

            # TX Configurable Driver Ports
            i_TXPOSTCURSOR                   =0b00000,
            i_TXPOSTCURSORINV                =0,
            i_TXPRECURSOR                    =0b00000,
            i_TXPRECURSORINV                 =0,

            # TX Fabric Clock Output Control Ports
            i_TXRATEMODE                     =0,

            # TX Initialization and Reset Ports
            i_CFGRESET                       =0,
            i_GTTXRESET                      =gttxreset,
            #o_PCSRSVDOUT                     =,
            i_TXUSERRDY                      =txuserrdy,

            # TX Phase Interpolator PPM Controller Ports
            i_TXPIPPMEN                      =0,
            i_TXPIPPMOVRDEN                  =0,
            i_TXPIPPMPD                      =0,
            i_TXPIPPMSEL                     =1,
            i_TXPIPPMSTEPSIZE                =0,

            # Transceiver Reset Mode Operation
            i_GTRESETSEL                     =0,
            i_RESETOVRD                      =0,

            # Transmit Ports
            #o_TXPMARESETDONE                 =,

            # Transmit Ports - Configurable Driver Ports
            i_PMARSVDIN0                     =0b0,
            i_PMARSVDIN1                     =0b0,

            # Transmit Ports - FPGA TX Interface Ports
            i_TXDATA                         =self.txdata,
            i_TXUSRCLK                       =self.txusrclk,
            i_TXUSRCLK2                      =self.txusrclk2,

            # Transmit Ports - PCI Express Ports
            i_TXELECIDLE                     =txelecidle,
            i_TXMARGIN                       =0b000,
            i_TXRATE                         =0b000,
            i_TXSWING                        =0,

            # Transmit Ports - Pattern Generator Ports
            i_TXPRBSFORCEERR                 =0,

            # Transmit Ports - TX 8B/10B Encoder Ports
            i_TX8B10BBYPASS                  =0,
            i_TXCHARDISPMODE                 =0,
            i_TXCHARDISPVAL                  =0,
            i_TXCHARISK                      =self.txcharisk,

            # Transmit Ports - TX Buffer Bypass Ports
            i_TXDLYBYPASS                    =0,
            i_TXDLYEN                        =txdlyen,
            i_TXDLYHOLD                      =0,
            i_TXDLYOVRDEN                    =0,
            i_TXDLYSRESET                    =txdlysreset,
            o_TXDLYSRESETDONE                =txdlysresetdone,
            i_TXDLYUPDOWN                    =0,
            i_TXPHALIGN                      =txphalign,
            o_TXPHALIGNDONE                  =txphaligndone,
            i_TXPHALIGNEN                    =1,
            i_TXPHDLYPD                      =0,
            i_TXPHDLYRESET                   =0,
            i_TXPHINIT                       =txphinit,
            o_TXPHINITDONE                   =txphinitdone,
            i_TXPHOVRDEN                     =0,

            # Transmit Ports - TX Buffer Ports
            #o_TXBUFSTATUS                    =,

            # Transmit Ports - TX Buffer and Phase Alignment Ports
            i_TXSYNCALLIN                    =0,
            #o_TXSYNCDONE                     =,
            #i_TXSYNCIN                       =0,
            #i_TXSYNCMODE                     =0,
            #o_TXSYNCOUT                      =,

            # Transmit Ports - TX Configurable Driver Ports
            o_GTPTXN                         =pads.txn,
            o_GTPTXP                         =pads.txp,
            i_TXBUFDIFFCTRL                  =0b100,
            i_TXDEEMPH                       =0,
            i_TXDIFFCTRL                     =0b1000,
            i_TXDIFFPD                       =0,
            i_TXINHIBIT                      =0,
            i_TXMAINCURSOR                   =0b0000000,
            i_TXPISOPD                       =0,

            # Transmit Ports - TX Fabric Clock Output Control Ports
            o_TXOUTCLK                       =self.txoutclk,
            #o_TXOUTCLKFABRIC                 =,
            #o_TXOUTCLKPCS                    =,
            i_TXOUTCLKSEL                    =0b010 if tx_buffer_enable else 0b011,
            #o_TXRATEDONE                     =,

            # Transmit Ports - TX Gearbox Ports
            #o_TXGEARBOXREADY                 =,
            i_TXHEADER                       =0b000,
            i_TXSEQUENCE                     =0b0000000,
            i_TXSTARTSEQ                     =0,

            # Transmit Ports - TX Initialization and Reset Ports
            i_TXPCSRESET                     =0,
            i_TXPMARESET                     =0,
            o_TXRESETDONE                    =txresetdone,

            # Transmit Ports - TX OOB signaling Ports
            o_TXCOMFINISH                    =txcomfinish,
            i_TXCOMINIT                      =txcominit,
            i_TXCOMSAS                       =0,
            i_TXCOMWAKE                      =txcomwake,
            i_TXPDELECIDLEMODE               =0,

            # Transmit Ports - TX Polarity Control Ports
            i_TXPOLARITY                     =0,

            # Transmit Ports - TX Receiver Detection Ports
            i_TXDETECTRX                     =0,

            # Transmit Ports - pattern Generator Ports
            i_TXPRBSSEL                      =0b000,
        )
        self.specials += Instance("GTPE2_CHANNEL", **gtp_params)
