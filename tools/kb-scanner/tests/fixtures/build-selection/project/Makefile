ARCH := $(shell uname -m)
ifeq ($(ARCH),riscv64)
SRC += src/rv.c
CFLAGS += -march=rv64gc
else
SRC += src/generic.c
endif
X86_FLAGS = -mavx -mavx2
include config.mk
all: $(SRC)
	@echo not-executed
