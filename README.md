# Apple II Super Serial Card → Centronics GLP 3101

Getting an **Apple II Super Serial Card** to print to a **Centronics GLP (Great Little
Printer), model 3101** over RS-232, at 9600 baud, from BASIC and any other software.

Working, with a bootable ProDOS test/diagnostic disk.

## Why this exists

The GLP 3101's user manual (Centronics `37403101-9A00`, Rev A, October 1984) is **not
online anywhere**. The only catalogued copy is at Stanford, unscanned. Widely repeated
information about this printer is wrong: the commonly cited source claims the 3101 was
parallel-only and that NLQ was a GLP II feature. Both are false — this 3101 has serial and
NLQ. Its DIP switch tables here are transcribed from the physical manual.

Four independent faults had to be fixed, each producing indistinguishable garbage, so
fixing any one alone changed nothing visible:

1. **Bit 7** — the Apple emits high-ASCII; the GLP renders `$80`–`$FF` as Epson graphics
2. **Parity** — the GLP checks odd parity *even in 8-bit mode* and silently drops failures
3. **Linefeed** — neither end was generating one
4. **Flow control** — characters lost during the ~80 ms CR/LF mechanical cycle

Plus a trap that is in no manual: **the two DIP switch blocks are mounted in opposite
orientations** (§ 1.5). Our copy of the manual carries a previous owner's handwritten
correction to the block-numbering figure, so they hit it too.

## Contents

| | |
|---|---|
| `README.md` | the whole thing — start at **WORKING CONFIGURATION** |
| `disk/GLPTEST.dsk` | bootable ProDOS test disk, DOS sector order |
| `disk/GLPTEST.po` | same volume, ProDOS order |
| `src/*.bas` | the nine Applesoft programs on the disk |
| `tools/` | ProDOS filesystem writer and Applesoft tokenizer, written from scratch |

`PRSETUP` is the one for daily use: run it once after boot, then `PR#2` / `LIST` / `PR#0`.
The others are diagnostics — loopback, baud and framing sweeps, a receive-line watcher, and
a direct-to-6551 printer that bypasses the card firmware entirely.

## Rebuilding the disk

```
python3 tools/build.py [path/to/bootable-prodos.dsk]
```

`PRODOS` and `BASIC.SYSTEM` are copied out of the donor image at build time; they are Apple
system files and are not redistributed here. Everything else is generated from `src/`.

---

## WORKING CONFIGURATION

**Status: working.** Confirmed 2026-09-25 at **9600 baud** through the ordinary `PR#2`
path — `STDTEST` clean, and `PR#2` / `LIST` / `PR#0` from BASIC clean. Because the route is
the standard firmware one, other software inherits it.

### Printer — Centronics GLP 3101

| Switch | Setting | Meaning |
|--------|:-------:|---------|
| 1-1 | **as shipped — do not change** | BUSY polarity. Correct already: DSR asserted when on line, deasserted when off line. |
| 1-2 | ON | transmits XON/XOFF (unused) |
| 1-3 / 1-4 / 1-5 | **ON / ON / ON** | **9600 baud** |
| 1-6 | ON | **odd parity — the printer really does check it** |
| 1-7 | **ON** | **7 data bits** — this is what lets the Apple's high bit be dropped |
| 1-8 | OFF | serial interface |
| 2-7 | **ON** | **printer adds its own linefeed after CR** |

Everything else on SW2 at factory.

### Apple II Super Serial Card, slot 2

Jumper block → **TERMINAL**. Straight-through DB-25, fully wired (the handshake lines are
used).

| SW1 | | SW2 | |
|:---:|---|:---:|---|
| 1-4 | **OFF OFF OFF ON — 9600 baud** | 1 | ON — 1 stop bit |
| 5 | OFF — printer mode | 2 | **ON — 1/4 s pause after CR** |
| 6 | ON — printer mode | 3 / 4 | OFF / ON — 80 columns |
| 7 | ON — normal | 5 | **OFF — printer does the LF, not the card** |
| | | 6 | OFF — no interrupts |
| | | 7 | OFF — normal |

With these, a bare `PR#2` already gives 9600 baud, 1 stop bit, 80 columns and a CR pause,
and the **printer** supplies linefeeds on its own. Only the word length and parity still
need software.

