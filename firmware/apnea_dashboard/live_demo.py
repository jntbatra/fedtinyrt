#!/usr/bin/env python3
"""Live apnea-injection demo for the RA8P1 board.

Streams one subject's night into the board one 60 s window at a time over the
existing `feat` serial command, reads back the board's decision, and renders a
full-screen status display (big current verdict + running AHI + progress) so a
room can watch present state while the dataset is injected.

Nothing is flashed and no firmware constant is changed: this only drives the
already-shipped `feat` command. The board's inference is bit-exact against the
host reference (see FINAL_RESULTS.md); this tool just paces and visualises it.

Honesty notes (carried from FINAL_RESULTS.md, do not overstate on screen):
  * "AHI" here is the WINDOW-COUNT PROXY = predicted positive windows per hour.
    The AHI question is unresolved in this project; this is a proxy, not a
    scored clinical index.
  * The board runs the SpO2-only 10-feature INT8 model. Inputs are X[:, 11:21].

Usage:
  /tmp/cincenv/bin/python tools/live_demo.py                 # first subject
  /tmp/cincenv/bin/python tools/live_demo.py --subject tr12-0481
  /tmp/cincenv/bin/python tools/live_demo.py --list          # list subjects
  /tmp/cincenv/bin/python tools/live_demo.py --delay 0.15    # slower, for demo
  /tmp/cincenv/bin/python tools/live_demo.py --limit 200     # first 200 windows
"""

import argparse
import os
import sys
import time

import numpy as np

try:
    import serial  # pyserial
except ImportError:
    serial = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "feat_v2_cache.npz")

STRIDE_S = 30.0          # window stride: one window every 30 s of night
SPO2_COLS = slice(11, 21)  # the 10 SpO2 raw features the board's `feat` expects

# ---------------------------------------------------------------- ANSI helpers

CSI = "\x1b["
RESET = CSI + "0m"
BOLD = CSI + "1m"
RED = CSI + "97;41m"     # white on red
GREEN = CSI + "30;42m"   # black on green
DIM = CSI + "90m"
CYAN = CSI + "96m"
YELLOW = CSI + "93m"


def clear():
    sys.stdout.write(CSI + "2J" + CSI + "H")


def home():
    sys.stdout.write(CSI + "H")


def hide_cursor():
    sys.stdout.write(CSI + "?25l")


def show_cursor():
    sys.stdout.write(CSI + "?25h")


# 5-row block font for the two words we ever show. Keeps the verdict readable
# across a room without pulling in a rendering dependency.
_GLYPHS = {
    "A": ["  ##  ", " #  # ", "######", "#    #", "#    #"],
    "P": ["##### ", "#    #", "##### ", "#     ", "#     "],
    "N": ["#    #", "##   #", "# #  #", "#  # #", "#    #"],
    "E": ["######", "#     ", "#### ", "#     ", "######"],
    "O": [" #### ", "#    #", "#    #", "#    #", " #### "],
    "R": ["##### ", "#    #", "##### ", "#  #  ", "#   # "],
    "M": ["#    #", "##  ##", "# ## #", "#    #", "#    #"],
    "L": ["#     ", "#     ", "#     ", "#     ", "######"],
    " ": ["      ", "      ", "      ", "      ", "      "],
}


def big_word(word):
    rows = ["", "", "", "", ""]
    for ch in word:
        g = _GLYPHS.get(ch, _GLYPHS[" "])
        for r in range(5):
            rows[r] += g[r] + "  "
    return rows


# ---------------------------------------------------------------- board I/O

class Board:
    """Round-trips one `feat` command per window against the serial console.

    The console prints a `apnea> ` prompt after every command, which is the
    reliable end-of-reply delimiter (far faster than a fixed timeout).
    """

    def __init__(self, port, baud=115200):
        if serial is None:
            raise SystemExit("pyserial not available; use /tmp/cincenv/bin/python")
        self.s = serial.Serial(port, baud, timeout=0.05)
        time.sleep(0.3)
        self.s.reset_input_buffer()
        # wake the prompt so the first real reply is clean
        self.s.write(b"\r\n")
        self.s.flush()
        self._drain(0.4)

    def _drain(self, dur):
        t0 = time.time()
        while time.time() - t0 < dur:
            self.s.read(4096)

    def cmd(self, text, timeout=2.0):
        """Send an arbitrary console command, wait for the prompt, return reply."""
        self.s.reset_input_buffer()
        self.s.write((text + "\r\n").encode())
        self.s.flush()
        buf = b""
        t0 = time.time()
        while time.time() - t0 < timeout:
            chunk = self.s.read(4096)
            if chunk:
                buf += chunk
                if b"apnea>" in buf or b"reset" in buf or b"name" in buf:
                    break
        return buf.decode(errors="replace")

    def feat(self, vec10, timeout=2.0):
        """Send one window, return (decision_bool, prob_float, raw_reply)."""
        cmd = "feat " + " ".join("%.6f" % v for v in vec10)
        self.s.reset_input_buffer()
        self.s.write((cmd + "\r\n").encode())
        self.s.flush()
        buf = b""
        t0 = time.time()
        # read until the next prompt returns
        while time.time() - t0 < timeout:
            chunk = self.s.read(4096)
            if chunk:
                buf += chunk
                if b"apnea>" in buf:
                    break
        text = buf.decode(errors="replace")
        decision = None
        prob = None
        for ln in text.splitlines():
            ls = ln.strip()
            if ls.startswith("decision:"):
                decision = "APNEA" in ls
            elif ls.startswith("prob "):
                try:
                    prob = float(ls.split(":", 1)[1].strip())
                except (ValueError, IndexError):
                    pass
        return decision, prob, text

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


