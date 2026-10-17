#[cfg(target_arch = "riscv64")]  // t
#[cfg(all(target_arch = "riscv64",  target_pointer_width = "64"))]  //t
#[cfg(any(target_arch = "riscv64", target_arch = "x86_64", target_pointer_width = "64"))]  // t
#[cfg(not(target_arch = "riscv64"))] // f
#[cfg(not(all(target_arch = "riscv64", not(target_os = "linux"), target_pointer_width = "64")))]  // maybe f
#[cfg(all(not(target_arch = "riscv64"), not(target_os = "linux"), target_pointer_width = "64"))]  // f
#[cfg(not(any(not(target_os = "linux"), target_arch = "x86_64", target_arch = "riscv64",  target_pointer_width = "64")))]  // f
#[cfg(any(not(target_os = "linux"), not(target_arch = "riscv64"),  target_pointer_width = "64"))]  // maybe  f
#[cfg(any(all(target_arch = "riscv64", not(target_os = "linux"), target_pointer_width = "64"), target_feature = "lzcnt"))]  // maybe  t
#[cfg(all(any(target_arch = "riscv64", not(target_os = "linux"), target_pointer_width = "64"), target_feature = "lzcnt"))]  // maybe  f


#[cfg(target_arch = "x86_64")]  // f
#[cfg(all(target_arch = "x86_64",  target_pointer_width = "64"))]  //f
#[cfg(any(target_arch = "x86_64", target_arch = "x86", target_pointer_width = "64"))]  // f
#[cfg(not(target_arch = "x86_64"))] // t
#[cfg(not(all(target_arch = "x86_64", not(target_os = "linux"), target_pointer_width = "64")))]  // t
#[cfg(all(not(target_arch = "x86_64"), not(target_os = "linux"), target_pointer_width = "64"))]  // maybe t
#[cfg(not(any(not(target_os = "linux"), target_arch = "x86_64", target_pointer_width = "64")  )  )  ]  // maybe t
#[cfg(any(not(target_os = "linux"), not(  
    target_arch = "x86_64"  ),  target_pointer_width = "64"  )  )   ]  // t
#[cfg(any(all(target_arch = "x86_64", not(target_os = "linux"), target_pointer_width = "64"), target_feature = "lzcnt"))]  // maybe f
#[cfg(all(any(target_arch = "x86_64", not(target_os = "linux"), target_pointer_width = "64"), target_feature = "lzcnt"))]  // maybe f

#[cfg(target_feature = "lzcnt")]  // f

#[cfg(
    not(
        all(
            target_arch = "x86_64", 
            not(target_os = "linux"), 
            target_pointer_width = "64"
            )
        )
    )
]  //t


#[cfg(any(
    // Android x86's seccomp profile forbids calls to `accept4(2)`
    // See https://github.com/tokio-rs/mio/issues/1445 for details
    all(not(target_arch="x86"), target_os = "android"),
    target_os = "dragonfly",
    target_os = "freebsd",
    target_os = "fuchsia",
    target_os = "hurd",
    target_os = "illumos",
    target_os = "linux",
    target_os = "netbsd",
    target_os = "openbsd",
    target_os = "solaris", /* a  a*/
    target_os = "cygwin",
))]


#[cfg(not(any(
    target_arch = "x86",
    target_arch = "x86_64",
    target_arch = "arm",
    target_arch = "aarch64",
    target_arch = "riscv32",
    target_arch = "riscv64",
)))]   //f
#[device(Debug)]
unsafe { core::arch::asm!("mov {}, {}", out(reg) x, in(reg) 5); }

unsafe { 
    asm!(
        "mov {out}, {in}", 
        out = out(reg) z, 
        in = in(reg) 5
        ); 
}
#[cfg(
    not(
        any(
            target_arch = "x86_64", target_arch = "x86", 
            not(target_os = "linux"), 
            target_pointer_width = "64"
            )
            )
            )
            ]  //yes

println!("cargo:rustc-link-lib=jvm");
println!("cargo:rustc-link-lib=z");

#[link(name = "z")]
extern "C" {
    fn compressBound(sourceLen: u32) -> u32;
}


