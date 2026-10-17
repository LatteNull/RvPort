
System.loadLibrary("valid");

Runtime.getRuntime().load("test.so");
static {
    System.load("/path/to/lib.so");
}

public void loadJnaLibrary() {
    Native.loadLibrary("jnalib", MyClass.class);
}

public static void main(String[] args){
    System.out.println("hhh")
}