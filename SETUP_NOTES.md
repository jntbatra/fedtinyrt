# RA8P1 headless toolchain setup — verified findings

Working dir: `/home/jbatra/tron`. Host: **Fedora Linux 43**, x86_64, SELinux, user `jbatra`,
passwordless `sudo` available. NOT Ubuntu — **there is no `apt`/`dpkg`; use `dnf`/`rpm`.**

## Hardware: REAL and CONNECTED (verified)
- USB: `Bus 001 Device 002: ID 1366:1024 SEGGER J-Link`, plus `/dev/ttyACM0`.
- Probe is a **J-Link OB-RA4M2**, S/N `1081811618`, FW `compiled May 6 2026`, VTref=3.300V.
- Target genuinely present. Confirmed connect output:
  - `Found Cortex-M85 r1p1, Little endian.`
  - Dual core: **CPU0 = CM85 (primary)**, **CPU1 = CM33 (secondary)**.
  - `OFS bit=0x00000001` → primary CPU is CM85.
  - `Found SW-DP with ID 0x6BA02477`, TrustZone `Secure Debug: Enabled (SSD)`,
    `PACBTI extension: implemented`, I-Cache/D-Cache L1 16 KB.
- Board is almost certainly **Renesas EK-RA8P1**.

## CRITICAL CORRECTION: J-Link device name
- The guide's `-device R7KA8P1` **FAILS**: `The selected device "R7KA8P1" is unknown to this software version.`
- Bare `RA8P1` also fails.
- **Working name: `R7KA8P1AF`** (verified connects fully).
- J-Link's real RA8P1 names (from `strings libjlinkarm.so`):
  `R7KA8P1AD, R7KA8P1AF, R7KA8P1BD, R7KA8P1BF, R7KA8P1JF, R7KA8P1KF`
  - `R7KA8P1JF` resolves to dual-core `R7KA8P1JF_CPU0` (J/K variants have SiP flash).
- Use `-si SWD -speed 4000`.

## Step status
1. **Build system — DONE.** Installed via `dnf`: cmake 3.31.11, ninja 1.13.1, gcc/g++ 15.2.1,
   make 4.4.1. (`ninja-build` on Fedora; `build-essential` does not exist.)
2. **Arm GNU toolchain — DONE, verified.**
   - Download URL from the guide is **valid**.
   - File: `/home/jbatra/tron/arm-gnu-toolchain-13.2.rel1-x86_64-arm-none-eabi.tar.xz`
     (179,347,712 bytes).
   - sha256 `6cd1bbc1d9ae57312bcd169ae283153a9572bd6a8e4eeae2fedfbc33b115fdbb`
     = **matches ARM's official `.sha256asc`**.
   - **GOTCHA:** extraction dir is `arm-gnu-toolchain-13.2.`**`R`**`el1-x86_64-arm-none-eabi`
     (capital R) — the guide's lowercase `rel1` PATH export silently fails.
   - Bin dir: `/home/jbatra/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin`
   - Verified: `arm-none-eabi-gcc 13.2.1 20231009`; compiles `-mcpu=cortex-m85 -mthumb`
     AND `-mfloat-abi=hard -mfpu=fpv5-d16` OK.