**Linefeed must come from exactly one side.** Both → double spacing; neither → every line
overprinted. Here the printer does it (SW2-7 ON), so the card must not (`L D`).

### `PRSETUP` is mandatory, not a convenience

There is no switch-only configuration that works. The SSC's DIP switches can only select
**8 data bits**, and 7-bit mode is the only thing that strips the Apple's high bit. So
without `PRSETUP`:

- every character goes out with bit 7 set and prints as an Epson graphics glyph
- **carriage return goes out as `$8D`, not `$0D`** — so the printer never sees a CR at all

That last point matters: printer SW2-7 cannot rescue it, because there is no carriage
return for it to append a linefeed to. Setting SW2-7 makes no observable difference until
`PRSETUP` has run. Run it once after every boot.

### Run once after each boot

`PRSETUP` on the test disk, or these lines in any program:

```basic
10  D$ = CHR$(4) : C$ = CHR$(9)
20  PRINT D$;"PR#2"
30  PRINT C$;"14B"  : REM 9600 BAUD
40  PRINT C$;"1D"   : REM 7 DATA BITS, 1 STOP
50  PRINT C$;"1P"   : REM ODD PARITY
60  PRINT C$;"LD"   : REM PRINTER SW2-7 SUPPLIES THE LF
70  PRINT C$;"2C"   : REM 250 MS PAUSE AFTER CR
80  PRINT C$;"80N"  : REM 80 COLUMNS
90  PRINT D$;"PR#0"
```

Then `PR#2` / `LIST` / `PR#0` works from anywhere.

**Why software is unavoidable:** the SSC's DIP switches only ever give 8 data bits — SW2-1
selects stop bits, not word length. 7 data bits and parity can only be set with `<n>D` and
`<n>P`. The card keeps them until the Apple is reset, not merely until the next `PR#2`, so
once per boot is enough.

**At 9600 the printer receives about eight times faster than it can print**, so its buffer
fills and the handshake does the real work — at 1200 the timing was forgiving enough to hide
mistakes. If characters go missing, raise the CR pause to `3C`, or drop back to `8B` (1200)
with printer SW1-3/4/5 = OFF/OFF/ON.

### The frame

```
SSC sends:  START | d0 d1 d2 d3 d4 d5 d6 | ODD PARITY | STOP     10 bits
GLP wants:  START | b0 b1 b2 b3 b4 b5 b6 | PARITY     | STOP     10 bits
```

7 data bits drop the Apple's high bit at the UART, so `A` goes out as `$41` rather than
`$C1`. Parity matches SW1-6.

### The four faults, in the order they had to be fixed

1. **Bit 7.** The Apple emits high-ASCII; the GLP renders `$80`–`$FF` as Epson graphics, so
   `ABCDEFGH` printed as `┴┬├─┼╞╟╚` and CR arrived as `$8D`, which is not a carriage return.
2. **Parity.** The GLP checks odd parity **even in 8-bit mode** and silently discards
   failures. Sending no parity bit, only characters with an even number of 1 bits survived:
   `LINE ONE   ABCDE 12345` printed as `NNABD35`.
3. **Linefeed.** Originally SW2-7 = OFF, so nobody generated one. Now SW2-7 = ON and the
   printer does it, so the card must not (`L D`).
4. **Flow control.** Without it the printer loses whatever arrives during the ~80 ms CR/LF
   mechanical cycle — about ten characters at 1200 baud. The firmware's handshake plus a
   250 ms CR pause covers it.

### Do not flip SW1-1

It looks tempting, because driving the 6551 directly needs `DSR HIGH = READY` — the
opposite of the RS-232 convention. That is an artefact of polling the bit once per byte;
the firmware treats the same line as a gate and wants it the other way. **The shipped
position is correct for the firmware.** Flipping it makes the card wait forever, printing
only a burst each time the printer is toggled off and on line.

---

## 0. Source of truth

Settings below come from the printer's own manual:

> **GLP (Great Little Printer) Users Manual** — Centronics, `37403101-9A00`, Rev A, October 1984

Unit: **Centronics GLP Model 3101**, ser. L44205270, 117 V 60 Hz, made in Japan.
Both a 36-pin Centronics parallel connector and a DB-25 serial connector are fitted.

