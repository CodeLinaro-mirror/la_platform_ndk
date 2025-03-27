#include <locale.h>

int main(int argc, char** argv) {
  locale_t locale = newlocale(LC_ALL, "tr_TR", static_cast<locale_t>(0));
  freelocale(locale);
  return 0;
}
