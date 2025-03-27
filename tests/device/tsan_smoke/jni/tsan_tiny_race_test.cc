//===----------------------------------------------------------------------===//
//
// Part of the LLVM Project, under the Apache License v2.0 with LLVM Exceptions.
// See https://llvm.org/LICENSE.txt for license information.
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
//
//===----------------------------------------------------------------------===//
#include <pthread.h>
#include <gtest/gtest.h>

int Global;
void *Thread1(void *x) {
  Global = 42;
  return x;
}
int RaceTest() {
  pthread_t t;
  pthread_create(&t, NULL, Thread1, NULL);
  Global = 43;
  pthread_join(t, NULL);
  return Global;
}

TEST(tsan_smoke, RaceTest) {
  ASSERT_DEATH(RaceTest(),
               "tsan_smoke/jni/tsan_tiny_race_test.cc:*.: "
               "virtual void assert_DeathTest_assert_false_Test::TestBody\\(\\): "
               "assertion \"false\" failed");
}
