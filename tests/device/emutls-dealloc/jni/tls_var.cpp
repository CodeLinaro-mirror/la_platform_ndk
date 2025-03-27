// Regression test for https://github.com/android-ndk/ndk/issues/687. Ensure
// that thread_local destructors run before emutls storage is deallocated.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <thread>

#include <gtest/gtest.h>

int dtor_count = 0;
bool dtor_failed = false;

struct TlsObject {
  ~TlsObject();
  // Use a large object to make it easier to trample on later.
  char buffer[1024 * 1024];
};

TlsObject::~TlsObject() {
  // Try to trample on freed heap memory. The compiler optimizes the
  // alloc-and-free away without volatile.
  char* volatile trample = new char[sizeof(TlsObject)];
  memset(trample, 0xcd, sizeof(TlsObject));
  delete[] trample;

  // Check whether the buffer has changed.
  dtor_count++;
  for (char& check_entry : buffer) {
    if (check_entry != 7) {
      dtor_failed = true;
    }
  }
}

TEST(emutls, tls_var) {
  std::thread([] {
    static thread_local TlsObject tls_var;
    for (char& assign_entry : tls_var.buffer) {
      assign_entry = 7;
    }
    return nullptr;
  }).join();

  ASSERT_EQ(1, dtor_count);
  ASSERT_EQ(false, dtor_failed);
}
