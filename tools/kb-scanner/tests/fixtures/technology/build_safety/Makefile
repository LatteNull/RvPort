ARCH ?= riscv64
SOURCES := common.c

ifeq ($(ARCH),x86_64)
SOURCES += x86.c
else ifeq ($(ARCH),riscv64)
SOURCES += riscv.c
else
SOURCES += generic.c
endif

-include local.mk
DANGEROUS := $(shell touch /tmp/kb-scanner-security-marker)
ALSO_DANGEROUS != touch /tmp/kb-scanner-security-marker
