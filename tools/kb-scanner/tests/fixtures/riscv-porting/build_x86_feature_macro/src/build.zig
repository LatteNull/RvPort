pub fn build() void {
    lib.root_module.addCMacro("HAVE_AVX2INTRIN_H", "1");
}
