cmake_minimum_required(VERSION 3.6)
project(CMakeDefaultFlagsTest CXX)

set(GTEST_PATH "${ANDROID_NDK}/sources/third_party/googletest")

add_library(hwasan-smoke-cmake SHARED
    ${GTEST_PATH}/src/gtest-all.cc
    jni/hwasan_oob_test.cc)

add_executable(hwasan-smoke-cmake_exe
    jni/hwasan_oob_test.cc
    ${GTEST_PATH}/src/gtest-all.cc
    ${GTEST_PATH}/src/gtest_main.cc
)

target_include_directories(hwasan-smoke-cmake PRIVATE ${GTEST_PATH}/include ${GTEST_PATH})
target_include_directories(hwasan-smoke-cmake_exe PRIVATE ${GTEST_PATH}/include ${GTEST_PATH})
