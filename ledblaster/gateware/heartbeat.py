from migen import *

class Heartbeat(Module):
    """A cute LED fader for hearbeat indication."""

    bpm = 80

    def __init__(self, clk_freq):
        period = clk_freq * (self.bpm / 60.0)
        qrs_period = clk_freq * (80e-3)
        t_period = clk_freq * (160e-3)
        qt_period = clk_freq * (440e-3)
        st_period = qt_period - (t_period + qrs_period)

        counter = Signal(max=int(period))
        self.sync += [
            If(counter == 0,
               counter.eq(int(period))
            ).Else(
                counter.eq(counter - 1)
            )
        ]

        in_qrs = Signal()
        in_t = Signal()

        self.comb += [
            in_qrs.eq(counter < int(qrs_period)),
            in_t.eq((counter > int(qrs_period + st_period)) & (counter < int(qt_period))),
        ]

        self.out = Signal()
        self.comb += [
            self.out.eq(in_qrs | in_t),
        ]
