int test(int x, int y) {
  return x + y;
}
void main() {
  // Missing second arg
  printf(test(4, ));
}
