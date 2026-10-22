#define VZEROALL asm("vzeroall");

void clear_vector_state(void) {
  VZEROALL
}