This manual is not online — the only catalogued copy is at Stanford, unscanned. Everything
here that concerns the printer is transcribed from photographs of the physical manual, and
supersedes an earlier draft of this file that was based on a GLP **II** (Brother M-1109)
hobbyist page. That page was wrong on three counts: it claimed the 3101 was parallel-only,
claimed NLQ was a GLP II feature, and gave a switch layout that does not match this machine
(10 switches per bank vs. the actual 8).

> **Switch positions are given as ON / OFF exactly as the manual states them.**
> Unlike the GLP II, this manual does not define an UP/DOWN convention — read the ON/OFF
> legend printed on the switch block itself.
>
> **Power the printer off before changing any switch.** The manual is explicit about this;
> settings are read at power-on only.

---

## 1. Printer: Centronics GLP 3101

### 1.1 DIP SW1 — serial interface (Table 2-2)

Eight switches. Only active when the interface mode switch selects serial.

| Seg | Function | ON | OFF | As delivered | **Set to** |
|:---:|----------|----|-----|:------------:|:----------:|
| 1-1 | BUSY Polarity | BUSY | /BUSY | ON | **OFF** |
| 1-2 | X-ON/OFF | Transmit | Not transmit | ON | **ON** |
| 1-3 | Baud rate | see 1.2 | | OFF | **OFF** |
| 1-4 | Baud rate | see 1.2 | | OFF | **OFF** |
| 1-5 | Baud rate | see 1.2 | | ON | **ON** |
| 1-6 | Parity | Odd | Even | ON | see note |
| 1-7 | Character code level | 7 bits | 8 bits | OFF | **OFF** (8 bits) |
| 1-8 | Interface mode | Parallel | Serial | ON | **OFF** (serial) |

So from the factory state you change exactly **two** switches to get on the air:
**1-8 → OFF** (serial) and **1-1 → OFF** (busy polarity). 1-2 is already correct.

#### 1-1 BUSY Polarity — the one that will bite you

Verbatim from the manual:

> Busy Polarity Switch (1-1) controls both DTR and Reverse Channel. With the switch in the
> OFF position, DTR and Reverse Channel are ON when the printer is READY or NOT BUSY.
> Conversely, DTR and Reverse Channel are OFF for a READY or NOT BUSY condition with the
> switch set in the ON position.

**As delivered it is ON, i.e. inverted** — DTR is deasserted when the printer is *ready*.
That is backwards for the Apple SSC, which will sit and wait forever. Set 1-1 **OFF**.

This also settles an earlier open question: the printer **does** drive a hardware busy line
(DTR, plus a Reverse Channel), so hardware handshaking is genuinely available here.

#### 1-6 Parity — the GLP DOES use parity in 8-bit mode

The manual offers only Odd / Even on 1-6, with no "none" position. **Parity applies even
when 1-7 selects 8 bits.** With SW1-6 = ON the printer checks **odd parity** and silently
discards every character that fails.

So the printer's frame is **11 bits**: `START | d0..d7 | PARITY | STOP` at 1200 baud.

Proven by the drop pattern. Sending `LINE ONE   ABCDE 12345` with 8 data / no parity
printed exactly `NNABD35` — and those are precisely the characters with an **even number of
1 bits**. A 10-bit frame puts our stop bit (always 1) into the printer's parity slot, so a
character survives only when `ones(data) + 1` is odd. Predicted survivors matched the
printout character for character.

> **An earlier version of this file claimed the opposite**, on the grounds that RXWATCH
> received XON and XOFF as clean 17 and 19 with the 6551 set to 8-data/no-parity. That
> inference was invalid: the *data bits* are identical either way. Under odd parity, XON's
> parity bit is 1 and passes as a stop bit, while XOFF's is 0 and raises a framing error but
> still delivers the right byte. RXWATCH does not check the framing-error flag, so both look
> clean. The measurement could never have distinguished the two cases.

### Correct settings

| Path | Apple side |
|------|-----------|
| Direct 6551 POKEs, bit 7 masked in software | control `24`, command `43` — 8 data, odd parity, 1 stop |
| SSC firmware, printer left at 8 bits | not possible — 8 data bits means the Apple's bit 7 goes out as data |
| SSC firmware, **printer SW1-7 → ON (7 bits)** | `1D` + `1P` — 7 data, odd parity, 1 stop |

