LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := __builtin___stpncpy_chk
LOCAL_SRC_FILES := __builtin___stpncpy_chk.c
LOCAL_CFLAGS += -D_FORTIFY_SOURCE=3
include $(BUILD_EXECUTABLE)

