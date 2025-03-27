LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := gets-libcxx
LOCAL_SRC_FILES := gets-libcxx.cpp
LOCAL_CPPFLAGS := -std=c++14 -Wall -Werror
include $(BUILD_EXECUTABLE)
