from fractions import Fraction
import logging
import math

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from litedram.modules import SDRAMModule
from litedram.modules import _TechnologyTimings
from litedram.modules import _SpeedgradeTimings

from ledblaster.gateware.heartbeat import Heartbeat
from ledblaster.gateware import led

logger = logging.getLogger(__name__)

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys_ps = ClockDomain()

        self.reset = Signal()

        f0 = 25*1000000
        clk25 = platform.request("clk25")
        clk25a = Signal()
        self.specials += Instance("IBUFG", i_I=clk25, o_O=clk25a)
        clk25b = Signal()
        self.specials += Instance("BUFIO2", p_DIVIDE=1,
                                  p_DIVIDE_BYPASS="TRUE", p_I_INVERT="FALSE",
                                  i_I=clk25a, o_DIVCLK=clk25b)
        f = Fraction(int(sys_clk_freq), int(f0))
        n, m = f.denominator, f.numerator
        assert f0/n*m == sys_clk_freq
        p = 8
        pll_lckd = Signal()
        pll_fb = Signal()
        pll_sys = Signal()
        pll_sys_ps = Signal()
        self.specials.pll = [
            Instance("PLL_ADV",
                p_SIM_DEVICE="SPARTAN6",
                p_BANDWIDTH="OPTIMIZED", p_COMPENSATION="INTERNAL",
                p_REF_JITTER=.01, p_CLK_FEEDBACK="CLKFBOUT",
                i_DADDR=0, i_DCLK=0, i_DEN=0, i_DI=0, i_DWE=0, i_RST=0, i_REL=0,
                p_DIVCLK_DIVIDE=1, p_CLKFBOUT_MULT=m*p//n, p_CLKFBOUT_PHASE=0.,
                i_CLKIN1=clk25b, i_CLKIN2=0, i_CLKINSEL=1,
                p_CLKIN1_PERIOD=1e9/f0, p_CLKIN2_PERIOD=0.,
                i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb, o_LOCKED=pll_lckd,
                o_CLKOUT0=pll_sys, p_CLKOUT0_DUTY_CYCLE=.5,
                p_CLKOUT0_PHASE=0., p_CLKOUT0_DIVIDE=p//1,
                o_CLKOUT1=pll_sys_ps, p_CLKOUT1_DUTY_CYCLE=.5,
                p_CLKOUT1_PHASE=270., p_CLKOUT1_DIVIDE=p//1),
            Instance("BUFG", i_I=pll_sys, o_O=self.cd_sys.clk),
            Instance("BUFG", i_I=pll_sys_ps, o_O=self.cd_sys_ps.clk),
        ]
        reset = self.reset
        self.clock_domains.cd_por = ClockDomain()
        por = Signal(max=1 << 11, reset=(1 << 11) - 1)
        self.sync.por += If(por != 0, por.eq(por - 1))
        self.comb += self.cd_por.clk.eq(self.cd_sys.clk)
        self.specials += AsyncResetSynchronizer(self.cd_por, reset)
        self.specials += AsyncResetSynchronizer(self.cd_sys, ~pll_lckd | (por > 0))
        platform.add_period_constraint(self.cd_sys.clk, 1e9/sys_clk_freq)
        #platform.add_period_constraint(self.cd_sys_ps.clk, 1e9/sys_clk_freq)

        # sdram_clock
        self.specials += Instance("ODDR2",
            p_DDR_ALIGNMENT="NONE", p_INIT=0, p_SRTYPE="SYNC",
            i_D0=0, i_D1=1, i_S=0, i_R=0, i_CE=1,
            i_C0=self.cd_sys.clk, i_C1=~self.cd_sys.clk,
            o_Q=platform.request("sdram_clock", 0))


class M12L64322A(SDRAMModule):
    memtype = "SDR"
    # geometry
    nbanks = 4
    nrows  = 2048
    ncols  = 256
    # timings
    technology_timings = _TechnologyTimings(tREFI=64e6/4096, tWTR=(2, None), tCCD=(1, None), tRRD=(None, 10))
    speedgrade_timings = {"default": _SpeedgradeTimings(tRP=15, tRCD=15, tWR=15, tRFC=55, tFAW=None, tRAS=40)}



class Target(Module):
    def __init__(self, platform):
        sys_clk_freq = int(75e6)
        self.submodules.cfg = _CRG(platform, sys_clk_freq)

        # Blink the LED
        self.submodules.heartbeat = Heartbeat(sys_clk_freq)
        self.comb += platform.request('user_led').eq(~self.heartbeat.out)

        self.submodules.blinker = led.Controller(platform)
