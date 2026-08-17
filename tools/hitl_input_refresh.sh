#!/usr/bin/env bash
# Human-in-the-loop runner for examples/picogame_input_refresh_stress.py.
# The device interaction is intentionally manual: mount points and serial tools
# differ between hosts, and overwriting code.py must remain an explicit action.

set -euo pipefail

step() {
  printf '\n>>> %s\n' "$1"
  read -r -p "    [Enter when done] " _
}

capture() {
  local var="$1" question="$2" answer
  printf '\n>>> %s\n' "$question"
  read -r -p "    > " answer
  printf -v "$var" '%s' "$answer"
}

ROOT=$(cd "$(dirname "$0")/.." && pwd)
TEST="$ROOT/examples/picogame_input_refresh_stress.py"

printf 'Test file: %s\n' "$TEST"
step "Back up the Fruit Jam's current code.py and settings.toml."
step "Copy the test file as CIRCUITPY/code.py. Ensure picogame_game.py and picogame_shapes.py are in CIRCUITPY/lib/."
step "Open the serial console, reset the Fruit Jam, and wait for [PG-REFRESH] PASS or a reset/safe-mode message."

capture FIRMWARE "Paste the CircuitPython firmware/version line:"
capture LAST_MARKER "Paste the last complete [PG-REFRESH] line before PASS/reset:"
capture RESULT "Result (pass, hardfault, reset, hang, exception):"
capture DETAILS "Paste the exception/reset reason, or 'none':"

printf '\n--- Captured ---\n'
printf 'FIRMWARE=%s\n' "$FIRMWARE"
printf 'LAST_MARKER=%s\n' "$LAST_MARKER"
printf 'RESULT=%s\n' "$RESULT"
printf 'DETAILS=%s\n' "$DETAILS"
