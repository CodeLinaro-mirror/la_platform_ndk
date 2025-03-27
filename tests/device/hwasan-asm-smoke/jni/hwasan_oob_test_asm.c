int asm_zero();

int main(int argc, char** argv) {
  // Make sure we actually get linked against the assembly
  return asm_zero();
}