# ---------------------------------------------------------------- rendering

def render(subject, i, n, start_s, decision, prob, pos, truth_pos,
           tp, tn, fp, fn, board_ok):
    home()
    W = 64
    out = []
    out.append(BOLD + CYAN + "  RA8P1 apnea live inject".ljust(W) + RESET)
    out.append(DIM + ("  subject %s   window %d / %d   t=%5.1f min"
                      % (subject, i + 1, n, start_s / 60.0)).ljust(W) + RESET)
    out.append("")

    # big verdict banner
    if decision is None:
        banner_word = "  ??  "
        color = YELLOW
    elif decision:
        banner_word = "APNEA"
        color = RED
    else:
        banner_word = "NORMAL"
        color = GREEN
    for row in big_word(banner_word):
        out.append("  " + color + BOLD + (" " + row + " ") + RESET)
    out.append("")

    probstr = "--" if prob is None else "%.3f" % prob
    out.append("  prob %s   (threshold 0.29, shipped)" % probstr)
    out.append("")

    # running AHI = predicted positive windows per hour (WINDOW-COUNT PROXY)
    elapsed_h = ((i + 1) * STRIDE_S) / 3600.0
    ahi = pos / elapsed_h if elapsed_h > 0 else 0.0
    true_ahi = truth_pos / elapsed_h if elapsed_h > 0 else 0.0
    out.append(BOLD + "  AHI (window proxy)  pred %5.1f /h   truth %5.1f /h"
               % (ahi, true_ahi) + RESET)
    out.append(DIM + "  proxy = predicted positive windows per hour; not a scored index"
               + RESET)
    out.append("")

    # running agreement vs annotations (informational only)
    seen = tp + tn + fp + fn
    if seen:
        acc = 100.0 * (tp + tn) / seen
        sens = 100.0 * tp / (tp + fn) if (tp + fn) else float("nan")
        spec = 100.0 * tn / (tn + fp) if (tn + fp) else float("nan")
        out.append("  vs annotations   agree %5.1f%%   sens %5.1f%%   spec %5.1f%%"
                   % (acc, sens, spec))
    out.append("")

    # progress bar
    barw = W - 8
    filled = int(barw * (i + 1) / n)
    bar = "#" * filled + "-" * (barw - filled)
    out.append("  [" + bar + "]")
    out.append(DIM + ("  positives so far: %d   " % pos)
               + ("board OK" if board_ok else "NO BOARD REPLY").ljust(20) + RESET)

    # pad and print
    sys.stdout.write("\n".join(line + CSI + "K" for line in out) + CSI + "J")
    sys.stdout.flush()


