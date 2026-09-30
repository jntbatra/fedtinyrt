#!/usr/bin/env bash
# Deploy the apnea LCD dashboard firmware to the RA8P1 board.
# Run this from the Legion machine (where these files live). It stages the new
# sources into the cam2lcd project on the board host, builds, and flashes.
#
# Reversible: apnea_deploy's clean image is untouched; to go back to the camera
# demo, restore src/hal_entry.c (call mipi_csi_ep_entry) and rebuild, or reflash
# ~/tron/apnea_deploy/build/Release/apnea_deploy.elf.
set -euo pipefail

# Set these for your board host (the machine the RA8P1 is attached to):
#   BOARD_HOST=user@host   BOARD_KEY=~/.ssh/your_key
HOST=${BOARD_HOST:?set BOARD_HOST=user@host}
KEY=${BOARD_KEY:-~/.ssh/id_ed25519}
SSH="ssh -i $KEY -o IdentitiesOnly=yes"
STG="$(cd "$(dirname "$0")" && pwd)/src"
REMOTE=${BOARD_PROJECT:?set BOARD_PROJECT=/path/to/board/project}
TOOLCHAIN=${ARM_GCC_TOOLCHAIN_PATH:?set ARM_GCC_TOOLCHAIN_PATH=/path/to/arm-gnu-toolchain/bin}

echo "== 1/4  push new sources =="
scp -i "$KEY" -o IdentitiesOnly=yes \
    "$STG/apnea_dash.c" "$STG/font8x8_basic.h" "$STG/hal_entry.c" \
    "$HOST:$REMOTE/src/"

echo "== 1b/4 push updated host driver (adds --board mode) =="
scp -i "$KEY" -o IdentitiesOnly=yes \
    "$(dirname "$0")/live_demo.py" \
    "$HOST:$REMOTE/../apnea_deploy/tools/live_demo.py"

echo "== 2/4  copy model headers into cam2lcd (box-internal) =="
$SSH "$HOST" "cp $REMOTE/../apnea_deploy/src/apnea_model.h \
                 $REMOTE/../apnea_deploy/src/feature_normalization_mean.h \
                 $REMOTE/../apnea_deploy/src/feature_normalization_inverse_std.h \
                 $REMOTE/src/ && ls $REMOTE/src/ | grep -iE 'apnea|font|feature_norm|hal_entry'"

echo "== 3/4  build (ReleaseCI) =="
$SSH "$HOST" "cd $REMOTE && export ARM_GCC_TOOLCHAIN_PATH=$TOOLCHAIN && \
              rm -rf build/Release && cmake --preset ReleaseCI && \
              cmake --build --preset ReleaseCI 2>&1 | tail -15"

echo "== 4/4  flash =="
# find the produced .elf (project name may differ); adjust if needed
ELF=$($SSH "$HOST" "ls $REMOTE/build/Release/*.elf | head -1")
echo "flashing: $ELF"
$SSH "$HOST" "cd $REMOTE && printf 'h\nloadfile %s\nr\ng\nq\n' '$ELF' > flash_dash.jlink && \
              timeout 180 JLinkExe -device R7KA8P1AF -if SWD -speed 4000 -autoconnect 1 -CommanderScript flash_dash.jlink 2>&1 | tail -20"

echo "== done. Board should show the apnea dashboard on the LCD. =="
echo "Drive it from the board host:  /tmp/cincenv/bin/python ~/tron/apnea_deploy/tools/live_demo.py --board --subject tr03-0413 --delay 0.15"
