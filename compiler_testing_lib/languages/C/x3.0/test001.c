// Function implementation

int fac(int x) {
  if (x == 1) {
    return 1;
  }
  printf(x);
  return mult(x, fac(x-1));
}

int mult(int x, int y) {
  return x * y;
}

void main() {
  int n = 5;
  printf(fac(n));
}
 // test main function call