The last row is the one that makes ordinary `PRINT` work: 7 data bits drops the Apple's high
bit, the odd parity bit matches SW1-6, and the frame is 10 bits at both ends. See § 4a.

### 1.2 Baud rate (Table 2-3)

Three switches, 1-5 as MSB through 1-3 as LSB — a straight binary count.

| Baud | 1-5 | 1-4 | 1-3 |
|-----:|:---:|:---:|:---:|
| 110 | OFF | OFF | OFF |
| 150 | OFF | OFF | ON |
| 300 | OFF | ON | OFF |
| 600 | OFF | ON | ON |
| **1200** \* | **ON** | **OFF** | **OFF** |
| 2400 | ON | OFF | ON |
| 4800 | ON | ON | OFF |
| 9600 | ON | ON | ON |

\* factory setting. 2400 **is** supported — the GLP II page omitted it.

### 1.3 DIP SW2 — both parallel and serial (Table 2-1)

Eight switches. Leave these at factory settings; only 2-7 interacts with the Apple.

| Seg | Function | ON | OFF | As delivered | **Set to** |
|:---:|----------|----|-----|:------------:|:----------:|
| 2-1 | Form Length | 11" | 12" | ON | ON |
| 2-2 | Not used | – | – | OFF | OFF |
| 2-3 | Character Set | Set 2 | Set 1 | ON | ON |
| 2-4 | NLQ | Valid | Invalid | OFF | taste |
| 2-5 | Skip perforation (1 inch) | Valid | Invalid | OFF | taste |
| 2-6 | Buffer Full Print | With LF | Without LF | ON | ON |
| 2-7 | CR (auto LF enable/disable) | Print with LF | Print without LF | OFF | **OFF** |
| 2-8 | /SLCT IN | Fixed | Not fixed | ON | ON |

**2-7 is the line-spacing switch**, and on this unit it is **OFF** — the printer prints
without LF. So **the SSC must generate the linefeed** (`L E`, or SSC SW2-5 = ON). Exactly
one of the two must do it: both → double spacing, neither → everything overprinted on one
line. See § 1.5.

Note 2-4: **this 3101 does have NLQ**, and it is switched on here.

### 1.5 Switch orientation — read this before touching anything

**The two DIP blocks are mounted in opposite orientations.** This caused more wasted effort
than every other issue here combined, and the manual does not mention it — though the copy
we have carries a *handwritten* correction to the block-numbering figure, so the original
owner hit it too.

Physical layout, viewed through the access opening, left to right:

```
[ left block = SWITCH 1 ]   [ right block = SWITCH 2 ]
  left->right = seg 8..1      left->right = seg 1..8
  DOWN = ON, UP = OFF         UP = ON, DOWN = OFF
```

- **Switch 1** follows Figure 1-4 as printed: segments run 8→1 left to right, DOWN = ON.
- **Switch 2** is rotated 180°: segments run 1→8 left to right, and UP = ON.

Two independent confirmations:

1. Reading the left block by the Fig 1-4 convention gives 1200 baud / 8 bits / serial, which
   matches all four RXWATCH measurements. Swapping the blocks would give 4800 baud / 7 bits,
   which contradicts them — so the left block is Switch 1, as the handwritten note says.
2. Reading the right block by that same convention gives the exact inverse of the factory
   defaults in **all eight** positions. Reading it rotated gives the factory defaults in all
   eight. Eight-for-eight inversion is an orientation artefact, not eight deliberate changes.

### 1.5.1 Current state

**SW1** (1→8): `OFF ON OFF OFF ON ON OFF OFF`
— serial, 1200 baud, 8 data bits, XON/XOFF transmit on, busy polarity normal. Correct.

**SW2** (1→8): `ON OFF ON OFF OFF ON OFF ON` — factory throughout.
**2-7 = OFF, so the printer adds no linefeed and the SSC must supply it** (`L E`, or
SSC SW2-5 = ON; programs bypassing the firmware must send LF (10) after CR (13)).

### 1.6 Changes needed

| Switch | From | To | Why |
|--------|:----:|:--:|-----|
| **1-8** | ON | **OFF** | select the serial interface — without this nothing happens |
| **1-1** | ON | **OFF** | busy polarity; harmless on a 3-wire cable, essential on a full one |

