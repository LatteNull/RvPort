static int recurse(int value) { return value ? recurse(value - 1) : 0; }
int main(void) { return recurse(2); }
