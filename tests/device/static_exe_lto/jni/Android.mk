# Regression test for https://github.com/android/ndk/issues/1461.
LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := foo
LOCAL_SRC_FILES := foo.cpp
LOCAL_LDFLAGS := -static -flto
include $(BUILD_EXECUTABLE)
