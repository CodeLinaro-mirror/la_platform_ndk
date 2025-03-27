extern int bar();

#if !__ARM_NEON__
#error __ARM_NEON__ expected but not defined
#endif

int main(int, char**) {
  return bar();
}
