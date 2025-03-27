LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := foo_static
LOCAL_SRC_FILES := $(TARGET_ARCH_ABI)/libfoo.a
LOCAL_ALLOW_MISSING_PREBUILT := true
include $(PREBUILT_STATIC_LIBRARY)

include $(CLEAR_VARS)
LOCAL_MODULE := foo
LOCAL_SRC_FILES := $(TARGET_ARCH_ABI)/libfoo.so
LOCAL_ALLOW_MISSING_PREBUILT := true
# Prevent the test from failing because llvm-strip will reject an empty file
# because it's not ELF.
LOCAL_STRIP_MODE := none
include $(PREBUILT_SHARED_LIBRARY)
