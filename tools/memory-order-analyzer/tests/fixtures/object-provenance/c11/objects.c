struct Inner { int value; };
union Choice { int left; long right; };
struct Box { struct Inner inner; struct Inner *pointer; union Choice choice; };

int read_nested(struct Box *box) { return box->inner.value; }
int *read_pointer(struct Box *box) { return &box->pointer->value; }
long read_union(struct Box *box) { return box->choice.right; }
