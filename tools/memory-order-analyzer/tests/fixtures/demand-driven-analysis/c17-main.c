extern int helper(int);
__attribute__((used)) static int unreachable(void) { return helper(99); }
int main(void) { return helper(1); }
