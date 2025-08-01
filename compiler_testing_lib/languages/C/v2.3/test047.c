void main() {
  // Unexpected OPEN_BRA
  int f = 1;
  if (f == 1) {
    f = 2;
  }
  {
    f = 3;
  }
}