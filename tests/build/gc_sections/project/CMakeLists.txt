cmake_minimum_required(VERSION 3.22.1)
project("--gc-sections test")

add_library(foo SHARED jni/foo.cpp)
