/*
 * Copyright (C) 2018 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include <stdint.h>
#include <stdio.h>

struct Align4 { char buf[4]; } __attribute__((aligned(4)));
struct Align8 { char buf[8]; } __attribute__((aligned(8)));
struct Align16 { char buf[16]; } __attribute__((aligned(16)));
struct Align32 { char buf[32]; } __attribute__((aligned(32)));

static bool saw_error = false;

// A smart-enough compiler could decide that a pointer is aligned because it's
// required to be aligned. This weak symbol hides the pointer value from the
// optimizer.
__attribute__((weak))
uintptr_t hide_uintptr(uintptr_t val) {
  return val;
}

template <typename T>
void testT(const char* test_name, const char* type_name) {
  T t;
  const uintptr_t addr = hide_uintptr(reinterpret_cast<uintptr_t>(&t));
  const uintptr_t mask = sizeof(T) - 1;
  if ((addr & mask) != 0) {
    fprintf(stderr, "ERROR: %s %s: address is not aligned: %p\n",
        test_name, type_name, &t);
    saw_error = true;
  }
}

// The compiler will probably have to align the stack pointer for at least one
// of these types. If the different cases are inlined into one function, we
// won't test anything.

__attribute__((noinline))
void test4(const char* test_name) { testT<Align4>(test_name, "Align4"); }

__attribute__((noinline))
void test8(const char* test_name) { testT<Align8>(test_name, "Align8"); }

__attribute__((noinline))
void test16(const char* test_name) { testT<Align16>(test_name, "Align16"); }

__attribute__((noinline))
void test32(const char* test_name) { testT<Align32>(test_name, "Align32"); }

void do_test(const char* test_name) {
  test4(test_name);
  test8(test_name);
  test16(test_name);
  test32(test_name);
}

#if defined(__i386__) && __ANDROID_API__ <= 23
// On x86, API 23 and before, ESP isn't necessarily aligned in a static
// constructor, so skip this part of the test.
//
// The test would pass if it were compiled with -mstackrealign, but this test
// is trying to verify that the platform and CRT are aligning the stack pointer
// correctly rather than verify that -mstackrealign is used when it's
// necessary.
#else
bool static_initializer = (do_test("static_initializer"), false);
#endif

int main() {
  do_test("main");
  return saw_error;
}
