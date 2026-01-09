// Struct implementation

struct Student {
  str name;
  int age;
  bool grade;
};

void main() {
  struct Student student1;
  student1.name = "John Doe";
  student1.age = 20;
  student1.grade = true;

  student1.age = student1.age + 1;
  printf(student1.name);
  printf(student1.age);
  printf(student1.grade);

}
 // test main function call