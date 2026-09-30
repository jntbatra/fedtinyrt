# Apnea LCD dashboard firmware (Renesas RA8P1)

Live on-board dashboard for the SpO2-only INT8 apnea screener. Runs on the
EK-RA8P1 (Arm Cortex-M85), draws directly into the GLCDC framebuffer
(RGB565, 1024×600), and shows a big **APNEA / NORMAL** verdict, the live input
features, the model probability, and the measured balanced accuracy — updating in
real time.

It is built on top of the board's existing GLCDC display bring-up (the camera
example's display stack is reused; no display reconfiguration needed). The INT8
arithmetic is identical to the validated host reference, so board decisions are
bit-exact.

## Files
| file | what |
|---|---|
| `apnea_dash.c` | framebuffer drawing, bitmap font rendering, INT8 inference, serial command loop, free-running demo loop |
| `hal_entry.c` | entry point — launches the dashboard instead of the camera demo |
| `font8x8_basic.h` | 8×8 bitmap font (public domain, Daniel Hepper) |
| `CMakeLists.txt` | project build file (adds `libm` for the sigmoid) |
| `deploy.sh` | stage sources → build → flash, end to end |
| `flash_dash.jlink` | J-Link flash script |
| `live_demo.py` | host driver: stream a night of recorded data into the board over serial |

## Build & flash
Requires the Arm GNU toolchain and SEGGER J-Link. From the board project root
(the FSP/`cam2lcd` project these sources drop into):

```bash
export ARM_GCC_TOOLCHAIN_PATH=/path/to/arm-gnu-toolchain/bin
cmake --preset ReleaseCI
cmake --build --preset ReleaseCI
JLinkExe -device R7KA8P1AF -if SWD -speed 4000 -autoconnect 1 -CommanderScript flash_dash.jlink
```

`deploy.sh` automates staging + build + flash if you keep the same layout.

## Run
On reset the board free-runs its built-in windows and animates on its own — no host
needed. To inject a real overnight recording instead:

```bash
python3 live_demo.py --board --loop --subject tr03-0413 --delay 0
```

Serial commands (115200 8N1): `feat <10 floats>`, `dashreset`, `dashname <text>`,
`auton` (resume self-loop), `autooff` (stop, host drives).
