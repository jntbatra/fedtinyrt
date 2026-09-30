# CMake scaffold for the RASC-generated RA8P1 (EK-RA8P1, CPU0) project.
#
# RASC's own CMakeLists.txt/CMakePresets.json/cmake/Generated*.cmake are emitted only by
# the GUI project-creation wizard (no CLI command renders them), so this file supplies the
# equivalent build data. Flags/includes/defines were derived from the generated FSP content
# and from Renesas' own mipi_csi_ek_ra8p1_ep example project settings (.cproject).
#
# All FSP sources/linker scripts under ra/, ra_cfg/, ra_gen/, src/ and script/ are produced
# by `rasc ... generate project-content`.

cmake_minimum_required(VERSION 3.25.1)

set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

project(cam2lcd VERSION 1.0.0 LANGUAGES C ASM)

set(CMAKE_CROSSCOMPILING TRUE)
set(CMAKE_EXPORT_COMPILE_COMMANDS TRUE)
set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Cortex-M85 core of the RA8P1 (CPU0, primary core)
set(CPU_FLAGS -mcpu=cortex-m85 -mthumb -mfloat-abi=hard -mfpu=fpv5-d16)

set(COMMON_FLAGS
    -fmessage-length=0
    -funsigned-char
    -fshort-enums
    -fno-unroll-loops
    -fdata-sections
    -ffunction-sections
    -fno-strict-aliasing
    -Wall
)

set(RASC_SOURCE_DIR ${CMAKE_CURRENT_SOURCE_DIR})

file(GLOB_RECURSE SOURCES
    "${RASC_SOURCE_DIR}/src/*.c"
    "${RASC_SOURCE_DIR}/ra_gen/*.c"
    "${RASC_SOURCE_DIR}/ra/board/*.c"
    "${RASC_SOURCE_DIR}/ra/fsp/src/*.c"
)

add_executable(${PROJECT_NAME} ${SOURCES})

target_compile_definitions(${PROJECT_NAME} PRIVATE
    _RENESAS_RA_
    USE_VIRTUAL_COM=1
    _RA_CORE=CPU0
    _RA_ORDINAL=1
)

target_include_directories(${PROJECT_NAME} PRIVATE
    ${RASC_SOURCE_DIR}
    ${RASC_SOURCE_DIR}/src
    ${RASC_SOURCE_DIR}/ra/fsp/inc
    ${RASC_SOURCE_DIR}/ra/fsp/inc/api
    ${RASC_SOURCE_DIR}/ra/fsp/inc/instances
    ${RASC_SOURCE_DIR}/ra/arm/CMSIS_6/CMSIS/Core/Include
    ${RASC_SOURCE_DIR}/ra_gen
    ${RASC_SOURCE_DIR}/ra_cfg/fsp_cfg/bsp
    ${RASC_SOURCE_DIR}/ra_cfg/fsp_cfg
    ${RASC_SOURCE_DIR}/ra/fsp/src/r_mipi_csi
    ${RASC_SOURCE_DIR}/ra/fsp/src/r_vin
)

target_compile_options(${PROJECT_NAME} PRIVATE
    ${CPU_FLAGS}
    ${COMMON_FLAGS}
    $<$<CONFIG:Debug>:-Og -g3>
    $<$<CONFIG:Release>:-Os -g3>
)

# The FSP startup code supplies Reset_Handler/vector table, so the C runtime startup
# files must not be linked (they would define conflicting _start/Reset_Handler).
target_link_options(${PROJECT_NAME} PRIVATE
    ${CPU_FLAGS}
    -nostartfiles
    --specs=nosys.specs
    -Wl,--gc-sections
    -Wl,-z,norelro
    -T${RASC_SOURCE_DIR}/script/fsp.lld
    -L${RASC_SOURCE_DIR}/script
    -L${RASC_SOURCE_DIR}
    -Wl,-Map=${PROJECT_NAME}.map
)

set_target_properties(${PROJECT_NAME} PROPERTIES SUFFIX ".elf")

# The apnea sigmoid uses exp(); libm must come after the objects on the link line.
target_link_libraries(${PROJECT_NAME} PRIVATE m)
