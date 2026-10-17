runtime.GOARCH == "x86_64"
runtime . GOARCH == "x86_64"
runtime. GOARCH = "x86_64"
runtime .GOARCH
runtime.GOOS
runtime. GOOS == "windows"

if runtime.GOARCH == "x86_64" {
    fmt.Println("x86_64")
}

if runtime.GOARCH == "arm64" {
    fmt.Println("arm64")
}

if runtime.GOARCH == "x86_64" || runtime.GOARCH == "mips64le" ||
	runtime.GOARCH == "arm64" ||
	runtime.GOARCH == "arm" ||
	runtime.GOARCH == "ppc64le" ||
	runtime.GOARCH == "s390x" ||
	runtime.GOARCH == "mips64" ||
	runtime.GOARCH == "mips64p32" ||
	runtime.GOARCH == "mipsle" {
    // do something
}

if runtime.GOARCH == "x86_64" || runtime.GOARCH == "mips64le" ||
	runtime.GOARCH == "arm64" ||
	runtime.GOARCH == "arm" ||
	runtime.GOARCH == "ppc64le" ||
	runtime.GOARCH == "s390x" ||
	runtime.GOARCH == "mips64" ||
	runtime.GOARCH == "mips64p32" ||
	runtime.GOARCH == "riscv64" ||
	runtime.GOARCH == "mipsle" {
    // do something
}

if runtime.GOARCH == "x86_64" || runtime.GOARCH == "mips64le" ||
	runtime.GOARCH == "arm64" {
    // do something
}else if runtime.GOARCH == "mips64le" {
	// do something else
}else {
	// default case
}

if runtime.GOARCH == "x86_64" || runtime.GOARCH == "mips64le" ||
	runtime.GOARCH == "riscv64" {
    // do something
}else if runtime.GOARCH == "mips64le" {
	// do something else
}else {
	// default case
}

if runtime.GOARCH == "x86_64" || runtime.GOARCH == "mips64le" ||
	runtime.GOARCH == "arm" {
    // do something
}else if runtime.GOARCH == "riscv64" {
	// do something else
}else {
	// default case
}


tmp = runtime.GOARCH == "x86_64" || runtime.GOARCH == "mips64le" ||
runtime.GOARCH == "s390x" ||
runtime.GOARCH == "mips64" ||
runtime.GOARCH == "mipsle"

tmp = runtime.GOARCH == "x86_64" || runtime.GOARCH == "mips64le" ||
runtime.GOARCH == "arm64" ||
runtime.GOARCH == "riscv64" ||
runtime.GOARCH == "mipsle"

const tmp = runtime.GOARCH == "x86_64" || runtime.GOARCH == "mips64le" ||
runtime.GOARCH == "mips64p32" ||
runtime.GOARCH == "mipsle"


switch runtime.GOARCH {
case "x86_64":
	fmt.Println("x86_64")
case "arm64":
	fmt.Println("arm64")
case "riscv64":
	fmt.Println("riscv64")
default:
	fmt.Println("unknown")
	
}

 switch     runtime . GOARCH  
 {
case "x86_64":
	fmt.Println("x86_64")
case "arm64":
	fmt.Println("arm64")

default:
	fmt.Println("unknown")
	
}

var arch = runtime.GOARCH

tmp_value = runtime . GOARCH

// 动态条件编译
func architectureSpecific() {
	// 运行时架构检测
	goarch := runtime.GOARCH

	if goarch == "amd64" {
		fmt.Println("Running x86-64 optimized code")
	} else if goarch == "386" {
		fmt.Println("Running i386 optimized code")
	} else {
		fmt.Printf("Unsupported architecture: %s\n", goarch)
	}
}


func hostByteOrder() byteOrder {
	switch runtime.GOARCH {
	case "386", "amd64", "amd64p32",
			"alpha",
			"arm", "arm64",
			"loong64",
			"mipsle", "mips64le", "mips64p32le",
			"nios2",
			"ppc64le",
			"riscv", "riscv64",
			"sh":
			return littleEndian{}
	case "armbe", "arm64be",
			"m68k",
			"mips", "mips64", "mips64p32",
			"ppc", "ppc64",
			"s390", "s390x",
			"shbe",
			"sparc", "sparc64":
			return bigEndian{}
	}

	switch {
	case processMachine == pe.IMAGE_FILE_MACHINE_AMD64 && runtime.GOARCH == "amd64":
	case processMachine == pe.IMAGE_FILE_MACHINE_I386 && runtime.GOARCH == "386":
	case processMachine == pe.IMAGE_FILE_MACHINE_ARMNT && runtime.GOARCH == "arm":
	case processMachine == pe.IMAGE_FILE_MACHINE_ARM64 && runtime.GOARCH == "arm64":
	default:
		t.Fatalf("unknown architecture: %s", runtime.GOARCH)
	}
	panic("unknown architecture")
}
