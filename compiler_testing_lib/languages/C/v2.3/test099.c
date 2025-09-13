int test(bool x) {
  return x;
}
void main() {
  // Wrong func return type
  printf(test(true));
}
