# PCB Design Guidelines (Internal Engineering Reference)

## Clearance Rules

The minimum copper-to-copper clearance for this design class is 0.2000mm
(200 microns), as defined by the "Default" netclass. Reducing clearance
below this value increases the risk of solder bridging during reflow and
raises the probability of dielectric breakdown at elevated humidity. Pads
and tracks placed closer than the configured clearance must be flagged and
either rerouted, the footprint repositioned, or the local design rule
explicitly (and knowingly) relaxed via a documented exception.

## Minimum Track Width

The minimum track width for signal-class nets on this stackup is 0.1500mm.
Tracks narrower than this are difficult to reliably reproduce during
fabrication (etching tolerance) and can suffer excessive resistive losses
and localized heating on nets carrying more than a few hundred milliamps.
For high-speed digital signals (e.g. SPI clock lines), track width also
affects characteristic impedance; narrowing a trace below the qualified
width can shift impedance outside the intended range and increase
reflection-induced signal integrity issues.

## Silkscreen Over Board Edge

Silkscreen text or graphics must maintain at least 0.15mm clearance from
the board edge (Edge.Cuts layer). Text overlapping or clipped by the board
outline is often physically cut off during panel routing/depaneling and
becomes illegible, which is a cosmetic/manufacturability issue rather than
an electrical one.

## Unconnected / Unrouted Nets

Any net with pads assigned but no completed copper connection between them
represents an incomplete design. Before fabrication, every net must either
be fully routed or explicitly marked as intentionally unconnected (e.g. a
test point or a populate-later option).

## SPI Bus Routing Guidance

SPI_CLK and other high-speed digital clock signals should be routed with
controlled length and kept away from adjacent unrelated signal pads to
avoid crosstalk-induced clock jitter. Maintain full clearance margins near
clock nets in particular, since clearance violations on clock lines are
more likely to produce intermittent, hard-to-debug signal integrity
failures than static DC nets.
