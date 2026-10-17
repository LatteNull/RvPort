import cffi

ffi.dlopen("lib.so")
cffi.FFI().dlopen("/path/lib")
FFI.dlopen(123)
a.c[1].call()
cffi.FFI().cdef(None)
cffi.FFI().cdef(aaa)
cffi.FFI().cdef('aaa')
