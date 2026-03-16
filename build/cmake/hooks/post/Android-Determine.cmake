# Copyright (C) 2020 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# This is a hook file that will be included by cmake at the end of
# Modules/Platform/Android-Determine.cmake.

# Cmake can't determine linux-arm64 hosts and set incorrect values.
# This will be fixed in future versions.  Detect when the values are
# wrong and override them.
if(CMAKE_HOST_SYSTEM_NAME STREQUAL "Linux" AND
   CMAKE_HOST_SYSTEM_PROCESSOR STREQUAL "aarch64" AND
   NOT CMAKE_ANDROID_NDK_TOOLCHAIN_HOST_TAG STREQUAL "linux-arm64" AND
   CMAKE_ANDROID_NDK)

   set(CMAKE_ANDROID_NDK_TOOLCHAIN_HOST_TAG "linux-arm64")
   set(CMAKE_ANDROID_NDK_TOOLCHAIN_UNIFIED "${CMAKE_ANDROID_NDK}/toolchains/llvm/prebuilt/${CMAKE_ANDROID_NDK_TOOLCHAIN_HOST_TAG}")

   string(APPEND CMAKE_SYSTEM_CUSTOM_CODE
     "set(CMAKE_ANDROID_NDK_TOOLCHAIN_HOST_TAG \"${CMAKE_ANDROID_NDK_TOOLCHAIN_HOST_TAG}\")\n"
     "set(CMAKE_ANDROID_NDK_TOOLCHAIN_UNIFIED \"${CMAKE_ANDROID_NDK_TOOLCHAIN_UNIFIED}\")\n"
   )
endif()


# android.toolchain.cmake may set this to export old variables.
if(_ANDROID_EXPORT_COMPATIBILITY_VARIABLES)
  file(READ "${CMAKE_ANDROID_NDK}/build/cmake/exports.cmake" _EXPORTS)
  string(APPEND CMAKE_SYSTEM_CUSTOM_CODE "\n${_EXPORTS}\n")
endif()
