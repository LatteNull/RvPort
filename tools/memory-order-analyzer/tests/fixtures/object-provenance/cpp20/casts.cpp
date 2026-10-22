struct Box { int value; };
int *bounded_cast(Box *box) {
  void *opaque = static_cast<void *>(box);
  return &static_cast<Box *>(opaque)->value;
}
