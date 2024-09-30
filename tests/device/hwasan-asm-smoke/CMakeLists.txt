cmake_minimum_required(VERSION 3.6)
project(CMakeDefaultFlagsTest C ASM)

add_library(hwasan-asm-smoke-cmake SHARED
    jni/hwasan_oob_test_asm.S)

add_executable(hwasan-asm-smoke-cmake_exe
    jni/hwasan_oob_test_asm.c
    jni/hwasan_oob_test_asm.S)
