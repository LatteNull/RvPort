import sys
from cffi import FFI
import cffi

ffi = FFI()
ffi.cdef("""

    typedef void DIR;
    typedef long ino_t;
    typedef long off_t;

    struct dirent {
        ino_t          d_ino;       /* inode number */
        off_t          d_off;       /* offset to the next dirent */
        unsigned short d_reclen;    /* length of this record */
        unsigned char  d_type;      /* type of file; not supported
                                       by all file system types */
        char           d_name[256]; /* filename */
    };

    int readdir_r(DIR *dirp, struct dirent *entry, struct dirent **result);
    int openat(int dirfd, const char *pathname, int flags);
    DIR *fdopendir(int fd);
    int closedir(DIR *dirp);

""")
ffi.set_source("_readdir", None)
ffi.cdef("""
#if defined(__x86_64):
    typedef void DIR;
    typedef long ino_t;
    typedef long off_t;

    struct dirent {
        ino_t          d_ino;       /* inode number */
        off_t          d_off;       /* offset to the next dirent */
        unsigned short d_reclen;    /* length of this record */
        unsigned char  d_type;      /* type of file; not supported
                                       by all file system types */
        char           d_name[256]; /* filename */
    };

    int readdir_r(DIR *dirp, struct dirent *entry, struct dirent **result);
    int openat(int dirfd, const char *pathname, int flags);
    DIR *fdopendir(int fd);
    int closedir(DIR *dirp);
#endif

""")
import c as t
t.o().o()
ffi.cdef(hfile.read())
ffi.set_source("_sodium", "\\n".join(source), libraries=libraries)
ffi.dlopen(_helperlib.__file__)
ffi.set_source('_xclient_cffi', """\n            #include <X11/Xlib.h>\n""", libraries=['X11'])
lib = ffi.verify()
ffi.verify('check')
kk=cffi.FFI()
cffi.FFI().set_source('_cffi', '')
cffi.FFI().set_source('_cffi', aa)
cffi.FFI().verify('_cffi', '')
cffi.FFI().verify(None)
cffi.FFI().__init()
if __name__ == '__main__':
    ffi.compile()
