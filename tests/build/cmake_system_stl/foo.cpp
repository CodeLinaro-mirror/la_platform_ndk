class MyClass {
 public:
  virtual ~MyClass() {
  }
};

extern "C" void* func() {
  return new MyClass();
}

int main(int, char**) {
  func();
  return 0;
}
