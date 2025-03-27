LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := foo
LOCAL_SRC_FILES := foo.cpp
LOCAL_CLANG_TIDY := true
LOCAL_CLANG_TIDY_FLAGS := -checks=*
include $(BUILD_EXECUTABLE)