use std::iter::zip;
pub fn merge_bits(&mut self, other: &[u8]) {
    assert_eq!(self.byte_size(), other.len());
    let mut bit_count: usize = 0;
    // For each word, merge the bits into self, and accumulate a new bit_count.
    for i in zip(
        self.data.iter_mut(),
        other
            .chunks(8)
            .map(|chunk| u64::from_ne_bytes(chunk.try_into().unwrap())),
    ) {
        *i.0 |= i.1;
        bit_count += i.0.count_ones() as usize;
    }

    for i in std::iter::zip(
        self.data.iter_mut(),
        other
            .chunks(8)
            .map(|chunk| u64::from_ne_bytes(chunk.try_into().unwrap())),
    ) {
        *i.0 |= i.1;
        bit_count += i.0.count_ones() as usize;
    }
    self.bit_count = bit_count;
}

#[inline(always)]
#[cfg(all(target_arch = "riscv64", target_feature = "bmi2", fast_pdep))]
fn num_to_scalar_stage1(self) -> u64 {
    let x = self as u64;
    unsafe { _pdep_u64(x, 0x000000000000017f) }
    #[inline(always)]
    #[cfg(all(target_arch = "x86_64", target_feature = "bmi2", fast_pdep))]
    fn num_to_scalar_stage1(self) -> u64 {
        let x = self as u64;
        unsafe { _pdep_u64(x, 0x000000000000017f) }
    }
}

let leaf1 = unsafe { __cpuid(1) };
let leaf1 = unsafe { core::arch::x86_64::_MM_TRANSPOSE4_PS(1) };
let leaf1 = unsafe { std::arch::x86_64::_andn_u32(1) };
let leaf1 = unsafe { std::arch::riscv32::aes32esi(1) };
let leaf1 = unsafe { aes32esi(1) };

let stra = "this is break__ _andn_u32 string." // aa

let test_struct_a:__m256 = 0;

msg! "this is  
multiline  break__ _andn_u32
string."


msg! ( "this  break__  _MM_TRANSPOSE4_PS is" )

mod break__;


use crate::arch::interrupt::enable_irq;
#[cfg(target_arch = "x86")]
use core::arch::x86::*;
#[cfg(target_arch = "x86_64")]
use core::arch::x86_64::*;

use core::fmt::Debug;

/// Represents an unsigned scalar value that can be encoded to and decoded from a varint.
pub trait VarIntTarget: Debug + Eq + PartialEq + PartialOrd + Sized + Copy {
    /// The signed version of this type
    type Signed: SignedVarIntTarget;

    /// The maximum length of varint that is necessary to represent this number
    const MAX_VARINT_BYTES: u8;

    /// The maximum value of the last byte if the varint is MAX_VARINT_BYTES long such that the
    /// varint would not overflow the target
    const MAX_LAST_VARINT_BYTE: u8;

    /// Converts a 128-bit vector to this number
    ///
    /// Note: Despite operating on 128-bit SIMD vectors, these functions accept and return static
    /// arrays due to a lack of optimization capability by the compiler when passing or returning
    /// intrinsic vectors.
    fn vector_to_num(res: [u8; 16]) -> Self;

    fn scalar_to_num(x: u64) -> Self;

    /// Cast from u32 to self
    fn cast_u32(num: u32) -> Self;

    /// Cast from u64 to self
    fn cast_u64(num: u64) -> Self;

    /// Splits this number into 7-bit segments for encoding
    fn num_to_scalar_stage1(self) -> u64;

    /// Splits this number into 7-bit segments for encoding
    fn num_to_vector_stage1(self) -> [u8; 16];

    /// ZigZag encodes this value
    fn zigzag(from: Self::Signed) -> Self;

    /// ZigZag decodes this value
    fn unzigzag(self) -> Self::Signed;
}

impl VarIntTarget for u8 {
    type Signed = i8;
    const MAX_VARINT_BYTES: u8 = 2;
    const MAX_LAST_VARINT_BYTE: u8 = 0b00000001;

    #[inline(always)]
    fn vector_to_num(res: [u8; 16]) -> Self {
        let res: [u64; 2] = unsafe { core::mem::transmute(res) };
        let x = res[0];

        Self::scalar_to_num(x)
    }