Nothing else needs to move. Baud, data bits and XON/XOFF are already correct from the
factory.

---

### 1.4 Self-test

Hold **LINE FEED** and switch POWER on. The printer prints its character set continuously
until you power it off; the manual says to stop after a few sets and check the characters
are in line, unbroken and unsmudged.

This is a mechanism check only — it does **not** dump the switch configuration, and it does
not exercise the serial port. Useful to prove the printer works before you blame the cable.

---

## 2. Apple II Super Serial Card

### Jumper block

**Arrow must point to `TERMINAL`.**

In this position the block acts as a built-in **modem eliminator** — so do *not* also
use a null-modem cable or adapter. The Apple manual warns explicitly that a second
modem eliminator cancels the jumper block and nothing will work.

### SW1

| SW | Set | Why |
|:--:|:---:|-----|
| 1 | OFF | 1200 baud |
| 2 | ON | " |
| 3 | ON | " |
| 4 | ON | " |
| 5 | **OFF** | Printer Mode |
| 6 | **ON** | Printer Mode |
| 7 | ON | normal (pin 8 / DCD) |

For 9600 baud: SW1-1..4 = **OFF OFF OFF ON**.

#### SSC baud rate (SW1-1 … SW1-4)

| Baud | 1 | 2 | 3 | 4 |
|-----:|:-:|:-:|:-:|:-:|
| 110 | ON | ON | OFF | OFF |
| 300 | ON | OFF | OFF | ON |
| 600 | ON | OFF | OFF | OFF |
| 1200 | OFF | ON | ON | ON |
| 2400 | OFF | ON | OFF | ON |
| 4800 | OFF | OFF | ON | ON |
| 9600 | OFF | OFF | OFF | ON |
| 19200 | OFF | OFF | OFF | OFF |

### SW2

| SW | Set | Why |
|:--:|:---:|-----|
| 1 | ON | 1 stop bit |
| 2 | OFF | no CR delay |
| 3 | OFF | 80 columns, video off |
| 4 | ON | " |
| 5 | **ON** | SSC adds LF after CR (printer SW2-7 = OFF) |
| 6 | OFF | no interrupts |
| 7 | OFF | normal |

Line width (SW2-3 / SW2-4): 40 col + video ON = ON ON · 72 = ON OFF · 80 = OFF ON · 132 = OFF OFF.
Only the 40-column setting leaves the Apple's video screen on.

### Slot 2 is fine

The Apple manual only pins down slots for **Pascal** (slot 1 = printer, slot 3 = terminal).
Under BASIC, any slot 1–7 works.

---

## 3. Cable

**Start with 3 wires: pins 2, 3, 7, straight through.**

In TERMINAL position the SSC presents itself as DCE, so its pin 3 is output and pin 2 is
input. Straight-through (pin n → pin n) is correct. Do **not** use a null-modem cable or
adapter — the jumper block already is one.

Deliberately leave 4, 5, 6, 8, 19, 20 unconnected for now. The SSC has 15 kΩ pull-ups on
CTS / DCD / DSR, so unconnected handshake inputs read as asserted and it will always
transmit.

> **The trap:** a fully-wired 25-conductor cable. In TERMINAL mode the SSC refuses to
> transmit unless it sees **both pin 4 (RTS) and pin 20 (DTR)** asserted by the printer.
> Any one of those the GLP doesn't drive — or drives with the wrong polarity — hangs the
> Apple with no error. SW1-1 as delivered gets the polarity exactly backwards (§ 1.1).

Flow control on 3 wires comes from **XON/XOFF over pin 2**: printer SW1-2 = ON (transmit)
plus `PRINT CHR$(9);"XE"` on the Apple. The SSC's XOFF recognition is **off by default** —
this is the step people miss.

### Hardware handshake — measured

The printer drives its busy line on **DB-25 pin 20 (DTR)**, which in TERMINAL position
reaches the SSC's **DSR** input. Measured from the 6551 status register:

| Printer | Status | bit 6 (DSR) | bit 5 (DCD) |
|---------|:------:|:-----------:|:-----------:|
| on line | 28 | **0 — asserted** | 0 — asserted |
| off line | 92 | **1 — not asserted** | 0 — asserted |

