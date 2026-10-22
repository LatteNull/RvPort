int ir_only_shared;
void ir_only_write(void) { ir_only_shared = 1; }
int ir_only_read(void) { return ir_only_shared; }
