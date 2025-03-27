cmake_minimum_required(VERSION 3.6.0)

find_path(ANDROID_INCLUDE_DIR NAMES android/log.h)
if(NOT ANDROID_INCLUDE_DIR)
  message(FATAL_ERROR "ANDROID_INCLUDE_DIR = ${ANDROID_INCLUDE_DIR}")
endif()
