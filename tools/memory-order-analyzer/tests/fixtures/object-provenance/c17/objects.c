struct Node { int value; struct Node *next; };
int select_value(struct Node *left, struct Node *right, int choose) {
  struct Node *selected = choose ? left : right;
  return selected->value;
}
