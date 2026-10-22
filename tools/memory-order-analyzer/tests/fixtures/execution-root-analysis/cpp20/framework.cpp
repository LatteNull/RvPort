extern "C" void framework_entry() {}
extern "C" void exported_entry() { framework_entry(); }
