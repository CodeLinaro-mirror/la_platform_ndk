cmake_minimum_required(VERSION 3.22)
project(ArmMode CXX)

if(CMAKE_ANDROID_ARCH_ABI STREQUAL "armeabi-v7a")
  if(NOT DEFINED CMAKE_ANDROID_ARM_MODE)
    message(FATAL_ERROR "CMAKE_ANDROID_ARM_MODE should be set for armeabi-v7a")
  endif()
else()
  if(DEFINED CMAKE_ANDROID_ARM_MODE)
    message(
      FATAL_ERROR
      "CMAKE_ANDROID_ARM_MODE should not be set for non armeabi-v7a"
    )
  endif()
endif()
