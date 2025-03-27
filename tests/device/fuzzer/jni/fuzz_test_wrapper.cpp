#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include <string>

int main(int, char**) {
  char cwd[PATH_MAX];
  if (getcwd(cwd, sizeof(cwd)) == nullptr) {
    perror("Could not get current working directory");
    exit(EXIT_FAILURE);
  }

  std::string fuzz_test = std::string(cwd) + "/fuzz_test";

  const char* exec_args[] = {fuzz_test.c_str(), "-max_total_time=10", nullptr};
  execv(fuzz_test.c_str(), const_cast<char**>(exec_args));
}
