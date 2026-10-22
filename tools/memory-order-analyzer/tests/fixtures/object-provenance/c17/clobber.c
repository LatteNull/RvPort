struct Box { int *pointer; };
extern void unknown_change(struct Box *);
int *read_after_clobber(struct Box *box) {
  unknown_change(box);
  return box->pointer;
}