Only DSR moves, so DCD is not the busy line. **DSR low = printer ready**, which also confirms
SW1-1 is at the correct (non-inverted) polarity.

This was established by measurement because Appendix B's serial pin assignment table was
never available — the one documentation gap that remained open throughout.

**Using it:** poll status bit 6 and send only while it is 0. `DIRECT` does this with
`H` set to `DSR LOW = READY`. This is strictly better than timing delays: it is exact,
and it still works when the baud rate goes up.

**Why delays were needed without it:** the printer loses whatever arrives during the CR/LF
mechanical cycle, roughly 80 ms, which at 1200 baud is about ten characters. The symptom is
two characters through, ten gone, then the tail of the line.

**XON/XOFF is not a good substitute here.** The printer does send it, but the 6551's receive
register overruns while unread (status bit 2 was set in both readings above), so XOFF can be
missed.

---

## 4. Smoke test

### Quick version

At the `]` prompt. Note you'll be typing blind once video goes off (80-column setting):

```
PR#2
PRINT CHR$(9);"XE"
PRINT "HELLO GLP"
PR#0
```

### Fuller version

Also saved as [`glp-smoketest.bas`](glp-smoketest.bas):

```basic
10  REM  APPLE II SUPER SERIAL CARD (SLOT 2)
20  REM  --> CENTRONICS GLP II SERIAL SMOKE TEST
30  S = 2:D$ =  CHR$ (4):C$ =  CHR$ (9)
40  PRINT D$;"PR#";S
50  PRINT C$;"8B": REM  1200 BAUD (14B = 9600)
60  PRINT C$;"0D": REM  8 DATA BITS, 1 STOP BIT
70  PRINT C$;"0P": REM  NO PARITY
80  PRINT C$;"0C": REM  NO CARRIAGE-RETURN DELAY
90  PRINT C$;"80N": REM  80 COLUMNS
100  PRINT C$;"LD": REM  NO LF - PRINTER SW2-7 ADDS IT
110  PRINT C$;"XE": REM  OBEY XOFF/XON FROM PRINTER
120  PRINT "APPLE II SSC SLOT ";S;" --> CENTRONICS GLP"
130  PRINT "....+....1....+....2....+....3....+....4....+....5....+....6....+....7....+....8"
140  FOR I = 32 TO 126: PRINT  CHR$ (I);: NEXT I: PRINT
150  FOR L = 1 TO 60: PRINT "LINE ";L;" - FLOW CONTROL TEST": NEXT L
160  PRINT  CHR$ (12): REM  FORM FEED
170  PRINT D$;"PR#0"
180  PRINT "DONE - CHECK THE PAPER."
190  END
```

Two things to know about it:

1. **Lines 40 and 170 use the DOS/ProDOS `CHR$(4)` form**, which is required inside a
   *program* — a bare `PR#2` statement lets DOS grab the output hooks back.
   But at a bare ROM Applesoft prompt with no disk booted, `CHR$(4)` does nothing and the
   literal text `PR#2` gets sent to the printer. In that case:
   change line 40 to `40 PR#2` and line 170 to `170 PR#0`.

2. **Line 150 prints ~2400 characters**, overrunning the GLP's 1936-byte buffer, so it
   genuinely exercises XON/XOFF. Garbage or dropped text near the end means flow control
   isn't working. Raise the `60` to `200` to hammer it harder.

### Useful SSC Printer Mode commands

All are `PRINT CHR$(9);"..."` from BASIC — the `PRINT` statement's own carriage return
terminates the command.

| Command | Effect |
|---------|--------|
| `<n>B` | baud rate — 0 = use switches, 6 = 300, 7 = 600, 8 = 1200, 12 = 4800, 14 = 9600 |
| `<n>D` | data format — 0 = 8 data / 1 stop, 4 = 8 data / 2 stop |
| `<n>P` | parity — 0 = none, 1 = odd, 3 = even |
| `<n>C` | CR delay — 0 = none, 1 = 32 ms, 2 = 250 ms, 3 = 2 s |
| `<n>N` | line width, video off (e.g. `80N`) |
| `L E` / `L D` | generate LF after CR: enable / disable |
| `X E` / `X D` | XOFF recognition: enable / disable (**default is D**) |
| `R` | reset the SSC + `PR#0` and `IN#0` |

