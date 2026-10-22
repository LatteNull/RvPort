extern int helper(int);
__attribute__((used)) static int unreachable() { return helper(99); }
int main() { return helper(20); }
