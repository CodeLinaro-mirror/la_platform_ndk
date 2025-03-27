#include <dlfcn.h>

#include <thread>

void myThread() {
  void* lib = dlopen("./libtestlib.so", RTLD_LAZY);
  auto func = reinterpret_cast<void (*)()>(dlsym(lib, "func"));
  func();
  dlclose(lib);
}

int main(int, char**) {
  std::thread t(myThread);
  t.join();
}