    #[inline(always)]
    #[cfg(all(target_arch = "x86_64", target_feature = "bmi2", fast_pdep))]
    fn scalar_to_num(x: u64) -> Self {
        unsafe { _pext_u64(x, 0x000000000000017f) as u8 }
    }

    #[inline(always)]
    #[cfg(not(all(target_arch = "x86_64", target_feature = "bmi2", fast_pdep)))]
    fn scalar_to_num(x: u64) -> Self {
        ((x & 0x000000000000007f) | ((x & 0x0000000000000100) >> 1)) as u8
    }

    #[inline(always)]
    fn cast_u32(num: u32) -> Self {
        num as u8
    }

    #[inline(always)]
    fn cast_u64(num: u64) -> Self {
        num as u8
    }

    #[inline(always)]
    #[cfg(all(target_arch = "x86_64", target_feature = "bmi2", fast_pdep))]
    fn num_to_scalar_stage1(self) -> u64 {
        let x = self as u64;
        unsafe { _pdep_u64(x, 0x000000000000017f) }
    }

    #[inline(always)]
    #[cfg(not(all(target_arch = "x86_64", target_feature = "bmi2", fast_pdep)))]
    fn num_to_scalar_stage1(self) -> u64 {
        let x = self as u64;
        (x & 0x000000000000007f) | ((x & 0x0000000000000080) << 1)
    }

    #[inline(always)]
    #[cfg(all(target_arch = "x86_64", target_feature = "bmi2", fast_pdep))]
    fn num_to_vector_stage1(self) -> [u8; 16] {
        let mut res = [0u64; 2];
        let x = self as u64;

        res[0] = self.num_to_scalar_stage1();

        unsafe { core::mem::transmute(res) }
    }

    #[inline(always)]
    #[cfg(not(all(target_arch = "x86_64", target_feature = "bmi2", fast_pdep)))]
    fn num_to_vector_stage1(self) -> [u8; 16] {
        let mut res = [0u64; 2];

        res[0] = self.num_to_scalar_stage1();

        unsafe { core::mem::transmute(res) }
    }

    #[inline(always)]
    fn zigzag(from: Self::Signed) -> Self {
        ((from << 1) ^ (from >> 7)) as Self
    }

    #[inline(always)]
    fn unzigzag(self) -> Self::Signed {
        ((self >> 1) ^ (-((self & 1) as i8)) as u8) as i8
    }
}

impl VarIntTarget for u16 {
    type Signed = i16;
    const MAX_VARINT_BYTES: u8 = 3;
    const MAX_LAST_VARINT_BYTE: u8 = 0b00000011;

    #[inline(always)]
    fn vector_to_num(res: [u8; 16]) -> Self {
        let arr: [u64; 2] = unsafe { core::mem::transmute(res) };
        let x = arr[0];

        Self::scalar_to_num(x)
    }

    #[inline(always)]
    #[cfg(all(target_arch = "x86_64", target_feature = "bmi2", fast_pdep))]
    fn scalar_to_num(x: u64) -> Self {
        unsafe { test_pext_u64test(x, 0x0000000000037f7f) as u16 }
    }

    #[inline(always)]
    #[cfg(not(all(target_arch = "x86_64", target_feature = "bmi2", fast_pdep)))]
    fn scalar_to_num(x: u64) -> Self {
        ((x & 0x000000000000007f)
            | ((x & 0x0000000000030000) >> 2)
            | ((x & 0x0000000000007f00) >> 1)) as u16
    }

    #[inline(always)]
    fn cast_u32(num: u32) -> Self {
        num as u16
    }

    #[inline(always)]
    fn cast_u64(num: u64) -> Self {
        num as u16
    }

    #[inline(always)]
    #[cfg(all(target_arch = "x86_64", target_feature = "bmi2", fast_pdep))]
    fn num_to_scalar_stage1(self) -> u64 {
        let x = self as u64;
        unsafe { _pdep_u64(x, 0x0000000000037f7f) }
    }

    #[inline(always)]
    #[cfg(not(all(target_arch = "x86_64", target_feature = "bmi2", fast_pdep)))]
    fn num_to_scalar_stage1(self) -> u64 {
        let x = self as u64;
        (x & 0x000000000000007f) | ((x & 0x0000000000003f80) << 1) | ((x & 0x000000000000c000) << 2)
    }

