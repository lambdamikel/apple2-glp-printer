# Using real software with the GLP

## The rule

The GLP **always requires a parity bit** — Odd or Even, with no "none" setting. The Apple
II also emits high-ASCII, so the Super Serial Card must be put into 7-data-bit mode, which
its DIP switches cannot do. Both facts mean the card has to be configured in software
(`1D` + `1P`), and that configuration survives only until the Apple is reset.

So software falls into two groups:

| | |
|---|---|
| **Works** | prints through `PR#slot` and leaves the card's settings alone |
| **Cannot work** | programs the card's registers itself — it will assume 8 data bits and no parity, which this printer cannot accept at any switch setting |

Booting an application disk resets the Apple, so the setup has to run **on that disk**,
before the application starts. That is what `tools/patch_disk.py` does.

## Tested

| Software | Result | Notes |
|----------|--------|-------|
| Applesoft BASIC `PR#2` / `LIST` | **works** | after `PRSETUP` |
| **AppleWorks 1.3** | **works** | 64 K; two-disk set. Add a printer: Epson, slot 2 |
| **FreeWriter** (P. Lutus, 1984) | **works** | editor only; printing is the separate `PRINTER` utility in `FREEWARE/`, slot 2 |
| Easy Working Writer 1.03 (Spinnaker, 1987) | **cannot work** | see below |

AppleWorks 2.0 and 3.0 need 128 K. AppleWorks **1.3 runs in 64 K**.

## Why Easy Working Writer cannot work

Its printer setup offers `IIc SERIAL / SUPER SERIAL / APPLE PARALLEL / OTHER PARALLEL /
Apple IIgs SSC`, a slot, and a baud rate — but it writes the card's registers directly
(nine `STA $C08D,X` / `STA $C08F,X` sites around `$1439`–`$1530`), forcing 8 data bits with
no parity. It does mask bit 7 correctly, so characters arrive as clean ASCII rather than
graphics — but with no parity bit, the GLP reads the masked bit 7 as the parity slot and
discards roughly half of everything.

The signature is unmistakable. `THIS IS A TEST` prints as `TI I  TET` — exactly the
characters with an odd number of 1 bits:

```
printer checks parity over (data bits + whatever lands in the parity slot)
host sends 8 data bits, bit 7 masked to 0, no parity
  -> printer reads that 0 as the parity bit
  -> odd parity passes only when ones(data) is odd
```

Selecting `OTHER PARALLEL` does not help: that driver does not drive a serial card at all.

## Patching your own disk

```
python3 tools/patch_disk.py IN.dsk OUT.dsk --donor <any bootable ProDOS disk>
```

It finds the disk's current boot `.SYSTEM` file, adds `BASIC.SYSTEM` and a `STARTUP` that
configures the card and then chains to that original target. `--slot` and `--baud` adjust
the defaults (slot 2, 9600).

`BASIC.SYSTEM` is copied from a donor disk at patch time. It is Apple system software and
is not redistributed here.

## The included disk

`disk/FreeWriter-GLP.dsk` / `.po` is FreeWriter patched this way. FreeWriter is by
Paul Lutus (1984), of Apple Writer fame; the autoboot disk was assembled by Lynn Nicholson
in 1986. Its own title screen states it is freeware, free to copy but not to sell.

The commercial word processors are not included here, patched or otherwise. Use the
patcher on your own copies.
