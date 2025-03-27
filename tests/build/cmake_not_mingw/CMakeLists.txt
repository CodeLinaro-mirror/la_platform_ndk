cmake_minimum_required(VERSION 3.6)
project(CMakeNotMinGW C CXX ASM)

if(DEFINED MINGW)
  message(FATAL_ERROR "MINGW should not be defined")
endif()