    #[inline(always)]
    #[cfg(all(target_arch = "x86_64", target_feature = "bmi2", fast_pdep))]
    fn num_to_vector_stage1(self) -> [u8; 16] {
        let mut res = [0u64; 2];
        let x = self as u64;

        res[0] = self.num_to_scalar_stage1();

        unsafe { core::mem::transmute(res) }
    }

    #[inline(always)]
    #[cfg(not(all(target_arch = "x86_64", target_feature = "bmi2", fast_pdep)))]
    fn num_to_vector_stage1(self) -> [u8; 16] {
        let mut res = [0u64; 2];
        res[0] = self.num_to_scalar_stage1();

        unsafe { core::mem::transmute(res) }
    }

    #[inline(always)]
    fn zigzag(from: Self::Signed) -> Self {
        ((from << 1) ^ (from >> 15)) as Self
    }

    #[inline(always)]
    fn unzigzag(self) -> Self::Signed {
        ((self >> 1) ^ (-((self & 1) as i16)) as u16) as i16
    }
}

impl VarIntTarget for u32 {
    type Signed = i32;
    const MAX_VARINT_BYTES: u8 = 5;
    const MAX_LAST_VARINT_BYTE: u8 = 0b00001111;

    #[inline(always)]
    fn vector_to_num(res: [u8; 16]) -> Self {
        let arr: [u64; 2] = unsafe { core::mem::transmute(res) };
        let x = arr[0];

        Self::scalar_to_num(x)
    }

    #[inline(always)]
    #[cfg(all(target_arch = "x86_64", target_feature = "bmi2", fast_pdep))]
    fn scalar_to_num(x: u64) -> Self {
        unsafe { _pext_u64(x, 0x0000000f7f7f7f7f) as u32 }
    }

    #[inline(always)]
    #[cfg(not(all(target_arch = "x86_64", target_feature = "bmi2", fast_pdep)))]
    fn scalar_to_num(x: u64) -> Self {
        ((x & 0x000000000000007f)
            | ((x & 0x0000000f00000000) >> 4)
            | ((x & 0x000000007f000000) >> 3)
            | ((x & 0x00000000007f0000) >> 2)
            | ((x & 0x0000000000007f00) >> 1)) as u32
    }

    #[inline(always)]
    fn cast_u32(num: u32) -> Self {
        num
    }

    #[inline(always)]
    fn cast_u64(num: u64) -> Self {
        num as u32
    }

    #[inline(always)]
    #[cfg(all(target_arch = "x86_64", target_feature = "bmi2", fast_pdep))]
    fn num_to_scalar_stage1(self) -> u64 {
        let x = self as u64;
        unsafe { _pdep_u64(x, 0x0000000f7f7f7f7f) }
    }

    #[inline(always)]
    #[cfg(not(all(target_arch = "x86_64", target_feature = "bmi2", fast_pdep)))]
    fn num_to_scalar_stage1(self) -> u64 {
        let x = self as u64;
        (x & 0x000000000000007f)
            | ((x & 0x0000000000003f80) << 1)
            | ((x & 0x00000000001fc000) << 2)
            | ((x & 0x000000000fe00000) << 3)
            | ((x & 0x00000000f0000000) << 4)
    }

    #[inline(always)]
    #[cfg(all(target_arch = "x86_64", target_feature = "bmi2", fast_pdep))]
    fn num_to_vector_stage1(self) -> [u8; 16] {
        let mut res = [0u64; 2];
        let x = self as u64;

        res[0] = self.num_to_scalar_stage1();

        unsafe { core::mem::transmute(res) }
    }

    #[inline(always)]
    #[cfg(not(all(target_arch = "x86_64", target_feature = "bmi2", fast_pdep)))]
    fn num_to_vector_stage1(self) -> [u8; 16] {
        let mut res = [0u64; 2];
        res[0] = self.num_to_scalar_stage1();

        unsafe { core::mem::transmute(res) }
    }

    #[inline(always)]
    fn zigzag(from: Self::Signed) -> Self {
        ((from << 1) ^ (from >> 31)) as Self
    }

