package cn.rvport.backend.buildvalidation.bitcode;

public record RemoteBitcodeToolchain(
        String root,
        String clang,
        String clangxx,
        String llvmDis,
        String toolchainId,
        String version
) {
}
