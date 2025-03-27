LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := weak_symbols
LOCAL_SRC_FILES := weak_symbols.cpp
LOCAL_LDLIBS := -landroid
include $(BUILD_EXECUTABLE)