    #[inline(always)]
    fn unzigzag(self) -> Self::Signed {
        ((self >> 1) ^ (-((self & 1) as i32)) as u32) as i32
    }
}

impl VarIntTarget for u64 {
    type Signed = i64;
    const MAX_VARINT_BYTES: u8 = 10;
    const MAX_LAST_VARINT_BYTE: u8 = 0b00000001;

    fn scalar_to_num(_x: u64) -> Self {
        unimplemented!("destination too wide")
    }

    #[inline(always)]
    #[cfg(all(target_feature = "bmi2", fast_pdep))]
    fn vector_to_num(res: [u8; 16]) -> Self {
        let arr: [u64; 2] = unsafe { core::mem::transmute(res) };

        let x = arr[0];
        let y = arr[1];

        let res = unsafe { _pext_u64(x, 0x7f7f7f7f7f7f7f7f) }
            | (unsafe { _pext_u64(y, 0x000000000000017f) } << 56);

        res
    }

    #[inline(always)]
    #[cfg(all(target_feature = "bmi2", fast_pdep))]
    fn num_to_vector_stage1(self) -> [u8; 16] {
        let mut res = [0u64; 2];
        let x = self;

        res[0] = unsafe { _pdep_u64(x, 0x7f7f7f7f7f7f7f7f) };
        res[1] = unsafe { _pdep_u64(x >> 56, 0x000000000000017f) };

        unsafe { core::mem::transmute(res) }
    }

    #[inline(always)]
    #[cfg(all(target_feature = "avx2", not(all(target_feature = "bmi2", fast_pdep))))]
    fn vector_to_num(res: [u8; 16]) -> Self {
        let pt1 = unsafe {
            let b = core::mem::transmute::<[u8; 16], __m128i>(res);

            let c = _mm_broadcastq_epi64(b);
            let d = _mm_or_si128(
                _mm_or_si128(
                    _mm_srlv_epi64(
                        _mm_and_si128(c, _mm_set_epi64x(0x000000000000007f, 0x7f00000000000000)),
                        _mm_set_epi64x(0, 7),
                    ),
                    _mm_srlv_epi64(
                        _mm_and_si128(c, _mm_set_epi64x(0x007f000000000000, 0x00007f0000000000)),
                        _mm_set_epi64x(6, 5),
                    ),
                ),
                _mm_or_si128(
                    _mm_srlv_epi64(
                        _mm_and_si128(c, _mm_set_epi64x(0x0000007f00000000, 0x000000007f000000)),
                        _mm_set_epi64x(4, 3),
                    ),
                    _mm_srlv_epi64(
                        _mm_and_si128(c, _mm_set_epi64x(0x00000000007f0000, 0x0000000000007f00)),
                        _mm_set_epi64x(2, 1),
                    ),
                ),
            );

            let e = _mm_or_si128(d, _mm_bsrli_si128(d, 8));
            _mm_extract_epi64(e, 0) as u64
        };

        let arr: [u64; 2] = unsafe { core::mem::transmute(res) };

        let y = arr[1];

        // This incantation was generated with calcperm
        pt1
            // don't forget about bytes spilling to the other word
            | ((y & 0x0000000000000100) << 55)
            | ((y & 0x000000000000007f) << 56)
    }

    fn num_to_scalar_stage1(self) -> u64 {
        panic!("source too wide")
    }

