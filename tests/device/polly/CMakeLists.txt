cmake_minimum_required(VERSION 3.17)
project(polly_test)

add_executable(polly_test jni/polly_test.cpp)
target_compile_options(polly_test PRIVATE -mllvm -polly)
