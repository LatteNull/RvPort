#include "shared.h"
int shared_payload;
void *write_payload(void *unused) { (void)unused; shared_payload = 1; return 0; }