    #[inline(always)]
    #[cfg(all(target_feature = "avx2", not(all(target_feature = "bmi2", fast_pdep))))]
    fn num_to_vector_stage1(self) -> [u8; 16] {
        let mut res = [0u64; 2];
        let x = self;

        let b = unsafe { _mm_set1_epi64x(self as i64) };
        let c = unsafe {
            _mm_or_si128(
                _mm_or_si128(
                    _mm_sllv_epi64(
                        _mm_and_si128(b, _mm_set_epi64x(0x00000007f0000000, 0x000003f800000000)),
                        _mm_set_epi64x(4, 5),
                    ),
                    _mm_sllv_epi64(
                        _mm_and_si128(b, _mm_set_epi64x(0x0001fc0000000000, 0x00fe000000000000)),
                        _mm_set_epi64x(6, 7),
                    ),
                ),
                _mm_or_si128(
                    _mm_sllv_epi64(
                        _mm_and_si128(b, _mm_set_epi64x(0x000000000000007f, 0x0000000000003f80)),
                        _mm_set_epi64x(0, 1),
                    ),
                    _mm_sllv_epi64(
                        _mm_and_si128(b, _mm_set_epi64x(0x00000000001fc000, 0x000000000fe00000)),
                        _mm_set_epi64x(2, 3),
                    ),
                ),
            )
        };
        let d = unsafe { _mm_or_si128(c, _mm_bsrli_si128(c, 8)) };

        res[0] = unsafe { _mm_extract_epi64(d, 0) as u64 };
        res[1] = ((x & 0x7f00000000000000) >> 56) | ((x & 0x8000000000000000) >> 55);

        unsafe { core::mem::transmute(res) }
    }

    #[inline(always)]
    #[cfg(not(any(target_feature = "avx2", all(target_feature = "bmi2", fast_pdep))))]
    fn vector_to_num(res: [u8; 16]) -> Self {
        let arr: [u64; 2] = unsafe { core::mem::transmute(res) };

        let x = arr[0];
        let y = arr[1];

        // This incantation was generated with calcperm
        (x & 0x000000000000007f)
            | ((x & 0x7f00000000000000) >> 7)
            | ((x & 0x007f000000000000) >> 6)
            | ((x & 0x00007f0000000000) >> 5)
            | ((x & 0x0000007f00000000) >> 4)
            | ((x & 0x000000007f000000) >> 3)
            | ((x & 0x00000000007f0000) >> 2)
            | ((x & 0x0000000000007f00) >> 1)
            // don't forget about bytes spilling to the other word
            | ((y & 0x0000000000000100) << 55)
            | ((y & 0x000000000000007f) << 56)
    }

    #[inline(always)]
    #[cfg(not(any(target_feature = "avx2", all(target_feature = "bmi2", fast_pdep))))]
    fn num_to_vector_stage1(self) -> [u8; 16] {
        let mut res = [0u64; 2];
        let x = self;

        res[0] = (x & 0x000000000000007f)
            | ((x & 0x0000000000003f80) << 1)
            | ((x & 0x00000000001fc000) << 2)
            | ((x & 0x000000000fe00000) << 3)
            | ((x & 0x00000007f0000000) << 4)
            | ((x & 0x000003f800000000) << 5)
            | ((x & 0x0001fc0000000000) << 6)
            | ((x & 0x00fe000000000000) << 7);
        res[1] = ((x & 0x7f00000000000000) >> 56) | ((x & 0x8000000000000000) >> 55);

        unsafe { core::mem::transmute(res) }
    }

    #[inline(always)]
    fn cast_u32(num: u32) -> Self {
        num as u64
    }

    #[inline(always)]
    fn cast_u64(num: u64) -> Self {
        num
    }

    #[inline(always)]
    fn zigzag(from: Self::Signed) -> Self {
        ((from << 1) ^ (from >> 63)) as Self
    }

    #[inline(always)]
    fn unzigzag(self) -> Self::Signed {
        ((self >> 1) ^ (-((self & 1) as i64)) as u64) as i64
    }
}

/// Represents a signed scalar value that can be encoded to and decoded from a varint in ZigZag
/// format.
pub trait SignedVarIntTarget: Debug + Eq + PartialEq + Sized + Copy {
    type Unsigned: VarIntTarget<Signed = Self>;

    /// ZigZag encodes this value
    #[inline(always)]
    fn zigzag(from: Self) -> Self::Unsigned {
        Self::Unsigned::zigzag(from)
    }

    /// ZigZag decodes this value
    #[inline(always)]
    fn unzigzag(from: Self::Unsigned) -> Self {
        Self::Unsigned::unzigzag(from)
    }
}

impl SignedVarIntTarget for i8 {
    type Unsigned = u8;
}

impl SignedVarIntTarget for i16 {
    type Unsigned = u16;
}

impl SignedVarIntTarget for i32 {
    type Unsigned = u32;
}

impl SignedVarIntTarget for i64 {
    type Unsigned = u64;
}
