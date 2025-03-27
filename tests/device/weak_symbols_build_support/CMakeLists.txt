cmake_minimum_required(VERSION 3.22.1)
project(WeakSymbolsBuildSupport CXX)

set(GTEST_PATH "${ANDROID_NDK}/sources/third_party/googletest")

add_executable(weak_symbols
    jni/weak_symbols.cpp
    ${GTEST_PATH}/src/gtest-all.cc
    ${GTEST_PATH}/src/gtest_main.cc
)
target_include_directories(weak_symbols PRIVATE ${GTEST_PATH}/include ${GTEST_PATH})
target_link_libraries(weak_symbols PRIVATE -landroid)