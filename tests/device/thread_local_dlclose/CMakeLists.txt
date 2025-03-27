cmake_minimum_required(VERSION 3.17.0)
project(thread_local_dlclose)

add_library(testlib SHARED jni/testlib.cpp)

target_link_options(testlib
  PRIVATE
    -Wl,--version-script,${CMAKE_SOURCE_DIR}/jni/libtestlib.map.txt
)

add_executable(foo jni/foo.cpp)
