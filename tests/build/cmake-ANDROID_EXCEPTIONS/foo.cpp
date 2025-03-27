int main(int argc, char** argv) {
  try {
    throw 42;
  } catch (const int& ex) {
    return ex;
  }
  return 0;
}