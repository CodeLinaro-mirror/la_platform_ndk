LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := stack_alignment
LOCAL_SRC_FILES := stack_alignment.cpp
ifeq ($(TARGET_ARCH_ABI),x86)
  # Verify that the stack is still aligned without this workaround. See
  # https://github.com/android-ndk/ndk/issues/635. Use LOCAL_CPPFLAGS, because
  # ndk-build adds -mstackrealign *after* the app's flags in LOCAL_CFLAGS, but
  # definitions.mk put C++ flags after C flags.
  LOCAL_CPPFLAGS += -mno-stackrealign
endif
include $(BUILD_EXECUTABLE)
