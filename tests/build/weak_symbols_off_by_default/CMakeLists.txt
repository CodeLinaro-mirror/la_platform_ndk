cmake_minimum_required(VERSION 3.22.1)
project(WeakSymbolsBuildSupport CXX)
add_executable(weak_symbols jni/weak_symbols.cpp)