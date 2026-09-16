"""Build/run the actual portable C controller without requiring an RTOS board."""
import argparse
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cc", default="gcc", help="gcc/clang or path to zig executable")
    p.add_argument("--check-arm-entry", action="store_true", help="Zig only: compile usermain against actual kernel headers")
    args = p.parse_args()
    compiler = str(Path(args.cc).resolve()) if Path(args.cc).is_file() else args.cc
    zig = Path(compiler).stem == "zig"
    command = [compiler, "cc"] if zig else [compiler]
    build = ROOT/"tests/host/build"
    build.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["ZIG_GLOBAL_CACHE_DIR"] = str(ROOT/".cache/zig")
    executable = build/("test_sleep.exe" if os.name == "nt" else "test_sleep")
    flags = ["-std=c99", "-Wall", "-Wextra", "-Werror"]
    subprocess.run(command+flags+["tests/host/test_sleep.c", "src/sleep/sleep_core.c",
                   "src/sleep/sleep_replay.c", "-o", str(executable)]+([] if zig else ["-lm"]),
                   cwd=ROOT, env=env, check=True)
    subprocess.run([str(executable)], cwd=ROOT, check=True)
    if args.check_arm_entry:
        if not zig:
            p.error("--check-arm-entry requires --cc pointing to Zig")
        includes = ["ra_cfg/fsp_cfg/bsp", "mtk3_bsp2", "mtk3_bsp2/config", "mtk3_bsp2/include",
                    "mtk3_bsp2/mtkernel/kernel/knlinc", ".", "ra_gen", "ra_cfg/fsp_cfg", "src",
                    "ra/fsp/inc", "ra/fsp/inc/api", "ra/fsp/inc/instances", "ra/arm/CMSIS_6/CMSIS/Core/Include"]
        defines = ["_RENESAS_RA_", "_RAFSP_EK_RA8P1_", "_RA_CORE=CPU0", "_RA_ORDINAL=1"]
        subprocess.run(command+flags+["-target", "thumb-freestanding-eabi", "-mcpu=cortex_m85"]
                       +["-I"+v for v in includes]+["-D"+v for v in defines]
                       +["-c", "src/usermain.c", "-o", str(build/"usermain.o")], cwd=ROOT, env=env, check=True)
        print("PASS: Cortex-M85 entry object with actual kernel headers (not a full board link)")


if __name__ == "__main__":
    main()
