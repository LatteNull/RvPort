/* SPDX-License-Identifier: BSD-3-Clause */
/* Copyright 2019-2021, Intel Corporation */
/* Copyright 2019, IBM Corporation */

#ifndef PMDK_PAGE_SIZE_H
#define PMDK_PAGE_SIZE_H

#if HAS_LONG
	#if defined(__x86_64)

		#define PMEM_PAGESIZE 4096
	#endif
#else

	#error not support

#endif


#if HAS_LONG
	#if defined(__x86_64)

		#define PMEM_PAGESIZE 4096
	#endif
#elif __aarch64__

	#error not support

#endif

#endif  /* PMDK_PAGE_SIZE_H */