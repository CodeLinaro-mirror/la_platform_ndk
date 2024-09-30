#if !__has_feature(hwaddress_sanitizer)
#error "Expected HWASan build"
#endif

.globl asm_zero
asm_zero:
  mov x0, #0
  ret
