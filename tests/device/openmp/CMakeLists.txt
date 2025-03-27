cmake_minimum_required(VERSION 3.6.0)

add_executable(openmp jni/openmp.c)
set_target_properties(openmp PROPERTIES COMPILE_OPTIONS -fopenmp)
target_link_libraries(openmp -fopenmp -static-openmp)

add_executable(openmp2 jni/openmp2.c)
set_target_properties(openmp2 PROPERTIES COMPILE_OPTIONS -fopenmp)
target_link_libraries(openmp2 -fopenmp -static-openmp)

add_executable(fib jni/fib.c)
set_target_properties(fib PROPERTIES COMPILE_OPTIONS -fopenmp)
target_link_libraries(fib -fopenmp -static-openmp)