`<n>B` overrides SW1-1..SW1-4, so you can retune baud **without opening the case**.

---

## 4a. The high bit — the thing that actually breaks printing

**Symptom:** the printer produces Epson box-drawing and shaded-block glyphs instead of
text, and everything lands on one line with no carriage returns.

**Cause:** the Apple II emits text with **bit 7 set** — its internal high-ASCII convention.
`A` leaves Applesoft as `$C1`, not `$41`. The SSC at 8 data bits passes bit 7 straight
through, and the GLP in 8-bit mode uses `$80`–`$FF` for its graphics set:

| Sent | On the wire | GLP prints |
|------|-------------|-----------|
| `A B C D E` | `$C1 $C2 $C3 $C4 $C5` | `┴ ┬ ├ ─ ┼` |
| `1 2 3 4` | `$B1 $B2 $B3 $B4` | `▒ ▓ │ ┤` |
| space | `$A0` | `á` |
| **CR** | **`$8D`** | a printable glyph — **not** a carriage return |

The last row is why nothing breaks onto a new line.

**Fix — set the SSC to 7 data bits plus SPACE parity:**

```
PRINT CHR$(9);"1D"
PRINT CHR$(9);"7P"
```

`1D` (7 data bits) makes the 6551 drop bit 7. `7P` (SPACE parity, a constant 0) then refills
that bit position so the frame stays 10 bits:

```
SSC sends:      START | d0 d1 d2 d3 d4 d5 d6 | 0 | STOP
GLP reads:      START | b0 b1 b2 b3 b4 b5 b6 b7 | STOP
                                             ^-- always 0
```

**`7P` is not optional.** Without it the frame is only 9 bits, the printer reads your stop
bit as b7, and bit 7 is set high again.

Carriage return becomes `$0D`, so line breaks return as well.

### This must be re-sent after every `PR#2`

The SSC's DIP switches only ever give 8 data bits — SW2-1 selects stop bits, not word
length. So 7-data/SPACE can only be set in software, and any program that issues its own
`PR#2` needs to send `1D` and `7P` afterwards or it will print graphics again.

---

## 5. Troubleshooting

| Symptom | Cause |
|---------|-------|
| **Nothing prints, Apple hangs** | Ctrl-Reset. Either SW1-1 is still ON (inverted busy — most likely), or a fully-wired cable with an undriven pin 4/20. |
| **Nothing prints, Apple fine** | SW1-8 still ON (parallel mode), or TX/RX swapped. |
| **Garbage characters** | Serial is live and the cable is right — only speed or framing is wrong. |
| **Double-spaced** | Both SSC SW2-5 and printer SW2-7 are on. |
| **Everything on one line** | Neither SSC SW2-5 nor printer SW2-7 is on. |
| **First page fine, then garbles** | XON/XOFF not working: check `X E` ran and printer SW1-2 = ON. |

The **nothing vs. garbage** split is the key diagnostic — it separates a mode/wiring fault
from a speed/framing fault, so you never search both at once.

### If it garbles

Garbage is **progress**: bytes are arriving, so the cable is right, the printer is in serial
mode, and § 1.6 is done. Only speed or framing is left. The "won't print until I toggle
ONLINE" symptom is the same fault — the printer buffers a line until it sees a CR, never
recognises one in garbled data, and flushes when taken offline. It clears itself once
framing is right.

**Framing is the prime suspect, not speed.** The printer's rate is pinned by its own
switches (SW1-3/4/5 = OFF/OFF/ON = 1200) and the programs here force the SSC to 1200 in
software, so the two cannot disagree.

Run [`framing-sweep.bas`](framing-sweep.bas). It prints a labelled line in each of eight
data/parity/stop combinations, most likely first, all at 1200 baud with XON/XOFF off.
Whichever label is legible is your framing.

Top candidate is **8 data / odd parity / 1 stop** (`0D` + `1P`), because SW1-6 is set to Odd
and the manual gives parity no "none" position — see § 1.1. Quick manual version:

```
PR#2
PRINT CHR$(9);"XD"
PRINT CHR$(9);"1P"
PRINT "HELLO WORLD"
PR#0
```

Two housekeeping notes while sweeping:

