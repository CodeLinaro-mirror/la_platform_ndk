#include <jni.h>

extern "C" JNIEXPORT jstring JNICALL
Java_com_android_developer_ndkgdbsample_MainActivity_getHelloString(JNIEnv *env, jobject) {
    return env->NewStringUTF("Hello, world!");
}