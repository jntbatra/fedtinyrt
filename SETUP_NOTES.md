# FedTinyRT EK-RA8P1 Setup Notes

## What Was Done

### 1. Repositories Cloned
- `D:\Projects\TRON\mtk3_bsp2` — μT-Kernel 3.0 BSP2 (board support package)
- `D:\Projects\TRON\mtk3_bsp2\mtkernel` — μT-Kernel 3.0 core (git submodule, auto-fetched)

### 2. e2 Studio Project Created
- **Name:** Project (at `D:\Users\jayan\e2_studio\workspace\Project`)
- **Board:** EK-RA8P1
- **Toolchain:** GNU ARM Embedded 13.3.1
- **Template:** Bare Metal - Minimal (no RTOS plugin, no LCD, no FreeRTOS)
- **TrustZone:** Flat (disabled)

### 3. mtk3_bsp2 Linked Into Project
- Windows directory junction created:
  `Project\mtk3_bsp2` → `D:\Projects\TRON\mtk3_bsp2`
- Junction means no file duplication — same source used by both locations

### 4. Build Settings Configured
In Project Properties → C/C++ Build → Settings:

**GNU Arm Cross C Compiler → Preprocessor (Defined symbols):**
- `_RAFSP_EK_RA8P1_` — tells BSP2 which board we're targeting

**GNU Arm Cross C Compiler → Includes:**
- `${workspace_loc:/${ProjName}/mtk3_bsp2}`
- `${workspace_loc:/${ProjName}/mtk3_bsp2/config}`
- `${workspace_loc:/${ProjName}/mtk3_bsp2/include}`
- `${workspace_loc:/${ProjName}/mtk3_bsp2/mtkernel/kernel/knlinc}`

**GNU Arm Cross Assembler → Preprocessor:** same define as above  
**GNU Arm Cross Assembler → Includes:** same 4 paths as above

**GNU Arm Cross C++ Linker → General → Script files:**
- `${workspace_loc:/${ProjName}/mtk3_bsp2/etc/linker/mtkernel.ld}`

**mtk3_bsp2 folder:** Unchecked "Exclude resource from build" in folder Properties → C/C++ Build

### 5. Source Files Modified/Created

**`src/hal_entry.cpp`** — FSP entry point, boots μT-Kernel:
```cpp
extern "C" void knl_start_mtkernel(void);

void hal_entry(void)
{
    knl_start_mtkernel();  // starts μT-Kernel 3.0
    ...
}
```

**`src/usermain.c`** — μT-Kernel calls this after boot:
```c
#include <tk/tkernel.h>
#include <tm/tmonitor.h>

EXPORT INT usermain(void)
{
    tm_putstring((UB*)"FedTinyRT starting...\n");
    tk_slp_tsk(TMO_FEVR);  // sleep forever, keeps OS alive
    return 0;
}
```

### 6. Result
- Build: SUCCESS (241 mtk3_bsp2 object files compiled)
- Flash: SUCCESS via e2 studio Debug
- Serial output (115200 baud, USB COM port):
  ```
  microT-Kernel Version 3.00
  FedTinyRT starting...
  ```

## Important Notes
- **Black screen is normal** — no LCD driver in this project
- All output is via UART → Tera Term at 115200 baud
- The 4 "errors" shown in e2 studio build are false positives (linker warnings about unused C stdlib stubs)
- This project replaces the quickstart demo — to go back to LCD/menu, open `quickstart_ek_ra8p1_ep` project

## Next Steps (FedTinyRT Development)
1. Add sensor task (I2C accelerometer or PDM microphone)
2. Add ML inference task (CMSIS-NN INT8)
3. Add UART federation task (inter-board gradient sharing)
4. Implement FedAvg aggregation
