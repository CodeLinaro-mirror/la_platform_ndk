# Clang Migration Notes

NDK r17 was the last version to include GCC. If you're upgrading from an old NDK
and need to migrate to Clang, this doc can help.

If you maintain a custom build system, see the [Build System Maintainers]
documentation.

[Build System Maintainers]: ./BuildSystemMaintainers.md

## `-Oz` versus `-Os`

[Clang Optimization Flags](https://clang.llvm.org/docs/CommandGuide/clang.html#code-generation-options)
has the full details, but if you used `-Os` to optimize your
code for size with GCC, you probably want `-Oz` when using
Clang. Although `-Os` attempts to make code small, it still
enables some optimizations that will increase code size (based on
https://stackoverflow.com/a/15548189/632035). For the smallest possible
code with Clang, prefer `-Oz`. With `-Oz`, Chromium actually saw both
size *and* performance improvements when moving to Clang compared to
`-Os` with GCC.

## `__attribute__((__aligned__))`

Normally the `__aligned__` attribute is given an explicit alignment,
but with no value means “maximum alignment”. The interpretation of
“maximum” differs between GCC and Clang: Clang includes vector types
too so for ARM GCC thinks the maximum alignment is 8 (for `uint64_t`), but
Clang thinks it’s 16 (because there are NEON instructions that require
16-byte alignment). Normally this shouldn’t matter because malloc is
always at least 16-byte aligned, and mmap regions are page (4096-byte)
aligned. Most code should either specify an explicit alignment or use
[alignas](http://en.cppreference.com/w/cpp/language/alignas) instead.

## `-Bsymbolic`

When targeting Android (but no other platform), GCC passed
[-Bsymbolic](ftp://ftp.gnu.org/old-gnu/Manuals/ld-2.9.1/html_node/ld_3.html)
to the linker by default. This is not a good default, so Clang does not
do that. `-Bsymbolic` causes the following behavior change:

```c++
// foo.cpp
#include <iostream>

void foo() {
  std::cout << "Goodbye, world" << std::endl;
}

void bar() {
  foo();
}
```

```c++
// main.cpp
#include <iostream>

extern void bar();

void foo() {
  std::cout << "Hello, world\n";
}

int main(int, char**) {
  foo(); // Prints “Hello, world!”
  bar(); // Without -Bsymbolic, prints “Hello, world!” With -Bsymbolic, prints “Goodbye, world!”
}
```

In addition to not being the "expected" default behavior on all other
platforms, this prevents symbol interposition (used by tools such
as asan).

You might however wish to add manually `-Bsymbolic` back because it can
result in smaller ELF files because fewer relocations are needed. If you
do want the non-`-Bsymbolic` behavior but would like fewer relocations,
that can be achieved via `-fvisibility=hidden` (and manually exporting
the symbols you want to be public, using the `JNI_EXPORT` macro in JNI
code or `__attribute__ ((visibility("default")))` otherwise. Linker
version scripts are an even more powerful mechanism for controlling
exported symbols, but harder to use.

## Assembler issues

For many years the problem of adjusting inline assembler to work with
LLVM could be punted down the road by using `-fno-integrated-as` to fall
back to the GNU Assembler (GAS). With the removal of GNU binutils from
the NDK, such issues will now need to be addressed. We’ve collected
some of the most common issues and their solutions/workarounds here.

### `.arch` or `.arch_extension` scope with `__asm__`
GAS doesn’t scope `.arch` or `.arch_extension`, so you can have a global
`__asm__(".arch foo")` that applies to the whole C/C++ source file,
just like a bare `.arch` or `.arch_extension` directive would in a .S
file. LLVM scopes these to the specific `__asm__` in which it occurs,
so you’ll need to adapt your inline assembler, or build the whole file
for the relevant arch variant.

### ARM `ADRL`
GAS lets you use the `ADRL` pseudoinstruction to get the address of
something too far away for a regular `ADR` to reference. This means
that it expands to two instructions, which LLVM doesn’t support,
so you’ll need to use a macro something like this instead:
```
  .macro ADRL reg:req, label:req
  add \reg, pc, #((\label - .L_adrl_\@) & 0xff00)
  add \reg, \reg, #((\label - .L_adrl_\@) - ((\label - .L_adrl_\@) & 0xff00))
  .L_adrl_\@:
  .endm
```

### ARM assembler syntactical strictness
While GAS supports the older divided and newer unified syntax (selectable
via `.syntax unified` and `.syntax divided`), LLVM only supports the
newer unified syntax.

As an example of where this matters, `LDR` has an optional type and the
optional condition code allowed on all instructions. GAS allows these
to come in either order when using divided syntax, but LLVM only allows
them in the canonical order given in the ARM instruction reference (which
is what “unified” syntax means). So continuing this example, GAS
accepts both `LDRBEQ` and `LDREQB`, but LLVM only accepts `LDRBEQ` (with
the condition code at the end, as the instruction appears in the manual).

Most humans usually use this order anyway, but you’ll have to rearrange
any instructions that don’t use the canonical order.

### ARM assembler implicit operands
Some ARM instructions have restrictions that make some operands
implicit. For example, the two target registers supplied to `LDREXD`
must be consecutive. GAS would allow you to write `LDREXD R1, [R4]`
because the other register _must_ be `R2`, but LLVM requires both
registers to be explicitly stated, in this case `LDREXD R1, R2, [R4]`.

### ARM `.arm` or `.code 32` alignment
Switching from Thumb to ARM mode implicitly forces 4-byte alignment
with GAS but doesn’t with LLVM. You may need to use an explicit
`.align`/`.balign`/`.p2align` directive in such cases.

### No `--defsym` command-line option
GAS and LLVM implement their own conditional assembly mechanism with
`.if`...`.endif` rather than the C preprocessor’s `#if`...`#endif`. The
equivalent of `-DA=B` for `.if` is `-Wa,-defsym,A=B`, but GAS allowed
`--defsym` instead of `-defsym`. LLVM requires `-defsym`.

You might also prefer to just use the C preprocessor. If your assembly
is in a .S file it is already being preprocessed. If your assembly
is in a file with any other extension (including `.s` --- this is the
difference between `.s` and `.S`), you’ll need to either rename it to
`.S` or use the `-x assembler-with-cpp` flag to the compiler to override
the file extension-based guess.

### No `.func`/`.endfunc`
GAS ignores a request for obsolete STABS debugging information to be
emitted using `.func` and `.endfunc`. Neither GAS nor LLVM actually
support STABS, but LLVM rejects these meaningless directives. The fix
is simply to remove them.
