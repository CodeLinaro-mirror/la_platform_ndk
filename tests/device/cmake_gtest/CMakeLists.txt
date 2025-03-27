cmake_minimum_required(VERSION 3.22.1)
project(CMakeGTest CXX)

set(GTEST_PATH "${ANDROID_NDK}/sources/third_party/googletest")

add_executable(foo
    foo.cpp
    ${GTEST_PATH}/src/gtest-all.cc
    ${GTEST_PATH}/src/gtest_main.cc
)
target_include_directories(foo PRIVATE ${GTEST_PATH}/include ${GTEST_PATH})