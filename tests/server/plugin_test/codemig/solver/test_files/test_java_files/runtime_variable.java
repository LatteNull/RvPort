public class TestRuntimeVariable {
    public void testRuntimeVariable() {
        Runtime runtime = Runtime.getRuntime();
        runtime.load("test.so");
        runtime.loadLibrary("mylib");
        
        Runtime rt = Runtime.getRuntime();
        rt.load("another.so");
    }
}

public void loadWithDifferentImports() {
    // 完全限定名调用
    java.lang.System.loadLibrary("fullname_lib");
    // 通过变量调用
    java.lang.Runtime rt2 = java.lang.Runtime.getRuntime();
    rt2.load("/full/path/lib.so");
}

