# https://github.com/android/ndk/issues/929
# Tests that the first libdl found by find_library is the shared library rather
# than the static library.
cmake_minimum_required(VERSION 3.6.0)
project(cmake_search_order)

message("System library path: ${CMAKE_SYSTEM_LIBRARY_PATH}")
message("System prefix path: ${CMAKE_SYSTEM_PREFIX_PATH}")
find_library(LIBDL dl)
if(NOT LIBDL)
  message(FATAL_ERROR "libdl not found.")
endif()

if(LIBDL MATCHES ".a$")
  message(FATAL_ERROR "found libdl.a")
endif()

find_program(YASM yasm)
if(NOT YASM)
  message(FATAL_ERROR "yasm not found")
endif()
