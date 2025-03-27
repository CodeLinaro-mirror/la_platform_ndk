#include <string.h>

#if _FORTIFY_SOURCE != 2
#error Expected _FORTIFY_SOURCE=2
#endif

int main(int argc, char** argv) {
  const char src[] = "foo bar baz";
  char dst[10];
  strcpy(dst, src);
  return 0;
}
