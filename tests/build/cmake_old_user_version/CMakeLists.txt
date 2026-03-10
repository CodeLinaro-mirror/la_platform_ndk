# The oldest minimum version supported by the version of cmake in the NDK tree, and
# something lower than this version of the NDK supports based on
# ndk/build/cmake/flags.cmake.  A lot of existing projects set this once and never
# update it, and even when a new enough version that does support this version of
# the NDK is used, the value used here dictates which CMake policies (behavior
# compatibility flags) are enabled by default. We set it to the oldest supported
# minimum here to ensure that we can at least build a trivial project when old
# policies are used.
cmake_minimum_required(VERSION 3.5)
project(OldCMakeCompat)

add_executable(foo foo.cpp)
