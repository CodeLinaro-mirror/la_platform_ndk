// Regression test for http://b/78022094. Ensure that pthread key destructors
// run before emutls storage is deallocated.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <thread>

#include <gtest/gtest.h>

thread_local int foo;
thread_local char tls_var[1024 * 1024];

int dtor_count = 0;
bool dtor_failed = false;

void test_dtor(void* parm) {
  // Try to trample on freed heap memory. The compiler optimizes the
  // alloc-and-free away without volatile.
  char* volatile trample = new char[sizeof(tls_var)];
  memset(trample, 0xcd, sizeof(tls_var));
  delete[] trample;

  // Attempt to access local_tls, which will have been freed if emutls has been
  // destroyed already. Use local_tls rather than tls_var, because ASAN won't check
  // an access to tls_var, but it will check local_tls.
  dtor_count++;
  auto& local_tls = *reinterpret_cast<decltype(tls_var)*>(parm);
  for (char& check_entry : local_tls) {
    if (check_entry != 20) {
      dtor_failed = true;
    }
  }
}

TEST(emutls, pthread_test) {
  // Ensure that emutls (with its pthread key) is initialized.
  foo = 1;

  // Create another pthread key to call test_dtor.
  pthread_key_t key;
  ASSERT_EQ(0, pthread_key_create(&key, test_dtor));

  std::thread([&]{
    pthread_setspecific(key, &tls_var);
    for (char& assign_entry : tls_var) {
      assign_entry = 20;
    }
  }).join();

  ASSERT_EQ(1, dtor_count);
  ASSERT_EQ(false, dtor_failed);
}
