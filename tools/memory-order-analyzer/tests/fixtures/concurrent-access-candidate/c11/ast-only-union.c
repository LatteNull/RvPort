union shared_value { int word; unsigned char bytes[sizeof(int)]; } value;

void source_only_writer(void) { value.word = 7; }
int source_only_reader(void) { return value.bytes[0]; }
