#include <stdio.h>

extern const char* foo();

void bar() {
    printf("foo returned %s\n", foo());
}
