cmake_minimum_required(VERSION 3.6)

if(NOT "foobar" IN_LIST CMAKE_FIND_ROOT_PATH)
  message(FATAL_ERROR
    "Did not find user specified FIND_ROOT_PATH in ${CMAKE_FIND_ROOT_PATH}")
endif()
