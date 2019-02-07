import logging
import math

from migen import *


logger = logging.getLogger(__name__)


class Gamma(Module):
    """Combinatorial look-up table for gamma correction."""
    def __init__(self, source, destination, gamma=5):
        """
        :param source: Source signal to gamma correct.
        :param destionation: Output gamma-corrected signal.
        :param gamma: Gamma correction factor (5 seems accurate for LED panels).
        """
        srcn = source.nbits
        dstn = destination.nbits
        cases = {
            'default': destination.eq(0),
        }
        for i in range(0, 2**srcn):

            in_f = float(i) / ((2**srcn) - 1)
            gamma_f = math.pow(in_f, gamma)
            ov = gamma_f * ((2**dstn) - 1)

            cases[i] = destination.eq(int(ov))
            logger.debug("Gamma {:02x} -> {:03x}".format(i, int(ov)))

        self.comb += Case(source, cases)



class BankMachine(Module):
    """
    A color emitting module for each LED panel sub-panel.

    A subpanel is an individually controllable set of R,G,B values for a given
    X, Y coordinate. The amount of subpanels depends on the panel height and
    scan factor. For example, a 32-high 1/16th scan panel has two subpanels.
    """
    def __init__(self, r, g, b, x, y, plane):
        """
        :param r: output R signal
        :param g: output G signal
        :param b: output B signal
        :param x: current X coordinate within panel
        :param y: current Y coordinate within panel (not subpanel!)
        :param plane: current bit plane
        """
        color_r = Signal(8)
        color_r_g = Signal(12)
        self.submodules += Gamma(color_r, color_r_g)
        color_g = Signal(8)
        color_g_g = Signal(12)
        self.submodules += Gamma(color_g, color_g_g)
        color_b = Signal(8)
        color_b_g = Signal(12)
        self.submodules += Gamma(color_b, color_b_g)

        self.comb += [
            color_r.eq(x<<2),
            color_g.eq(0),
            color_b.eq(y<<3),
        ]


        self.comb += [
            r.eq((color_r_g >> plane) & 1),
            g.eq((color_g_g >> plane) & 1),
            b.eq((color_b_g >> plane) & 1),
        ]


class Controller(Module):
    def __init__(self, platform, chain_length=64):
        ctrl = platform.request('hub75_control')
        #nbanks = int(2 ** ctrl.bank.nbits)
        nbanks = 16
        logger.info('Banks: {}'.format(nbanks))

        # Register all control outputs.
        ctrl_bank = Signal(max=nbanks)
        ctrl_oe = Signal()
        ctrl_clk = Signal()
        ctrl_stb = Signal()

        self.sync += [
            ctrl.bank.eq(ctrl_bank),
            ctrl.oe.eq(ctrl_oe),
            ctrl.stb.eq(ctrl_stb),
            ctrl.clk.eq(ctrl_clk),
        ]


        pixel_counter = Signal(max=chain_length)

        clk_delay = 4
        clk_delay_counter = Signal(max=clk_delay)

        self.submodules.fsm = FSM(reset_state='IDLE')
        self.fsm.act('IDLE',
            NextValue(pixel_counter, 0),
            NextValue(clk_delay_counter, clk_delay-1),
            NextState('DATA'),
            NextValue(ctrl_clk, 0),
        )

        self.fsm.act('DATA',
            If(clk_delay_counter == 0,
                NextValue(clk_delay_counter, clk_delay-1),
                If(ctrl_clk == 1,
                    If(pixel_counter == chain_length - 1,
                        NextValue(pixel_counter, 0),
                        NextState('LATCH_PRE'),
                    ).Else(
                        NextValue(pixel_counter, pixel_counter + 1),
                    ),
                ),
                NextValue(ctrl_clk, ~ctrl_clk),
            ).Else(
                NextValue(clk_delay_counter, clk_delay_counter-1),
            )
        )

        clk_freq = (75e6)
        logger.info('Clock frequency (MHz): {}'.format(clk_freq/1e6))
        io_freq = (75e6)/(2*clk_delay)
        logger.info('IO frequency (MHz): {}'.format(io_freq/1e6))
        transfer_time = (chain_length + 1)/io_freq
        logger.info('Transfer time (s): {:.3e}'.format(transfer_time))

        transfer_time_clk_cycles = int(transfer_time/(1.0/clk_freq))
        logger.info('Transfer time (clk cycles): {}'.format(transfer_time_clk_cycles))

        planes = 12
        shortest_timeslot = 3
        plane = Signal(max=planes, reset=planes-1)
        wait = [2**(i + shortest_timeslot) for i in range(planes)]

        for i, w in enumerate(wait):
            t = w / (1.0/clk_freq)
            logger.debug('  Timeslot {:2d}, OE (s): {:.3e}, (cycles): {}'.format(i, t, w))

        total = (sum(wait)/clk_freq + transfer_time) * nbanks
        logger.info('Total time (s): {:.3e}'.format(total))
        logger.info('Framerate: (Hz): {:.3f} '.format(1.0/total))


        wait_counter = Signal(max=max(wait))
        wait_value = Signal(max=max(wait))
        wait_values = {
            'default': wait_value.eq(0),
        }
        for i, w in enumerate(wait):
            wait_values[i] = wait_value.eq(w-1)
        self.comb += Case(plane, wait_values)

        self.fsm.act('LATCH_PRE',
            If(clk_delay_counter == 0,
                NextState('LATCH'),
                NextValue(clk_delay_counter, clk_delay-1),
            ).Else(
                NextValue(clk_delay_counter, clk_delay_counter-1),
            )
        )
        self.fsm.act('LATCH',
            If(clk_delay_counter == 0,
                NextState('LATCH_POST'),
                NextValue(clk_delay_counter, clk_delay-1),
            ).Else(
                NextValue(clk_delay_counter, clk_delay_counter-1),
            )
        )
        self.fsm.act('LATCH_POST',
            If(clk_delay_counter == 0,
                NextState('WAIT'),
                NextValue(wait_counter, wait_value),
            ).Else(
                NextValue(clk_delay_counter, clk_delay_counter-1),
            )
        )

        self.fsm.act('WAIT',
            If(wait_counter == 0,
                NextState('IDLE'),
                If(plane == 0,
                    NextValue(ctrl_bank, ctrl_bank + 1),
                    NextValue(plane, planes-1),
                ).Else(
                    NextValue(plane, plane-1),
                ),
            ).Else(
                NextValue(wait_counter, wait_counter - 1),
            ),
        )

        self.comb += [
            # OE active low
            ctrl_oe.eq(~self.fsm.ongoing('WAIT')),
            ctrl_stb.eq(self.fsm.ongoing('LATCH')),
        ]


        j1 = platform.request('hub75_chain')
        j1_r = Signal(j1.r.nbits)
        j1_g = Signal(j1.g.nbits)
        j1_b = Signal(j1.b.nbits)
        self.sync += [
            j1.r.eq(j1_r),
            j1.g.eq(j1_g),
            j1.b.eq(j1_b),
        ]
        self.submodules.ba = BankMachine(r=j1_r[0], g=j1_g[0], b=j1_b[0],
                x=pixel_counter, y=ctrl_bank, plane=plane)
        self.submodules.bb = BankMachine(r=j1_r[1], g=j1_g[1], b=j1_b[1],
                x=pixel_counter, y=ctrl_bank+16, plane=plane)