3. **SEGGER J-Link — DONE, verified.**
   - Guide's V796 URL returns HTML, not a binary; V796 is ~5 yrs old. **Current = V9.78.**
   - Correct mechanism (verified working):
     `curl -sS -X POST -d "accept_license_agreement=accepted" -o JLink_Linux_V978_x86_64.rpm https://www.segger.com/downloads/jlink/JLink_Linux_x86_64.rpm`
   - Fedora needs the **`.rpm`**, not `.deb`. Size 76,431,038; md5 `312582ae1d8cbff957ad8d89659624e2`
     → **md5sum -c OK** (matches SEGGER's published hash).
   - Installed with `sudo dnf install -y ./JLink_Linux_V978_x86_64.rpm` → jlink 9.78.0-1,
     binaries in `/opt/SEGGER/JLink_V978/`, symlinks in `/usr/bin/` (`JLinkExe`, `JLinkGDBServer`).
   - Minor: `JLinkExe -Version` says "Unknown command line option -Version" but still prints banner.
     `JLinkCommander` does NOT exist (guide mentions only JLinkExe).
4. **RASC — NOT DONE. IN PROGRESS (delegated to subagent `agent-0`).**
   - Guide's `rasc_v5.3.0_linux_x86_64.tar.gz` → **HTTP 404, never existed.**
   - FSP 5.3.0 also **predates RA8P1 entirely**.
   - Real Renesas FSP releases: `https://github.com/renesas/fsp/releases`. Latest = **v6.6.0**.
     Assets include `setup_fsp_v6_6_0_rasc_v2026-07.xz.run`, `..._rasc_v2026-07.exe`,
     `..._e2s_v2026-07.xz.run`. (Older tags: v6.5.1, v6.5.0, v6.4.0, v6.3.1, v6.3.0.)
   - OPEN QUESTION: whether RASC runs **headless on Linux** at all, and which FSP first
     supports RA8P1. Subagent is downloading/inspecting the .xz.run.
5. Generate project — BLOCKED on step 4.
6. Build .elf — BLOCKED on step 5.
7. Flash — device name now known; can flash once a .elf exists.

## Environment gotcha for later commands
Each Bash call is a fresh shell — `export PATH=...` does NOT persist across calls.
Use absolute paths or prefix PATH inline:
`export PATH=/home/jbatra/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin:$PATH`


## RASC — RESOLVED (verified this session)
Guide's RASC section is entirely wrong (bad URL, nonexistent tarball, too-old FSP). Correct artifact:
- URL: `https://github.com/renesas/fsp/releases/download/v6.6.0/setup_fsp_v6_6_0_rasc_v2026-07.xz.run`
- Size downloaded OK = **1,298,663,272 bytes** (matches). Saved as `/home/jbatra/tron/rasc.run`.
- Makeself 2.5.0; payload = Eclipse p2 product. Extract WITHOUT running it:
  `tail -c +18745 rasc.run | xz -dc | tar -xf - -C /home/jbatra/tron/rasc_payload`
  (payload 1.4 GB; offset 18745 from Makeself header).
- Payload contains offline p2 repos at `install/repos/{ddsc,rasc,_categories}` and the installer
  Eclipse app (`./installer`, native ELF) with bundled JRE
  `plugins/org.eclipse.justj.openjdk.hotspot.jre.full.stripped.linux.x86_64_21.0.6.../jre/bin/java`.
- `installer.properties` gives: install root `~/renesas/ra/sc_v2026-07_fsp_v6.6.0`, profile `E2Profile`,
  product dir `eclipse`, required IUs `com.renesas.cdt.ddsc.standalone.configurator`,
  `com.renesas.e2studio.ra.ddsc.standalone.feature.feature.group`, `com.renesas.runtime.java`.
- Linux standalone RASC = feature `com.renesas.e2studio.ra.ddsc.standalone.feature` +
  binary fragment `com.renesas.cdt.ddsc.standalone.configurator.executable.gtk.linux.x86_64_26.7.0.R20260717-1302`
  (contains just `rasc` + `icon.xpm`). CLI plugin present: `com.renesas.cdt.ddsc.cli`; CMake generator plugin:
  `com.renesas.cdt.ddsc.project.idegeneric.cmake`.
- p2 director app (`org.eclipse.equinox.p2.director.app`) is NOT in the payload, so the classic
  `-application org.eclipse.equinox.p2.director` route FAILS ("could not be found in the registry").
- **WORKING HEADLESS ROUTE:** the Eclipse Installer itself supports CLI modes (verified strings from
  `com.codesourcery.installer` jar): `-install.silent` (silent install using defaults),
  `-install.console`, `-install.location <dir>`, `-install.data`, `-install.nofront`, `-install.status`,
  `-install.once`, `-install.D<prop>=<value>`, `-install.desc <props file>`.
  Command to try:
  `cd /home/jbatra/tron/rasc_payload && ./installer -install.silent -install.location /home/jbatra/renesas/ra/sc_v2026-07_fsp_v6.6.0`
  (Xvfb is installed: `xvfb-run -a` available if a display is demanded.)
- RASC CLI facts (from research, to re-verify): `rasc <command> [<subcommand>] [opts]`, long flags only,
  no `--version` (use `rasc version`); `rasc generate project-content --configuration <abs configuration.xml>
  [--devicefamily --buildconfiguration --compiler --toolchainversion]`.
- RASC-generated project is CMake+Ninja: `CMakeLists.txt`, `CMakePresets.json`, `cmake/gcc.cmake`,
  presets `DebugCI`/`ReleaseCI`, needs env `RASC_EXE_PATH`, `ARM_GCC_TOOLCHAIN_PATH`, `NINJA_PROGRAM=ninja`.

## RASC 6.6.0 headless — WORKING (verified this session)
### The CLI invocation (this is the key finding)
The `rasc` launcher starts the GUI unless you force the CLI application id:
```
R=/home/jbatra/renesas/ra/sc_v2026-07_fsp_v6.6.0/eclipse
xvfb-run -a $R/rasc -nosplash -application com.renesas.platform.cli.cliapplication <args>
```
- App id comes from `com.renesas.platform.cli` plugin.xml extension `cliapplication`.
- `rasc version` (guide/my earlier attempt) starts the GUI and hangs -> exit 124. Do NOT use it.
- Help style is `help <cmd>` / `help <cmd> <subcmd>`, NOT `--help` (`generate project-content --help` => "Unrecognized option: --help").
- Real command surface: `version`, `packs {install|info|extract}`, `generate
  {project-content|partition|smart-bundle|smart-bundle-partition|solution-bundle}`,
  `project {import|remove}`, `ease`, and legacy `--generate`, `--partition`,
  `--gensmartbundle`, `--gensmartbundleandpartition`, `--gensolutionbundle`,
  `--extractsupportfiles`.
- **There is NO project-create command. Creating a *new* project is GUI-wizard-only.**
  `generate project-content` only regenerates content for an EXISTING configuration.xml.
- `help generate project-content`:
  `Usage: generate project-content --configuration <ABSOLUTE configuration.xml>
   [--devicefamily <FAMILYID>] [--buildconfiguration <BUILDCONFIGNAME>]
   [--compiler <COMPILERTYPE>] [--toolchainversion <VERSION>]`
- `help project import`: `import <project path>` / `import -all <directory path>`.
- FSP packs are ALREADY present, no download needed:
  `/home/jbatra/renesas/ra/sc_v2026-07_fsp_v6.6.0/internal/projectgen/ra/packs/*.pack`
  incl. `Renesas.RA.6.6.0.pack`, `Renesas.RA_mcu_ra8p1.6.6.0.pack`,
  `Renesas.RA_board_ra8p1_ek.6.6.0.pack`, `Arm.CMSIS6.6.1.0+fsp.6.6.0.pack`.
  => the guide's separate "install packs" download is unnecessary.

### Generate a project (WORKING, verified)
Project dir: `/home/jbatra/tron/my_ra8_project`
1. Get a starter configuration.xml (no local starter ships with FSP). Used:
   `https://raw.githubusercontent.com/renesas/ra-fsp-examples/master/application_projects/r01an7881/Developing_with_RA8_Dual_Core_MCU/ek_ra8p1_dualcore/ek_ra8p1_dualcore_CPU0/configuration.xml`
   (176,139 B; EK-RA8P1, target R7KA8P1KFLCAC, board `ra8p1_ek`.)
2. The example is written for FSP 6.2.0 but only 6.6.0 packs are installed, so
   `generate` fails with `Error extracting CMSIS components` +
   `Failed to locate component "..." V6.2.0 ... in any software packs`.
   FIX (verified working): `sed -i 's/6\.2\.0/6.6.0/g' configuration.xml`
   (that rewrites both `<option key="#FSPVersion#">` and the 25 `<component version=...>`
   /`<originalPack>...6.2.0.pack` entries; all resulting pack names exist locally).
   Pre-edit backup kept at `/tmp/configuration.xml.fsp620.bak`.
3. `cd /home/jbatra/tron/my_ra8_project && xvfb-run -a $R/rasc -nosplash -application
   com.renesas.platform.cli.cliapplication generate project-content --configuration
   /home/jbatra/tron/my_ra8_project/configuration.xml`  -> exit 0, ~40 s,
   "Components have been added to, or removed from the project."
4. Produced: `ra/`, `ra_cfg/`, `ra_gen/` (hal_data.c, main.c, vector_data.c, pin_data.c...),
   `script/fsp.lld`, `memory_regions.lld`, `bsp_linker_info.h`, `src/hal_entry.c`,
   `.clangd`, `.api_xml`, `.settings/standalone.prefs`.
   NOTE: `.settings/standalone.prefs` contains
   `com.renesas.cdt.ddsc.project.standalone.projectgenerationoptions/ideProjectType=CMAKE`
   -> the standalone RASC *does* target CMake projects.
5. **CMakeLists.txt / CMakePresets.json / cmake/gcc.cmake are NOT produced by
   `generate project-content`.** They come from FreeMarker templates
   (`template/CMakeLists.txt.ftl`, `template/CMakePresets.json.ftl`, `template/cmake/gcc.cmake`,
   `template/cmake/GeneratedSrc.cmake.ftl`, ... inside
   `eclipse/plugins/com.renesas.cdt.ddsc.project.idegeneric.cmake_1.0.200.v20260717-1117.jar`;
   toolchain variants gcc/llvm/ccrh/iar). Missing piece: which command/flag renders them.
   NEXT THING TO TRY: `rasc project import /home/jbatra/tron/my_ra8_project`, then re-run
   `generate project-content`; if still absent, pass
   `--compiler gcc --toolchainversion 13.2.1` (config says `#SELECTED_TOOLCHAIN#=clang_arm`,
   `#ToolchainVersion#=18.1.3`) and/or inspect
   `com.renesas.cdt.ddsc.project.idegeneric.cmake...CMakeFilesGeneratorFactory` /
   `CMakeProjectConnectionClient` for the trigger.

### RASC install (recap, verified)
- Guide's step-4 URL/tarball is fabricated (404) and FSP 5.3.0 predates RA8P1.
- Correct: `setup_fsp_v6_6_0_rasc_v2026-07.xz.run` (1,298,663,272 B) -> `/home/jbatra/tron/rasc.run`.
- Extracted payload -> `/home/jbatra/tron/rasc_payload`; silent headless install via
  `cd /home/jbatra/tron/rasc_payload && ./installer -install.silent -install.location
   /home/jbatra/renesas/ra/sc_v2026-07_fsp_v6.6.0 -consolelog` (exit 0).
- Needs `xorg-x11-server-Xvfb` + gtk3/gtk4 (`dnf install`); the p2-director route does NOT work.
- RASC workspace/log: `/home/jbatra/.renesas/fspscws/.metadata/.log` (read this on failure).

### J-Link flashing (device name correction stands)
`JLinkExe -device R7KA8P1AF -if SWD -speed 4000 -autoconnect 1 -CommanderScript flash.jlink`
(guide's `-device R7KA8P1` fails: unknown device.)

## CMake-scaffold blocker — bytecode findings (verified 2026-09-17)

### `generate project-content --compiler` accepted values
`--compiler` is `CompilerType.valueOf(...)`, exact enum names only. Valid:
`ARMv6, GCCRX, CCRX, LLVMARM, CCRH, IAR_RX, IAR_RH850, GHS_RH850, LLVMRISCV, GHS_ARM`.
- `--compiler gcc` => `IllegalArgumentException: No enum constant ...CompilerType.gcc`
  (logged in `.metadata/.log`, then compilerType stays null).
- **There is no GNU-ARM enum constant.** `ARMv6` = Arm Compiler 6 (produced
  `fsp_gen.scat` + `memory_regions.scat`). `clang_arm`/`LLVMARM` => `.lld`.
- With compilerType left null, `SwpProjectGenAssist.addProjectContents:85` NPEs on
  `getCompilerType().name()` and generation FAILS.
- `--toolchainversion 13.2.1` is accepted (recorded in
  `.settings/standalone.prefs` as `...contentgen.options/options/toolchainversion=13.2.1`).

### `ToolchainCMakeGeneratorFactory` (in com.renesas.cdt.ddsc.project.idegeneric.cmake jar)
`CompilerType -> IToolchainCMakeGenerator`:
- `ToolchainGccCMakeGenerator`: template `cmake/gcc.cmake`, env var `ARM_GCC_TOOLCHAIN_PATH`,
  clangd query-driver `--query-driver=${env:ARM_GCC_TOOLCHAIN_PATH}*`, intellisense mode `gcc-arm`,
  VSCODE_COMPILER `/${env:ARM_GCC_TOOLCHAIN_PATH}/arm-none-eabi-gcc`.
- `ToolchainLlvmCMakeGenerator`, `ToolchainIarCMakeGenerator`, `ToolchainRh850IarCMakeGenerator`,
  `ToolchainCcrhCMakeGenerator`.
Toolchain-id display map (`getToolchainIds`): `com.renesas.cdt.managedbuild.gnuarm.toolchain.` =>
"GCC Toolchain for ARM"; `com.renesas.cdt.managedbuild.llvm.arm.`; `iar.arm.toolchain`;
`iar.rh850.toolchain`; `com.renesas.cdt.managedbuild.renesas.ccrh.`.

### Where the CMake files come from (trigger identified, still not reachable from CLI)
`com.renesas.cdt.ddsc.project.idegeneric.cmake` plugin declares, on extension point
`com.renesas.cdt.ddsc.project.idegeneric.types`:
- projecttype id `com.renesas.cdt.ddsc.project.idegeneric.cmake.projecttype` (name "CMake")
  with filetypes `.vscode.cmakekits`, `.vscode.settings`, `.vscode.tasks`, `.vscode.launch`,
  `.generatedfiles` (=> `CMakeFilesGeneratorFactory`), `.regeneratedfiles`
  (=> `CMakeRegeneratedFilesFactory`), `.iar.ewp`, ...
- `CMakeFilesGeneratorFactory extends AbstractIdeProjectFreemarkerFileGeneratorFactory`;
  `getFreemarkerTemplates()` renders: `CMakeLists.txt` (or `SolutionCMakeLists.txt`),
  `Config.cmake`, `CMakePresets.json`, `cmake/<toolchain>.cmake`, `cmake/prebuild.cmake`,
  `README.md`. Data model supplies `PROJECT_NAME`, `RASC_EXE_PATH`, `RASC_DEVICE_FAMILY`,
  `toolchainFilePath`, `TOOLCHAIN_PATH_VAR_NAME`.
- Also registers `CMakeProjectConnectionClient` on extension point
  `com.renesas.cdt.ddsc.projectconnection.projectConnectionClient` (runs on project
  connect/import) and `CmakeBuildInfoFactory` on `...idegeneric.buildInfoFactory`.
=> These file generators are driven by the **IDE project-generation machinery**, which the
`generate project-content` CLI command does NOT call. `.settings/standalone.prefs` already has
`...projectgenerationoptions/ideProjectType=CMAKE`, so the *setting* is right; the *invoker* is
missing (wizard-only).
- Templates extracted for reference: `/tmp/cmaketpl/template/` (CMakeLists.txt.ftl,
  CMakePresets.json.ftl, Config.cmake.ftl, cmake/{gcc,llvm,ccrh,iar,iar_rh850}.cmake,
  cmake/GeneratedCfg.cmake.ftl, cmake/GeneratedSrc.cmake.ftl, cmake/prebuild.cmake.ftl,
  README.md.ftl, SolutionCMakeLists.txt.ftl).
- `rasc ... project import <path> -data <ws>` => exit 0, **no output at all** (7-byte log = "EXIT=0"),
  and it did NOT create CMakeLists.txt.

### Decision pending
If the CLI genuinely cannot render the CMake scaffold, fall back to rendering the 6 FreeMarker
templates by hand from the extracted `template/` dir (everything else — FSP sources, linker
script, .settings — is already produced by RASC). Note `gcc.cmake` + flags come from
`Config.cmake`/`GeneratedCfg.cmake`/`GeneratedSrc.cmake`, so check which FSP data feeds
`RASC_CMAKE_C_FLAGS`.

## Handoff snapshot (2026-09-17) — approaching build

### Where the project is
`/home/jbatra/tron/my_ra8_project` — RASC content generation WORKS and is current.
Last generate (exit 0):
```
R=/home/jbatra/renesas/ra/sc_v2026-07_fsp_v6.6.0/eclipse
cd /home/jbatra/tron/my_ra8_project
xvfb-run -a $R/rasc -nosplash -application com.renesas.platform.cli.cliapplication \
  generate project-content --configuration /home/jbatra/tron/my_ra8_project/configuration.xml --compiler LLVMARM
```
- `--compiler LLVMARM` (clang_arm) is what produces the **GNU-ld-compatible** linker scripts:
  `script/fsp.lld` (106 B shim: `INCLUDE memory_regions.lld` + `INCLUDE fsp_gen.lld`),
  `memory_regions.lld` (root), `fsp_gen.lld` (root, `ENTRY(Reset_Handler)`, MEMORY+SECTIONS).
  (ARMv6 produced `.scat` = Arm-Compiler scatter format — NOT usable by GNU ld.)
- `.settings/standalone.prefs` now records `...defaultlinkerscript=script/fsp.lld`. Good.
- Stale `.scat` files still lying around at root (from the ARMv6 experiment) — ignore/delete.

### The CMake scaffold is NOT produced by any CLI command (devised workaround)
RASC's `CMakeFilesGeneratorFactory` templates live in
`eclipse/plugins/com.renesas.cdt.ddsc.project.idegeneric.cmake_1.0.200.v20260717-1117.jar`,
extracted for reference at `/tmp/cmaketpl/template/`:
`CMakeLists.txt.ftl`, `CMakePresets.json.ftl`, `Config.cmake.ftl`,
`cmake/{gcc,llvm,ccrh,iar,iar_rh850}.cmake` (static files), `cmake/GeneratedCfg.cmake.ftl`,
`cmake/GeneratedSrc.cmake.ftl`, `cmake/prebuild.cmake.ftl`, `README.md.ftl`,
`SolutionCMakeLists.txt.ftl`. They are rendered only by the GUI project-creation wizard
(`GenericIdeProjectGenerator`), NOT by `generate project-content`. CLI `project import` = no-op.
**Decision: hand-write a faithful scaffold** — copy `cmake/gcc.cmake` verbatim (it is a static
file, correct for the GCC toolchain) and hand-write `CMakeLists.txt` with the flag/include/
define/source data derived below. This fills an IDE-file gap; all FSP content still comes from RASC.

### GROUND-TRUTH build data (extracted from the upstream example's `.cproject`, /tmp/cpu0.cproject)
Source: `ra-fsp-examples` → `application_projects/r01an7881/Developing_with_RA8_Dual_Core_MCU/
ek_ra8p1_dualcore/ek_ra8p1_dualcore_CPU0/.cproject` (downloaded to /tmp/cpu0.cproject).
That example uses toolchain **clang_arm 18.1.3**; values below are its exact settings.

Includes (in order):
```
src  .  ra/fsp/inc  ra/fsp/inc/api  ra/fsp/inc/instances
ra/arm/CMSIS_6/CMSIS/Core/Include  ra_gen  ra_cfg/fsp_cfg/bsp  ra_cfg/fsp_cfg
```
Defines: `_RENESAS_RA_`, `_RA_CORE=CPU0`, `_RA_ORDINAL=1`
Linker: script `script/fsp.lld`; `-L script`, `-L .` (this is how the shim's `INCLUDE`s resolve);
libraries `crt0`, `c++abi`; `-Wl,-z,norelro`; `--gc-sections` on; `-nostartfiles` OFF in that example.
Compile: `-mcpu=cortex-m85 -mthumb -mfloat-abi=hard -mfpu=fpv5-d16`,
`-fmessage-length=0 -funsigned-char -g3 -fdata-sections -fno-strict-aliasing`,
opt = `speedCodeSize` (−Os), C std c99, C++ c11,
`-flax-vector-conversions -fshort-enums -fno-unroll-loops` (clang-only `-flax-vector-conversions`
must be DROPPED for GCC).
The example's link-order list == the project's buildable sources (src/app files, ra_gen/*, FSP
`r_ioport`, bsp/*, startup, system, board_init, board_leds).

Exact source list my project needs (from `find ra ra_gen src -name '*.c'`):
```
ra/board/ra8p1_ek/board_init.c
ra/board/ra8p1_ek/board_leds.c
ra/fsp/src/bsp/cmsis/Device/RENESAS/Source/startup.c
ra/fsp/src/bsp/cmsis/Device/RENESAS/Source/system.c
ra/fsp/src/bsp/mcu/all/{bsp_clocks,bsp_common,bsp_delay,bsp_group_irq,bsp_guard,bsp_io,bsp_ipc,bsp_irq,bsp_macl,bsp_ospi_b,bsp_register_protection,bsp_sbrk,bsp_sdram,bsp_security}.c
ra/fsp/src/bsp/mcu/ra8p1/bsp_linker.c
ra/fsp/src/r_adc_b/r_adc_b.c
ra/fsp/src/r_ioport/r_ioport.c
ra/fsp/src/r_ipc/r_ipc.c
ra/fsp/src/r_rtc/r_rtc.c
ra_gen/{common_data,hal_data,main,pin_data,vector_data}.c
src/hal_entry.c
```
No `.S`/`.s` files. `src/hal_entry.c` is the RASC template (has TrustZone + multicore branches) —
it is a complete, linkable `hal_entry()`; the example's real app files (rtc.c/ipc_cpu0.c/…) are
NOT part of a plain RASC generate and are not being added.

### OPEN RISK to check before/while building
- TrustZone: project has `.secure_azone`/`.secure_rzone`; `hal_entry.c` uses
  `BSP_TZ_SECURE_BUILD`. If `ra_cfg/fsp_cfg/bsp/bsp_cfg.h` sets `BSP_TZ_SECURE_BUILD 1`, the build
  needs `-mcmse` and the `secure.o` handling from the template. CHECK THIS FIRST.
- Multilib: arm-none-eabi-gcc 13.2.1 at
  `/home/jbatra/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin` (capital R).

### Exact build command to attempt (presets, not the guide's `-DCMAKE_TOOLCHAIN_FILE=../gcc.cmake`)
All env inlined (fresh shell per Bash call):
```
cd /home/jbatra/tron/my_ra8_project
export PATH=/home/jbatra/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin:$PATH
export ARM_GCC_TOOLCHAIN_PATH=/home/jbatra/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin
export RASC_EXE_PATH=/home/jbatra/renesas/ra/sc_v2026-07_fsp_v6.6.0/eclipse/rasc
cmake --preset DebugCI && cmake --build --preset DebugCI
```
Expected `.elf` under `build/Debug/` named `my_ra8_project.elf`.

### Flash (device name correction stands)
```
JLinkExe -device R7KA8P1AF -if SWD -speed 4000 -autoconnect 1 -CommanderScript flash.jlink
```
with `flash.jlink`: `h` / `loadfile <elf>` / `r` / `g` / `q`. Success = J-Link prints `O.K.`
after download + verify. Board = EK-RA8P1; probe J-Link OB-RA4M2 S/N 1081811618.
This configuration.xml is the dual-core **CPU0** image (CM85, primary) — flashing CPU0 is correct.

### Honest scorecard of the user's 7 guide steps (for the final answer)
1. WRONG host pkg cmd — Fedora, `dnf` not `apt`; no `build-essential`. Done otherwise.
2. URL valid, hash verified — but extract dir is capital-`R` `13.2.Rel1` (guide's PATH silently fails).
3. WRONG — V796 URL dead (returns HTML); used V978 **.rpm** (md5 verified). Done.
4. WRONG entirely — guide URL 404, FSP 5.3.0 predates RA8P1; used FSP 6.6.0 `setup_fsp_v6_6_0_rasc_v2026-07.xz.run`.
5. PARTLY WRONG — `rasc -g` is not a thing; there is no CLI project-create; `generate project-content`
   needs an existing configuration.xml; CMake files not emitted (hand-written instead).
6. WRONG shape — `-DCMAKE_TOOLCHAIN_FILE=../gcc.cmake` doesn't match the preset layout.
7. PARTLY WRONG — `-device R7KA8P1` unknown; must be `R7KA8P1AF`.

---

## CLOSED — build and flash both verified (2026-09-17)

### Build: SUCCESS
```
cd /home/jbatra/tron/my_ra8_project
export PATH=/home/jbatra/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin:$PATH
export ARM_GCC_TOOLCHAIN_PATH=/home/jbatra/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin
cmake --preset DebugCI && cmake --build --preset DebugCI
```
30/30 objects compiled, linked to `build/Debug/my_ra8_project.elf`.
- `arm-none-eabi-size`: text 5456 / data 0 / bss 4326.
- `readelf -h`: Entry `0x0200009f` == `Reset_Handler (0x0200009e) | thumb`.
- `nm`: `__Vectors` @ `0x02000000` (SP word `0x22001000` = top of the 4 KB `g_main_stack`;
  Reset word `0x0200009f`), `g_vector_table` @ `0x02000040` (16 Cortex fixed vectors + 22 app
  vectors = 0x98 bytes in `__flash_vectors$$`). Layout is correct.
- GNU ld accepts the RASC-generated `.lld` verbatim (only benign warnings: `-z norelro ignored`,
  `_close/_lseek/_read/_write not implemented` from `--specs=nosys.specs`).
- TrustZone risk above: RESOLVED — not a secure build (`BSP_TZ_SECURE_BUILD` is 0 because
  `_RA_TZ_SECURE` is undefined), so no `-mcmse` needed.

### Flash: SUCCESS — J-Link printed `O.K.`
```
JLinkExe -device R7KA8P1AF -if SWD -speed 4000 -autoconnect 1 -CommanderScript flash.jlink
```
`J-Link: Flash download: Bank 0 @ 0x02000000: 1 range affected (6144 bytes)` + Bank 1 @ 0x02C9F020
(16 bytes, the option-setting bytes) → `O.K.` after Program & Verify, then reset + go.

### Running state verified (halt + regs, then resumed)
After `r`/`g`, halting shows `PC = 0x020000A8` — the `b .` idle loop at the end of `Reset_Handler`
(right after `bl main` returned), `SP = 0x22000FF8` (= stack top `0x22001000` minus the 8-byte
`push {r3,lr}`), `LR = 0x020010CF` (stale return into `main`). So the core is executing OUR image.
`src/hal_entry.c` is the empty RASC template, so `main` returns and the core idles — that is the
expected behavior of a plain generated project; no application logic was requested.
---

## cam2lcd — MIPI CSI-2 camera → LCD passthrough (2026-09-17)

Project lives in `/home/jbatra/tron/cam2lcd` (separate from `my_ra8_project`).
Source set = Renesas official `ek_ra8p1` `mipi_csi` example: OV5640 over CSI-2 → VIN →
SDRAM frame buffers → GLCDC → MIPI-DSI panel. 1024x600, the panel's native mode.

### The 32 KB code-MRAM wall (why .text is in SRAM)

Only the first **32 KB** of code MRAM is secure/decoded on this part.
`R_PSCU.CFSAMONA` @ `0x40204030` reads `0x00008000` (32 KB), read-only at runtime;
widening it is RDPM/RFP-proprietary. Anything past `0x02008000` traps.

Workaround — `.text`/`.rodata` relinked into SRAM at `0x22008000`, via two hand edits to
RASC-generated root files:

- `memory_regions.lld`: `RAM_LENGTH 0x8000`, `FLASH_LENGTH 0x8000`,
  `SRAM_CODE_START 0x22008000`, `SRAM_CODE_LENGTH 0x80000`
- `fsp_gen.lld`: new `SRAM_CODE (rx)` region; `__flash_readonly$$`'s `> FLASH` → `> SRAM_CODE`

Vectors must stay at `0x02000000` (nothing ever writes `SCB->VTOR`); RAM stays at
`0x22000000` for the reset-time stack. SDRAM bss at `0x68000000`.

**Gotchas:**
- Re-running RASC **wipes both `.lld` edits** — reapply after any regeneration.
- ninja does not track the `.lld` files, so a relink needs the ELF deleted first:
  `rm -f build/Release/cam2lcd.elf build/Release/cam2lcd.map` before building.

### Why the display was dark (root cause, fixed)

Not a hardware fault, not a dead GLCDC. `mipi_csi_ep_entry()` → `vin_resolution_set()`
blocked at `while (!APP_CHECK_DATA) {;}` waiting for the user to type a resolution on the
terminal **before** `glcdc_init()` was ever called. So GLCDC registers read 0
(uninitialised) and `g_display_ctrl` was all zeros.

Note: `CMakeLists.txt:51` sets **`USE_VIRTUAL_COM=1`**, so "terminal" = the SCI serial port
(`TERM_INIT()` = `serial_init()`); there is **no SEGGER RTT code in the ELF at all**
(`grep -c RTT` over the full disassembly = 0). The menu prompt therefore appeared on the
serial port, and the display never came up unless the host typed a resolution.

Fix — `src/user_config.h`, added after `AWB_MANUAL_ENABLE`:
```c
/* Resolution used at start-up without waiting for terminal input.
 * 1 = RES_1024x600, 2 = RES_VGA, 3 = RES_QVGA, 0 = keep the terminal prompt.
 * Keep this a plain number: e_image_resolution is an enum and would evaluate to 0 in #if. */
#define AUTO_START_RESOLUTION       (1)
```
That comment matters: `#if (RES_1024x600 == RESET_VALUE)` silently takes the **wrong**
branch because enum identifiers evaluate to 0 inside `#if`.

`src/mipi_csi.c`, in `vin_resolution_set()`: the `user_input` declaration and the
prompt/read block are wrapped in `#if (AUTO_START_RESOLUTION == RESET_VALUE)`, with
`#else` → `input_value = (uint8_t) AUTO_START_RESOLUTION;`. Everything downstream
(`input_value < RES_MAX && > 0` validation, `glcdc_init()`, memset of the three VIN
buffers, `vin_scale_image`, `vin_camera_start(&g_vin_cfg_run_time)`,
`g_is_set_resolution = true`) is untouched. `camera_open()` already loads the live OV5640
config and `camera_mode_selection()` is non-blocking, so nothing else needed changing.

Set `AUTO_START_RESOLUTION` back to `0` to restore the interactive prompt.

### Build

```bash
cd /home/jbatra/tron/cam2lcd
export PATH=/home/jbatra/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin:$PATH
export ARM_GCC_TOOLCHAIN_PATH=/home/jbatra/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin
rm -f build/Release/cam2lcd.elf build/Release/cam2lcd.map   # force relink (see gotcha)
cmake --build --preset ReleaseCI
```
`arm-none-eabi-size`: text **47468** / data 2424 / bss 6152356.
Program headers: vectors `0x02000000`; `.data` VMA `0x22000040` / LMA `0x0200007c`;
zero-init `0x22000000`; `__flash_readonly$$` R E @ `0x22008000` len `0x0b8f0`;
SDRAM bss @ `0x68000000`. `vin_resolution_set` is static and inlined into
`mipi_csi_ep_entry` (`0x2200bd24`), so it has no `nm` symbol — expected.

### Flash + probe

`flash_probe.jlink`:
```
h
loadfile /home/jbatra/tron/cam2lcd/build/Release/cam2lcd.elf
r
g
Sleep 5000
h
mem32 0xE000ED08 1
regs
mem32 0x22001F08 4
mem32 0x40343000 2
mem32 0x40343100 5
mem32 0x40343200 5
mem32 0x40343440 2
SaveBin /home/jbatra/tron/cam2lcd/vinC.bin 0x68000000 0x1000
q
```
Run:
```bash
timeout 200 /usr/bin/JLinkExe -device R7KA8P1AF -if SWD -speed 4000 -autoconnect 1 \
  -CommanderScript /home/jbatra/tron/cam2lcd/flash_probe.jlink
```

GLCDC register map used (from
`ra/fsp/src/bsp/cmsis/Device/RENESAS/Include/R7KA8P1KF_core0.h`):
`R_GLCDC_BASE = 0x40342000`; `BG` @ +0x1000, `GR[0]` @ +0x1100
(`VEN` +0, `FLMRD` +4, `FLM1` +8, `FLM2` +0xC, `FLM3` +0x10), `GR[1]` @ +0x1200,
`GAM` @ +0x1300, `OUT` @ +0x13C0, `TCON` @ +0x1400, **`SYSCNT` @ +0x1440**.
Earlier probe4/5/6 used wrong offsets — `0x40342100` is CLUT space and `SYSCNT` is at
`0x40343440`, not `0x40342440`.
`glcdc_instance_ctrl_t` = `{ display_state_t state; void (*p_callback)(...); void *p_context;
const display_cfg_t *p_cfg; }` (16 bytes, matches `nm` size of `g_display_ctrl`).

### Verification evidence — camera frames reach the LCD scanout

- `VTOR = 0x02000000`; PC = `0x2200BC9C` in SRAM, IPSR = 015 (inside an ISR), no fault.
- `g_display_ctrl` @ `0x22001F08` = `00000002 2200B9A9 00000000 22001CA8`
  → **state = 2 = `DISPLAY_STATE_DISPLAYING`**, callback = `glcdc_vsync_isr` (`0x2200B9A9`).
- `BG` @ `0x40343000` = `00010001` (EN=1, VEN=1), `MON` = `027B0536`.
- `GR[0]` @ `0x40343100` = `00000000 00000001 00000003 6812C000` / `08000000`
  → **`FLMRD` bit0 `RENB` = 1** (frame-buffer read enabled), `FLM1` = 3 (read active),
  **`FLM2` = `0x6812C000` = `vin_image_buffer_2`**.
- `GR[1]` all zero — layer 2 unused. `DISPLAY_FRAME_LAYER_1 == 0`, so the app's
  `R_GLCDC_BufferChange(..., DISPLAY_FRAME_LAYER_1)` writes `GR[0]`.
- `SYSCNT` @ `0x40343440` = `00000007 00000007`.
- `CFSR`/`HFSR` @ `0xE000ED28` = 0 / 0 — no fault latched.
- `g_is_set_resolution` (`0x220028A8`, byte) = 1; `g_image_width` = `0x0400` = 1024,
  `g_image_height` = `0x0258` = 600.

Liveness probe (`probe8.jlink`, ran OK) — scanout follows the newest capture buffer:
- 1st halt: `0x4034310C` (= `GR[0].FLM2`) = `68000000`, `gp_next_buffer`
  (`0x220028B0`) = `68000000` (= `vin_image_buffer_3`).
- `g`, Sleep 250, halt: `0x4034310C` = `6812C000`, `gp_next_buffer` = `6812C000`
  (= `vin_image_buffer_2`).

So GLCDC's live scanout address tracks the rotating VIN frame buffers → a continuously
updating camera → SDRAM → GLCDC stream, not a static image.

Frame buffer layout (`FLASH` laid out 1024x600, `0x12C000` apart):
`vin_image_buffer_1` = `0x68258000`, `_2` = `0x6812C000`, `_3` = `0x68000000`.

### Caveat — not visually confirmed

The LCD was never seen by the agent. The register evidence proves the camera stream
reaches the LCD scanout generator, but only the operator can confirm a visible picture.

### Artifacts on disk (`/home/jbatra/tron/cam2lcd/`)

`flash.jlink`, `flash_verify.jlink`, `flash_probe.jlink`, `probe4.jlink`, `probe5.jlink`,
`probe6.jlink`, `probe8.jlink`, `run.jlink`, `vin1.bin`, `vinA.bin`, `vinB.bin`, `vinC.bin`,
`build/Release/cam2lcd.elf`, `cam2lcd.map`.

`run.jlink` (`h` / `r` / `g` / `q`) was the last command run — the board was reset and left
running the new firmware.

### Optional next steps (not attempted)

- Widen the secure code area properly via RDPM/RFP CLI instead of the SRAM relink.
  Do **not** attempt option-byte writes unattended — OFS/OTP read `0xFFFFFFFF` here.
- Feed the captured `vinC.bin` (SDRAM dump) to a host-side decoder to eyeball a frame
  without the panel.
## cam2lcd follow-up — auto-exposure fix + serial/I2C evidence (2026-09-17)

### Fix 2 — near-black picture: the example disables sensor auto-exposure

Reading back the OV5640 over I2C showed the example's register table programs
`AEC_PK_MANUAL_REG` (0x3503) = **0x07**: auto-exposure *and* auto-gain both forced
manual/off, analogue gain pinned at `AEC_REAL_GAIN_L_REG` = 0x20 (~2x), exposure
`0x3500/1/2` = `00 FF 00`. In anything but bright light that produces a near-black
frame. AWB is left automatic (`AWB_MAN_CTRL` = 0), so only exposure/gain needed fixing.

`src/user_config.h`:

```c
/* DIAGNOSTIC: force the sensor's colour-bar test pattern at start-up instead of the
 * live camera image. Set back to 0 to return to live camera capture. */
#define FORCE_TEST_PATTERN          (0)

/* The example's OV5640 register table disables auto-exposure and auto-gain
 * (AEC_PK_MANUAL 0x3503 = 0x07) and pins the analogue gain at about 2x, which makes the
 * captured image very dark unless the scene is brightly lit. Setting this to 1 gives
 * exposure and gain back to the sensor's own control loops. */
#define CAMERA_AUTO_EXPOSURE        (1)
```

`src/mipi_csi.c`, in `mipi_csi_ep_entry()` right after the `camera_open` error check:
write `0x00` to `AEC_PK_MANUAL_REG`, read it back, print it. So after boot the SCI
terminal shows `AEC/AGC auto control: 0x3503 = 00 (expect 00)`.

Measured on hardware, same scene and camera, straight from the SDRAM frame buffers:

| frame | mean luma /187 | near-black pixels | distinct colours |
|---|---|---|---|
| before (`frame2.bin`) | 12.7 | 43.7 % | 2,739 |
| after (`ae2.bin` / `final.bin`) | **85.3** / 84.8 | **0.0 %** | 10,550 / 10,375 |

~6.7x brighter, zero near-black pixels. A coarse 16x10 block luma map of `ae2.bin`
shows a real scene (bright band across the lower ~20 %, mid-dark upper region).

### Capturing the SCI log without a terminal emulator

`/dev/ttyACM0` is the J-Link OB virtual COM port; the firmware's serial terminal runs
at 115200 (`src/SERIAL_TERM/serial.h:101`). Capture it in the background while J-Link
resets/runs the target:

```bash
stty -F /dev/ttyACM0 115200 raw -echo -onlcr
( timeout 25 cat /dev/ttyACM0 > /tmp/serial.log ) &
sleep 1
timeout 90 /usr/bin/JLinkExe -device R7KA8P1AF -if SWD -speed 4000 -autoconnect 1 \
    -CommanderScript fl.jlink
wait
cat -v /tmp/serial.log
```

Result: banner + `Select the resolution:` + `Select Camera Mode:` with **no FAILED
messages** — `camera_open`, `glcdc_init` and `vin_camera_start` all succeed.

### I2C readback evidence (sensor alive, writes land)

```
SENSOR ID = 56 40  (expect 56 40),  reg 0x503D = 00 (expect 80)
AUTO-WRITTEN 0x3808..0x380B = 04 00 02 58  (expect 04 00 02 58)
AEC/AGC auto control: 0x3503 = 00 (expect 00)
```

- OV5640 chip ID (`0x300A/0x300B`) = `56 40` — correct part, responding on I2C.
- The init table's window registers read back exactly `04 00 02 58` (= 1024x600), so
  register writes genuinely land.
- **Known quirk:** `0x503D` reads back `00` after writing `0x80`, so the colour-bar
  test pattern never takes effect on this part; all three frame buffers showed 0.00 %
  pattern match at every byte offset searched. Since ordinary writes work and 0x3503
  reads back correctly, 0x503D appears to be special/reserved here. The `FORCE_TEST_PATTERN`
  diagnostic switch remains in the source but is inert (0).

### Live scanout confirmation (final probe on the running board, `chk.jlink`)

```
22001F08 = 00000002 2200B9A9 00000000 22001CA8   <- g_display_ctrl: state=2 DISPLAYING
40343000 = 00010001 027B0536                     <- BG: EN=1, VEN=1
40343100 = 00000000 00000001 00000003 68000000   <- GR[0]: FLMRD=1, FLM1=3, FLM2=0x68000000
40343440 = 00000007 00000007                     <- SYSCNT ticking
220028B0 = 68000000                              <- gp_next_buffer == FLM2
E000ED08 = 02000000 (VTOR), E000ED28 = 00000000 00000000 (CFSR/HFSR: no fault)
```

Two dumps of the live buffer `0x6812C000` 400 ms apart (`liveA.bin`/`liveB.bin`) differ
in 241649 / 393216 bytes = **61.5 %** — real motion. Row-to-row MAD at stride 2048 bytes
= 15.44 vs 17.36/17.32 at 2046/2050 and 86.24 at 1024 → stride is exactly 1024 px,
no padding, matching the linker layout.

### Switches

- `AUTO_START_RESOLUTION` = 0 restores the interactive terminal prompt.
- `CAMERA_AUTO_EXPOSURE` = 0 restores the example's fixed exposure/gain.
- `FORCE_TEST_PATTERN` = 1 re-enables the colour-bar diagnostic (non-functional here).

### Rebuild + flash recipe

```bash
cd /home/jbatra/tron/cam2lcd
export PATH=/home/jbatra/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin:$PATH
export ARM_GCC_TOOLCHAIN_PATH=/home/jbatra/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin
rm -f build/Release/cam2lcd.elf build/Release/cam2lcd.map   # ninja does not track the .lld files
cmake --build --preset ReleaseCI
timeout 90 /usr/bin/JLinkExe -device R7KA8P1AF -if SWD -speed 4000 -autoconnect 1 \
    -CommanderScript fl.jlink
```

`fl.jlink` loads `build/Release/cam2lcd.elf`, resets and runs. `run.jlink` = `h`/`r`/`g`/`q`.
Latest image: text 47468, data 2424, bss 6152356. A host-side render of the captured
frame is at `ae2.png`. **The panel itself was not visually confirmed by the agent** —
the operator must check it.
## Stopping the cam2lcd firmware without reflashing (2026-09-17)

`JLinkExe ... -CommanderScript <h/q script>` does **not** leave the target stopped: on
disconnect the debugger clears `DHCSR.C_DEBUGEN`, which also clears `C_HALT`, so the core
resumes where it was. Verified: after `h` + `q`, `gp_next_buffer` (`0x220028B0`) kept
rotating through the three VIN buffers between sessions.

To actually stop it, park the core where its own code keeps it stopped:

```
h
w4 E000E010 00000000        ; SysTick off
w4 E000E180 FFFFFFFF        ; NVIC ICER0..7: mask every peripheral interrupt
w4 E000E184 FFFFFFFF
w4 E000E188 FFFFFFFF
w4 E000E18C FFFFFFFF
w4 E000E190 FFFFFFFF
w4 E000E194 FFFFFFFF
w4 E000E198 FFFFFFFF
w4 E000E19C FFFFFFFF
SetPC 22008010              ; Reset_Handler+0x10: `b.n 22008010` (in SRAM, executable)
g
q
```

`0x22008010` already holds `e7fe` (`b .`) — it is the "main returned" trap at the end of
`Reset_Handler`. With every IRQ masked the core spins there forever, surviving debugger
detach.

Then stop the two hardware engines so the picture really freezes (CPU is parked, so only
these two writes matter):

```
h
w4 40347400 00000000        ; R_VIN->MC = 0: ME=0, ST=0 -> capture engine off
w4 40343000 00000000        ; GLCDC BG = 0: EN/VEN=0 -> panel scanout off (blank)
SetPC 22008010
g
q
```

Verification on hardware:

- `R_VIN` `MC` = `0`, `MS` (`0x40347404`) = `0` → `CA` = 0, capture inactive.
- GLCDC `BG` (`0x40343000`) = `0`.
- `PC = 0x22008010` on every reconnect, `IPSR = 0`, `CFSR`/`HFSR` = 0.
- `gp_next_buffer` frozen at `0x68258000`.
- Two `savebin` dumps of `0x6812C000` two seconds apart are **byte-identical** → no
  further frames are written.

**To start it again:** reset and run —

```bash
timeout 60 /usr/bin/JLinkExe -device R7KA8P1AF -if SWD -speed 4000 -autoconnect 1 \
    -CommanderScript run.jlink      # h / r / g / q
```

Nothing was written to flash, so a reset restores the normal camera firmware completely.
Scripts on disk: `freeze.jlink` (CPU only), `stopcamera.jlink` (CPU + VIN + GLCDC),
`pcchk.jlink`, `finalcheck.jlink`, `dump1.jlink`, `dump2.jlink`.

---

## Per-core benchmark results (M85 vs M33), 2026-09-17

Project: `/home/jbatra/tron/bench` (CPU0 = M85 image `build/Release/bench.elf`;
CPU1 = M33 image `cpu1/cpu1.elf`). Mailbox `0x2208F000`, CPU1 image loaded at
`0x220EA000`, SCI_B / virtual COM 115200 8N1 on `/dev/ttyACM0`.
Flash: `JLinkExe -device R7KA8P1AF ... -CommanderScript flash2.jlink` (`h / r / loadfile x2 / g`).

Two bugs were found and fixed this round (both in `src/bench.c`):

1. **Cache coherence.** CPU0 has L1 D-cache on; CPU1 has none. A plain store of
   `go` by CPU0 stayed in its dirty cache line and CPU1 never saw it, even though
   J-Link read the new value. `BSP_CFG_DCACHE_FORCE_WRITETHROUGH` did not prevent it.
   Fix: explicit maintenance around every mailbox access — `mbox_clean()` (DCCMVAC
   over the mailbox) before publishing, `mbox_sync()` (DCCIMVAC + DSB) before reading.
2. **Stale-mailbox liveness.** SRAM survives a debugger reset, so a leftover
   `magic` made `cpu1_ensure_active()` skip activation while CPU1 was actually
   halted. Fix: trust the hardware `CPU1ACTCSR.ACT` bit, not the magic, for liveness.

Workload: 4 scalar kernels × 200,000 element-ops each, timed with DWT CYCCNT.

Measured (identical across repeated runs; checksum `1804556156` on both cores):

| | CPU0 M85 @1000 MHz | CPU1 M33 @250 MHz | concurrent (both) |
|---|---|---|---|
| int-mix | 4.00 ns/op | 193.68 ns/op | 4.00 / 193.68 |
| float-mac | 6.00 | 193.68 | 6.00 / 193.68 |
| divmod | 37.36 | 258.24 | 37.36 / 258.24 |
| mem-fill | 9.01 | 480.00 | 9.01 / 480.00 |
| **TOTAL** | **14.09 ns/op** | **281.40 ns/op** | **14.09 / 281.40** |

CPU1 clock confirmed two independent ways: `SCKDIVCR2=0x00052120` (CPUCK1 = ÷4 →
250 MHz) and CPU0's wall-clock cross-check (225,126,117 CPU0 cycles for 56,281,031
CPU1 ticks → ratio 4.00 → 250 MHz). M85 ≈ 20× faster per scalar op. Concurrency cost
is nil: solo and concurrent figures are the same to the last digit — the cores share
no cache and the workloads fit in local SRAM.

---

# apnea_deploy — INT8 apnea classifier on EK-RA8P1 (Phase 0 complete)

`/home/jbatra/tron/apnea_deploy` (scaffold cloned from `~/tron/bench`).
TFLite MLP (21-32-16-1, 1249 params) ported to hand-rolled INT8 dense kernels
on CPU0 (Cortex-M85). No TFLM / Ethos-U. libm's `exp` is used (link `-lm`,
after objects).

## Python side (run from `apnea_deploy/`, cwd matters)
- `tools/tflite_walk.py` — flatbuffer walker.
- `tools/extract_tflite.py` -> `src/apnea_model.h`. Output:
  `reference pass: 256/256 bit-exact vs int8_probability`; `threshold: prob >= 0.29 <=> q >= -53`.
- `tools/dump_vectors.py` -> `src/apnea_selftest_vectors.h` (256 fixed windows,
  int8 + raw features, oracle prob/label).

## Build (Fedora, fresh shell — re-export PATH each time)
```
export PATH=/home/jbatra/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin:$PATH
cmake -S . -B build/Release -G Ninja -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_C_COMPILER=arm-none-eabi-gcc -DCMAKE_ASM_COMPILER=arm-none-eabi-gcc
cmake --build build/Release
```
Compiler MUST be passed explicitly — CMake otherwise picks the host `/usr/bin/cc`.

## Flash
`JLinkExe -device R7KA8P1AF -if SWD -speed 4000 -autoconnect 1 -CommanderScript flash.jlink`
(`flash.jlink`: `h / loadfile build/Release/apnea_deploy.elf / r / g / q`).

## On-hardware results (all PASS)
```
run    -> pre-quantized inputs ; 256 vectors ; mismatches 0 [PASS] ; positives 51
runraw -> raw features (normalize+quantize on device) ; mismatches 0 [PASS] ; positives 51
bench  -> 10000 inferences ; 77835974 cycles ; 7783.59 cycles/inference
          7.78 us/inference @1000 MHz ; 128475 inferences/s
feat   -> prob_q -26 / prob 0.3981 / APNEA   (vector 102)
          prob_q -67 / prob 0.2368 / normal   (vector 113)
```
`feat` was initially broken: `SERIAL_RX_MAX_SIZE` was 64, so the SCI_B ISR
silently dropped every char past 64 and a 21-float line (~150 chars) never
parsed. Raised to 512 in `src/SERIAL_TERM/serial.h` -> fixed.

Serial driver semantics discovered: `serial_has_data()` only goes true after a
whole CR/LF-terminated line arrives and `serial_read()` returns the entire line
at once — read one line per `TERM_HAS_DATA()`, not byte-at-a-time.

Model quality note: the model predicts 51 positives out of 256 while labels
contain only 15 — a training/model-quality fact, not an implementation bug.
The self-test asserts against the recorded oracle codes, not labels.

## apnea_deploy Phase 1 — label-free personalization + head-only training on hardware (2026-09-26)

New source: `src/apnea_personal.c` (+ CLI dispatch in `src/main.c`). Commands added:
`labels`, `personalize`, `train A|B teacher|proxy`, `showhead`, `sethead <17 floats>|global`,
`evalhead`, `resetoff`. All of these were executed on the board this session.

### Link fix — DTCM placement (the 32 KB RAM wall)
First link failed:
  `section __ram_zero$$ will not fit in region RAM ... region RAM overflowed by 2440 bytes`
Cause: `g_a2[256][16]` + `g_p[256]` floats (~17 KB) competing for the 32 KB `RAM` region.
Fix: the generated `fsp_gen.lld` already carries a DTCM output section collecting
`*(.dtcm)` -> `> DTCM` (128 KB @ 0x20000000). No linker edit was needed.
In `src/apnea_personal.c`:
  `#define P_DTCM __attribute__((section(".dtcm")))`
  annotated `static float g_a2[P_N][APNEA_H2] P_DTCM;` and `static float g_p[P_N] P_DTCM;`
Both are fully written before first read, so DTCM zero-init is not relied on.
After rebuild: ELF text 98268 / data 1708 / bss 33500; `nm` shows `g_p` @0x20000000,
`g_a2` @0x20000400, `__dtcm_zero$$Limit` 0x20004400. RAM-side bss = 33500-17408 = 16092 B
(~16 KB margin). Board boots and runs — placement confirmed on silicon.
NOTE: never re-run RASC after this; it would regenerate the linker scripts.

### Build (worked)
```
export PATH=/home/jbatra/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin:$PATH
cmake --build build/Release
```
Benign warnings only: `-z norelro ignored`, nosys `_close/_lseek/_read/_write`.

### Flash + serial capture (recipe that works)
Run flash and capture in ONE shell call (a backgrounded `cd` previously made JLink
look for `flash.jlink` in the wrong dir):
```
cd /home/jbatra/tron/apnea_deploy
stty -F /dev/ttyACM0 115200 raw -echo -onlcr
rm -f /tmp/capN.txt
timeout 80 cat /dev/ttyACM0 > /tmp/capN.txt & CATPID=$!
sleep 1
JLinkExe -device R7KA8P1AF -if SWD -speed 4000 -autoconnect 1 -CommanderScript flash.jlink
sleep 5
for c in "labels" "personalize" ...; do printf '%s\r\n' "$c" > /dev/ttyACM0; sleep 4; done
wait $CATPID; cat /tmp/capN.txt
```
Flash O.K. (2048 B, 117 KB/s). The board does NOT need reflashing between captures —
state persists; later captures just reuse `/dev/ttyACM0`.
Ordering caveat: `personalize` persists `g_off`; a `train` after it runs on the
re-centred backbone (gives site-A teacher n=94, captured as cap2). Always `resetoff`
before raw-label comparisons.

### Capture 1 — fresh boot
```
labels      teacher 142/256 confident, 126 agree with oracle
            teacher pos 56 ; proxy rule spo2_max_drop>=3.0 -> 28 (tp8 fp20 fn7) ; oracle 15/256
personalize baseline 118/256 (teacher-confident normal)
            offsets raw hr -2.3921  spo2_mean 3.6068  spo2_min 4.8904
            before thr .29  acc 0.8242 sens 0.8667 prec 0.2321 predpos 56 (tp13 fp43 fn2)
            otsu 0.4566 (build+threshold 1512564 cycles)
            after           acc 0.9023 sens 0.6667 prec 0.3333 predpos 30 (tp10 fp20 fn5)
evalhead    all256 0.9023/30 ; site A 0.9375 ; site B 0.8672
showhead    bias 0.0076 drift 0
            w3 0.3500 -0.3542 0.4834 0.2875 0.3542 0.4542 0.3625 0.0708
               0.2958 -0.1417 -0.3375 0.3542 -0.0625 -0.1667 -0.3375 0.5292
```

### Capture 3 — after resetoff (raw labels)
```
labels      repeats: 142/126, teacher pos 56, proxy 28, oracle 15
train A teacher  n=64  loss 0.1534 -> 0.0199  cycles 44818260 (56022.82/iter)
                 drift 1.2925 ; all256 acc 0.8906 prec 0.3030 predpos 33 (tp10 fp23 fn5)
                 head bias 0.2256
                 w3 0.5073 -0.7926 0.4834 0.8170 0.3542 0.4542 0.4292 0.0656
                    0.7987 -0.2956 -0.9179 0.3542 -0.5475 -0.5080 -0.7117 0.6562
train B teacher  n=78  loss 0.1335 -> 0.0209  cycles 53308270 (66635.33/iter)
                 drift 1.2272 ; all256 acc 0.8633 prec 0.2500 predpos 40 (tp10 fp30 fn5)
                 head bias 0.2375
                 w3 0.4598 -0.8015 0.4834 0.8379 0.3542 0.4542 0.4069 0.0708
                    0.7986 -0.3699 -0.8253 0.3542 -0.5093 -0.5113 -0.6050 0.5885
```

### Capture 4 — proxy labels
```
train A proxy   n=128  loss 0.2385 -> 0.0510  cycles 82304755 (102880.94/iter)
                drift 1.5417 ; acc 0.8984 sens 0.6667 prec 0.3226 predpos 31
train B proxy   n=128  loss 0.2200 -> 0.0758  cycles 82538142 (103172.67/iter)
                drift 1.2077 ; acc 0.9023 sens 0.6667 prec 0.3333 predpos 30
```
Proxy follows the prototype almost exactly.

### Capture 5 — federation round-trip
Host-computed UNWEIGHTED FedAvg of heads A,B (sim_personal.py lines 253-264):
```
0.4835 -0.7971 0.4834 0.8275 0.3542 0.4542 0.4181 0.0682
0.7986 -0.3327 -0.8716 0.3542 -0.5284 -0.5096 -0.6583 0.6223  bias 0.2315
```
`sethead <that>` -> drift 1.2568 ; acc 0.8828 sens 0.6667 prec 0.2857 predpos 35
`sethead global` -> drift 0 ; acc 0.8242 predpos 56 (tp13 fp43 fn2) ; site A 0.8203 site B 0.8281

### C vs Python prototype agreement
Exact: global-head baseline (0.8242 / 56 / tp13 fp43 fn2); Otsu (0.8242->0.9023, 30);
both proxy trainings; oracle 15/256; proxy rule 28.
Not exact: teacher-confident count 142 (C) vs 145 (Py) -> teacher n 64/78 vs 66/79.
Cause: C derives qcodes from the float-replicated head (`prob_to_q`) while the prototype
uses bit-exact INT8 codes; +-1 rounding near the -80/20 boundary flips ~3 windows, and
GD over 800 full-batch steps is sensitive to a 2-window input change (C site A 0.8906 vs
Py 0.8945; C site B 0.8633 vs Py 0.8906; FedAvg C 0.8828 vs Py 0.8906). Float32 vs
mixed-precision difference — not a logic bug.

### Conclusions (hardware-measured)
1. The cheapest robust win is label-free Otsu recalibration: 0.8242 -> 0.9023.
   Re-centring alone barely helps; the threshold move does the work.
2. Head-only training raises accuracy but COSTS sensitivity (0.8667 -> 0.6667) and
   still loses to plain recalibration; teacher labels come from the model itself, so
   training sits near a fixed point.
3. Federation does not beat recalibration (fed 0.8828 < otsu 0.9023);
   fedtinyrt/context.md sec 8 predicted exactly this.
4. The deployed model over-predicts (56 predicted positives at the global threshold vs
   15 true). Matching the 0.229 cohort prior is worse than Otsu here, because this
   subject's true rate is 15/256 = 5.9%.


---

# Capture 6 — implementation of the run-analysis fix list (2026-09-28)

Firmware rebuilt (`apnea_deploy/src/apnea_personal.c`, 1383 lines) and reflashed to
RA8P1 (`R7KA8P1AF`, CPU0 M85 @1000 MHz). All commands below are on-device output.

## Fixes that landed and their measured effect

### 1. C/Python bit-exact agreement  (was: 142 vs 145)
`MODE_TEACHER` labels now read `(int) apnea_selftest_prob[k]` — the bit-exact INT8
global-head code — instead of deriving a code from a float `prob_to_q`.
```
  teacher labels: 145/256 confident, 130 agree with oracle
  teacher pos   : 51
```
145 matches `tools/sim_personal.py` exactly. Teacher nA=66 / nB=79 now match the
prototype too (was 64/78). **Correction:** the "142 teacher" figures in Captures 1-5
were the float-recode artefact; 145 is authoritative.

### 2. Sites documented as an index split
```
  sites      : index split (A = windows 0..127, B = 128..255), not physical
```
Both `labels` and `help` now say so. No physical two-client claim is made anywhere.

### 3. Confidence intervals (Wilson + bootstrap)
```
  sens  0.8667  CI95 [0.6212, 0.9626]  (n_pos 15)
  prec  0.2321  CI95 [0.1410, 0.3577]  (predpos 56)
  AUROC 0.8802  bootstrap CI95 [0.7764, 0.9458]  (200 resamples)
```
With only 15 positives the sensitivity CI is 0.62-0.96 — every single-point AUROC/bal
number in earlier captures is inside this band. This is the honest precision of the
whole prototype.

### 4. Repeated cycle measurement (`cycrep`)
```
  cycrep: 5 x (site A teacher, n=66, 800 iters)
    runs   : 46500290 46412675 46412665 46412452 46412376
    min/med/max: 46412376 / 46412665 / 46500290 cycles
    median cycles/iter: 58015.83
```
Spread is 88k cycles on 46.4M (<0.2%) — timings are stable, not noise.

### 5. DTCM assumption verified at runtime
```
  mem        : g_a2 @0x20000400 in DTCM (0x20000000-0x20020000)
```
`init_once()` prints the actual link address and tests it against the DTCM range.
`.dtcm` section is 0x4400 bytes (17 KB) at 0x20000000, inside the 128 KB DTCM.
Cycles above are therefore genuinely TCM-resident.

### 6. Label-free training modes (`entropy`, `temporal`)
Real label-free objectives now exist (entropy = prediction entropy minimisation;
temporal = adjacent-window consistency), and the help text marks them label-free:

| mode | site | n | AUROC all | bal | f1 | cycles/iter |
|------|------|---|-----------|-----|----|-------------|
| entropy  | A | 20  | 0.8902 | 0.7918 | 0.4444 | 23242.70 |
| entropy  | B | 37  | 0.8874 | 0.7856 | 0.4167 | 36278.86 |
| temporal | A | 128 | 0.9140 | 0.7751 | 0.5000 | 103882.22 |
| temporal | B | 128 | 0.9026 | 0.7918 | 0.4444 | 100867.85 |

Entropy is ~2.5x cheaper per iter than teacher (23k vs 58k cycles) because it skips
the per-window cross-entropy target loop. Temporal gets the best AUROC (0.9140) with
zero labels. **But** none beats plain Otsu recalibration (0.9023 acc); temporal trades
bal_acc for AUROC/precision (predpos drops 30->21, f1 0.4444->0.5000).

### 7. True on-device federation (n-weighted FedAvg, multiple rounds)
Previously FedAvg lived only in Python. Now on the MCU:
```
  fed local site A, teacher, n=66, cycles 46413346   local drift vs fed: 1.2940
  fed local site B, teacher, n=79, cycles 54442478   local drift vs fed: 1.1685
  fedavg n-weighted: nA=66 nB=79   drift 1.2241  AUROC 0.8888  bal 0.7856  f1 0.4167
  fedrounds 3 x teacher:
    round 1  drift 1.2241  AUROC 0.8888  bal 0.7856  f1 0.4167
    round 2  drift 1.2372  AUROC 0.8888  bal 0.7856  f1 0.4167
    round 3  drift 1.2376  AUROC 0.8888  bal 0.7856  f1 0.4167
```
`fedavg` weighting is by local sample count (66 vs 79). Three rounds converge in
drift (1.2241 -> 1.2372 -> 1.2376) and AUROC is flat — the head has reached a fixed
point after round 1. `evalhead` after `fedrounds` reports identical numbers, i.e.
`sethead`/persistence of the aggregated head is correct.

### 8. Persistence of recentring/threshold
`personalize` now prints `[state] recentring + threshold persist; resetoff reverts`,
and `resetoff` clears both. Confirmed by output.

## What did NOT improve (honest list)
1. **Federation still loses to plain Otsu recalibration** (fed 0.8888 vs otsu 0.9023).
   Confirms the `fedtinyrt` prediction; on a single subject with self-generated
   teacher labels, federating a 17-param head adds nothing over threshold moving.
2. **Head-only GD still trades sensitivity for precision.** Every training mode above
   keeps sens at 0.60-0.67 vs the untrained 0.8667, while raising precision. Net
   bal_acc barely moves (0.79 vs 0.7918 baseline).
3. **Entropy mode is under-powered here**: n is only 20-37 because it uses only
   teacher-confident windows; it cannot reach the full 256.
4. **No NPU / no TFLM.** The RA8P1 has no Ethos-U; the model is a 1249-param hand
   INT8 MLP on CPU0. All timings are CPU0 M85 cycles.
5. **CI width dominates every conclusion.** With n_pos=15, the AUROC bootstrap band is
   0.78-0.95. Differences of 0.01-0.02 between methods are not resolvable on one subject.
