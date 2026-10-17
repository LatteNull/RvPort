import { SolverType } from "./solver-type";

export const environment = {
  refreshSidebar: true,
  supportedSolverTypes: new Set<SolverType>([
    SolverType.MAKEFILE,
    SolverType.INTRINSICS,
    SolverType.BUILTIN,
    SolverType.MACROS,
    SolverType.INCODE_ASM,
    SolverType.ASM_FILE,
    SolverType.JAVA_SOURCE_CODE,
    SolverType.PYTHON_SOURCE_CODE,
    SolverType.GO_SOURCE_CODE,
    SolverType.SHELL_SOURRCE_CODE,
    SolverType.BUILD_SCRIPT,
    SolverType.GO_RELEASER_TML,
    SolverType.RUST_SOURCE_CODE,
    SolverType.RUST_TOML_CODE,
  ]),

  // 大文件上传flag
  CHUNK_SIZE: 5 * 1024 * 1024, // 5MB分块大小
  MAX_CONCURRENT_UPLOADS: 5, // 最大并发上传数
  Big_File_Info: 1024 * 1024 * 500, // 超过500MB大文件提醒

  // 最大上传文件大小限制
  MaxSize: 2 * 1024 * 1024 * 1024
};
