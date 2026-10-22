struct Box {
  int value;
  int read() const { return this->value; }
};
int sum(Box *left, Box *right) { return left->value + right->value; }
