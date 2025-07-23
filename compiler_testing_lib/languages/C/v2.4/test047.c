void main() {
  // Unexpected OPEN_BRA
  int m = 1;
  if (m == 1) {
    m = 2;
  }
  {
    m = 3;
  }
}