def summary(subject, n, pos, truth_pos, tp, tn, fp, fn, dur):
    elapsed_h = (n * STRIDE_S) / 3600.0
    ahi = pos / elapsed_h if elapsed_h else 0.0
    true_ahi = truth_pos / elapsed_h if elapsed_h else 0.0
    seen = tp + tn + fp + fn
    print("\n" + BOLD + "==== done: %s ====" % subject + RESET)
    print("  windows streamed : %d  (%.1f min of night, %.1f s wall)"
          % (n, n * STRIDE_S / 60.0, dur))
    print("  predicted apnea  : %d windows" % pos)
    print("  AHI window proxy : pred %.1f /h   truth %.1f /h" % (ahi, true_ahi))
    if seen:
        acc = 100.0 * (tp + tn) / seen
        print("  agreement vs annotations : %.1f%%  (tp %d tn %d fp %d fn %d)"
              % (acc, tp, tn, fp, fn))
    print(DIM + "  AHI is a window-count proxy, not a scored clinical index; "
          "AUROC unchanged by calibration (see FINAL_RESULTS.md)." + RESET)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", default=CACHE)
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("--subject", default=None, help="subject id (default: first)")
    ap.add_argument("--all", action="store_true",
                    help="play every subject back to back")
    ap.add_argument("--loop", action="store_true",
                    help="repeat forever until Ctrl-C (for screen recording)")
    ap.add_argument("--board", action="store_true",
                    help="drive the on-LCD dashboard firmware: send dashname/dashreset, "
                         "plain host progress (the board screen is the show)")
    ap.add_argument("--list", action="store_true", help="list subjects and exit")
    ap.add_argument("--delay", type=float, default=0.12,
                    help="pause per window, seconds (demo pacing; >0 so it is visible)")
    ap.add_argument("--limit", type=int, default=0, help="cap windows (0 = all)")
    ap.add_argument("--dry-run", action="store_true",
                    help="no board; echo first few commands then exit")
    args = ap.parse_args()

    if not os.path.exists(args.cache):
        raise SystemExit("cache not found: %s" % args.cache)
    d = np.load(args.cache, allow_pickle=True)
    subjects = list(d.keys())

    if args.list:
        for k in subjects:
            e = d[k].item()
            print("%-12s  %5d windows  %3d positive"
                  % (k, len(e["y"]), int(np.sum(e["y"]))))
        return

    # build the playlist
    if args.all:
        playlist = subjects
    else:
        subj = args.subject or subjects[0]
        if subj not in subjects:
            raise SystemExit("no such subject %r (try --list)" % subj)
        playlist = [subj]

    if args.dry_run:
        subj = playlist[0]
        e = d[subj].item()
        feats = e["X"][:, SPO2_COLS].astype(float)
        y = e["y"]
        for i in range(min(3, len(y))):
            print("feat " + " ".join("%.6f" % v for v in feats[i]),
                  "   (truth=%d)" % y[i])
        print("... %d windows total for %s (%d subjects in playlist%s)"
              % (len(y), subj, len(playlist), ", looping" if args.loop else ""))
        return

    board = Board(args.port)
    if not args.board:
        hide_cursor()
        clear()
    try:
        while True:  # --loop repeats the whole playlist until Ctrl-C
            for subj in playlist:
                play_subject(board, subj, d[subj].item(), args)
            if not args.loop:
                break
    except KeyboardInterrupt:
        pass
    finally:
        if not args.board:
            show_cursor()
        board.close()


def play_subject(board, subj, e, args):
    """Stream one subject's night to the board and render it live."""
    X, y, starts = e["X"], e["y"], e["starts"]
    feats = X[:, SPO2_COLS].astype(float)
    n = len(y) if not args.limit else min(args.limit, len(y))

    # board mode: name + reset the on-LCD dashboard, then stream with plain output
    if args.board:
        board.cmd("dashname " + subj)
        board.cmd("dashreset")
        pos = 0
        t0 = time.time()
        for i in range(n):
            decision, _, _ = board.feat(feats[i])
            if decision:
                pos += 1
            if i % 25 == 0 or i == n - 1:
                sys.stdout.write("\r%-12s  window %4d/%d   apnea %4d   "
                                 % (subj, i + 1, n, pos))
                sys.stdout.flush()
            if args.delay:
                time.sleep(args.delay)
        print("   done (%.0fs)" % (time.time() - t0))
        return

    # brief title card between subjects (helps a recording read cleanly)
    if args.all or args.loop:
        clear()
        sys.stdout.write("\n\n\n" + BOLD + CYAN
                         + "   next subject:  %s   (%d windows)\n" % (subj, n)
                         + RESET)
        sys.stdout.flush()
        time.sleep(1.2)
        clear()

    pos = truth_pos = 0
    tp = tn = fp = fn = 0
    t0 = time.time()
    for i in range(n):
        decision, prob, _ = board.feat(feats[i])
        board_ok = decision is not None
        pred = bool(decision) if board_ok else False
        truth = bool(y[i])
        if pred:
            pos += 1
        if truth:
            truth_pos += 1
        if board_ok:
            if pred and truth:
                tp += 1
            elif pred and not truth:
                fp += 1
            elif (not pred) and truth:
                fn += 1
            else:
                tn += 1
        render(subj, i, n, float(starts[i]), decision, prob,
               pos, truth_pos, tp, tn, fp, fn, board_ok)
        if args.delay:
            time.sleep(args.delay)
    # hold the final frame briefly so a recording captures the result
    if args.all or args.loop:
        time.sleep(1.5)


if __name__ == "__main__":
    main()
