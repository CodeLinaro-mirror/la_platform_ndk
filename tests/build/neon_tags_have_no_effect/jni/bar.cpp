#if !__ARM_NEON__
#error __ARM_NEON__ expected but not defined
#endif

int bar() {
  return 0;
}
