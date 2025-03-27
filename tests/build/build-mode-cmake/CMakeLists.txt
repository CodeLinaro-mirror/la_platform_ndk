cmake_minimum_required(VERSION 3.6)

include(ExternalProject)

function(add_test name)
  cmake_parse_arguments(ARG
                        "CHECK_NEON;CHECK_ARM;CHECK_THUMB2;CHECK_X86"
                        "NEON;ARM_MODE"
                        ""
                        ${ARGN})

  set(args
          -DANDROID_ABI=${ANDROID_ABI}
          -DCMAKE_TOOLCHAIN_FILE=${CMAKE_TOOLCHAIN_FILE}
          -DANDROID_PLATFORM=${ANDROID_PLATFORM}
          -DCHECK_NEON=${ARG_CHECK_NEON}
          -DCHECK_ARM=${ARG_CHECK_ARM}
          -DCHECK_THUMB2=${ARG_CHECK_THUMB2}
          -DCHECK_X86=${ARG_CHECK_X86}
          -DCMAKE_MAKE_PROGRAM=${CMAKE_MAKE_PROGRAM}
    )
  if(DEFINED ARG_NEON)
    list(APPEND args -DANDROID_ARM_NEON=${ARG_NEON})
  endif()
  if(DEFINED ARG_ARM_MODE)
    list(APPEND args -DANDROID_ARM_MODE=${ARG_ARM_MODE})
  endif()
  ExternalProject_Add(${name}
    SOURCE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/jni
    CMAKE_ARGS ${args}
    INSTALL_COMMAND ""
    USES_TERMINAL_CONFIGURE TRUE
    USES_TERMINAL_BUILD TRUE
    )
endfunction()

if(ANDROID_ABI STREQUAL armeabi-v7a)
  add_test(test_build_mode
          CHECK_NEON CHECK_THUMB2)

  add_test(test_build_mode_thumb2
          ARM_MODE thumb
          CHECK_NEON CHECK_THUMB2)

  add_test(test_build_mode_armv7
          ARM_MODE arm
          CHECK_NEON CHECK_ARM)

  add_test(test_build_mode_neon
          NEON ON
          CHECK_NEON CHECK_THUMB2)

  add_test(test_build_mode_thumb2_neon
          ARM_MODE thumb
          NEON ON
          CHECK_NEON CHECK_THUMB2)

  add_test(test_build_mode_armv7_neon
          ARM_MODE arm
          NEON ON
          CHECK_NEON CHECK_ARM)

elseif(ANDROID_ABI STREQUAL x86)

  add_test(test_build_mode_x86
           CHECK_X86)

endif()
