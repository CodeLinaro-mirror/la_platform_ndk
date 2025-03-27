cmake_minimum_required(VERSION 3.22.1)
project("--no-undefined-version test" CXX)

add_library(foo SHARED jni/foo.cpp)
