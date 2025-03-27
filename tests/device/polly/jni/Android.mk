LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := polly_test
LOCAL_SRC_FILES := polly_test.cpp
LOCAL_CPPFLAGS := -mllvm -polly
include $(BUILD_EXECUTABLE)
