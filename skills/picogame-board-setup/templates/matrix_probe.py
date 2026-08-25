# picogame MATRIX PROBE. For a ROW x COLUMN key matrix (e.g. a QWERTY) instead of one-pin-per-button.
# Copy to CIRCUITPY as code.py, edit ROWS/COLS pins, then press ONE key at a time: it prints the
# key_number and (row, col) for each. Put those into PICOGAME_MATRIX_MAP (NAME=row,col or
# NAME=key_number). See references/settings.md.
import time
import board
import keypad

# ---------------- config: EDIT for your matrix (pin ORDER sets the row/col indices) ----------------
ROWS = ["GP0", "GP1", "GP2", "GP3"]
COLS = ["GP4", "GP5", "GP6", "GP7"]
COLS_TO_ANODES = True                  # if presses don't register, flip this (diode direction)

rows = [getattr(board, n) for n in ROWS]
cols = [getattr(board, n) for n in COLS]
km = keypad.KeyMatrix(rows, cols, columns_to_anodes=COLS_TO_ANODES)
ncols = len(cols)
ev = keypad.Event()

print("=== picogame matrix probe === %dx%d matrix. Press ONE key at a time." % (len(rows), ncols))
print('map with:  PICOGAME_MATRIX_MAP = "A=row,col B=row,col ..."   (or NAME=key_number)')
print('           PICOGAME_MATRIX_ROWS = "%s"' % " ".join(ROWS))
print('           PICOGAME_MATRIX_COLS = "%s"' % " ".join(COLS))
while True:
    if km.events.get_into(ev) and ev.pressed:
        kn = ev.key_number
        print("  key_number=%d   (row=%d, col=%d)" % (kn, kn // ncols, kn % ncols))
    time.sleep(0.01)
