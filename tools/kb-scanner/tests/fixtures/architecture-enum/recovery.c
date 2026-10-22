enum Backend { scalar, X86_AESNI = 7, riscv };
int choose(enum Backend value) {
  switch (value) {
    case X86_AESNI: return 1;
    case riscv: return 0;
  /* deliberately incomplete for parser recovery */
