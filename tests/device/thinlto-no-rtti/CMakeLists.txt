# Regression test for ThinLTO rtti bug:
#  - https://github.com/android/ndk/issues/717
#  - https://github.com/android/ndk/issues/1046

cmake_minimum_required(VERSION 3.6.0)

# Use a strong definition of the typeinfo variable from an ordinary ELF file in a static library
# compiled with -frtti (like libc++_static.a and libc++abi.a).
add_library(test1 STATIC jni/test1.cpp)
set_target_properties(test1 PROPERTIES
  COMPILE_FLAGS -frtti)

# Build the executable with ThinLTO and -fno-rtti. It will use linkonce_odr definitions of the
# typeinfo variable. I couldn't get ndk-build to compile this executable with -fno-rtti when its
# dependency used -frtti, so this test uses cmake instead.
add_executable(main jni/test2.cpp jni/test3.cpp)
set_target_properties(main PROPERTIES
  COMPILE_FLAGS "-fno-rtti -fexceptions -flto=thin"
  LINK_FLAGS -flto=thin)
target_link_libraries(main test1)
