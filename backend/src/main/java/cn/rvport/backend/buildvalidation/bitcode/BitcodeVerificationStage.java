package cn.rvport.backend.buildvalidation.bitcode;

/** 共享 BC 从文档读取到 LLVM worker 消费的稳定失败阶段。 */
public enum BitcodeVerificationStage {
    MANIFEST_PARSE,
    MANIFEST_SCHEMA,
    MANIFEST_IDENTITY,
    BUNDLE_LAYOUT,
    MEMBER_INTEGRITY,
    SOURCE_COMPILE_BINDING,
    MATERIALIZATION,
    LLVM_WORKER
}