- **Disable XON/XOFF** (`PRINT CHR$(9);"XD"`) during diagnosis. With the line garbled, a
  byte that happens to look like XOFF (19) will stall the card indefinitely. Re-enable with
  `X E` once framing is right — you need it for long jobs.
- **Power-cycle the printer after a garbage run.** Random bytes can contain ESC sequences
  that leave it in an odd font, pitch or emulation mode, which then looks like a fresh bug.

Only if every framing combination fails is speed worth doubting — then run
[`baud-sweep.bas`](baud-sweep.bas), which sweeps 110 through 9600 via the SSC's `<n>B`
command with no switch touched.

Start at **1200 baud** — the printer's factory rate, so the fewest variables — then move up
to 9600 once it works.

---

## 7. Test disk

`GLPTEST.dsk` (DOS sector order) and `GLPTEST.po` (ProDOS order) — same 140K bootable
ProDOS volume `GLP.TEST`, in both orderings. Use whichever your FloppyEmu or emulator
prefers; try the `.po` first if the `.dsk` won't mount.

Boots straight to a menu. `PRODOS` and `BASIC.SYSTEM` were copied from
`~/git/perfect-paul-ii/disk/perfect-paul.dsk` — your own disk, nothing downloaded.

| Menu | File | What it does |
|:----:|------|--------------|
| 1 | `LOOPBACK` | **Tests the SSC alone.** Pokes the 6551 directly — no firmware, no `PR#`, no printer. Needs pins 2↔3 shorted on the DB-25. |
| 2 | `FRAMING` | Eight data/parity/stop combinations at 1200 baud, labelled. Most likely first. |
| 3 | `BAUD` | 110 through 9600, labelled, via the SSC's `<n>B`. |
| 4 | `SMOKETEST` | Full print test: ruler, character set, 60 lines, form feed. |
| 5 | `RXWATCH` | Shows bytes arriving **from** the printer, flagging XON/XOFF. Reads the 6551 directly. |

### Suggested order

1. **LOOPBACK** with a paperclip across pins 2 and 3. Ten characters out, ten back. This
   settles "is the card dead?" in ten seconds, with the printer out of the picture.
2. **FRAMING**. Whichever label prints legibly is your answer; set it permanently with the
   matching `<n>D` / `<n>P` commands, or switches.
3. **RXWATCH**, then take the printer off line and on line. If nothing appears, the printer
   isn't sending XON/XOFF back and you'll want hardware handshaking instead.
4. **SMOKETEST** once framing is right.

Source for each is in the matching `.bas` file here; the disk is rebuilt from them.

---

## 6. Sources

### Printer — authoritative

**GLP (Great Little Printer) Users Manual**, Centronics Data Computer Corp., Hudson NH.
Part `37403101-9A00`, Rev A, October 1984. Photographed from the physical manual:
Table 2-1 (SW2), Table 2-2 (SW1), Table 2-3 (baud), § 2.8 DIP switch settings,
§ 2.9 initial operation, Appendix B section 1 (parallel pinout).

The only catalogued copy elsewhere is at
[Stanford](https://archives.stanford.edu/catalog/m0997_aspace_ref13303_q4m), unscanned.
It is absent from the Internet Archive and from bitsavers' Centronics collection. If you
ever feel like scanning it, it would be the only copy on the open web.

### Apple SSC — authoritative

- [Apple II Super Serial Card — Installation and Operating Manual (1981)](https://archive.org/stream/Apple_II_Super_Serial_Card_1981_Apple/Apple_II_Super_Serial_Card_1981_Apple_djvu.txt)

Baud table cross-checked against the four worked printer examples in the manual
(IDS 560, NEC 5510 × 2, Qume Sprint 5).

### Superseded

An earlier draft of this file used
[The Great Little Printer](https://manuale-archive.keep.pl/files/The_Great_Little_Printer.html),
a hobbyist page documenting a Brother M-1109 (GLP II). It is wrong for the 3101 on every
point that matters: model capabilities, bank size, switch numbering, and function mapping.
Disregarded entirely.

### Still open

**The serial interface pin assignment** — Appendix B, section 2 of the manual, on the page
following the parallel pinout. Needed only to move from 3-wire XON/XOFF to hardware
handshaking (§ 3).
