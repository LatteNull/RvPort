package cn.rvport.backend.environment.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.credential.CredentialService;
import cn.rvport.backend.environment.EnvironmentRepository;
import cn.rvport.backend.environment.EnvironmentRole;
import cn.rvport.backend.environment.EnvironmentStatus;
import cn.rvport.backend.environment.EnvironmentView;
import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskExecutionException;
import cn.rvport.backend.task.TaskLogEventService;
import cn.rvport.backend.task.TaskScriptPayloadService;
import cn.rvport.backend.task.TaskSecretPayloadService;
import cn.rvport.backend.task.ToolRunRepository;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import java.lang.reflect.Constructor;
import java.util.UUID;
import org.mockito.ArgumentCaptor;

class SshRuntimeServiceUtilityTests {

    private final SshRuntimeService service = new SshRuntimeService(
            mock(EnvironmentRepository.class), mock(CredentialService.class), mock(SshClientAdapter.class),
            mock(ToolRunRepository.class), mock(TaskScriptPayloadService.class), mock(TaskLogEventService.class),
            mock(TaskSecretPayloadService.class));

    @Test
    void sanitizesNestedExceptionMessagesAndLimitsDepthAndLength() {
        Throwable nested = new IllegalStateException("outer password=secret\nline",
                new IllegalArgumentException("token: abc",
                        new RuntimeException(" ",
                                new Exception("private_key=key", new Exception("not included")))));

        String summary = invoke("safeExceptionSummary", nested);
        assertThat(summary).contains("IllegalStateException", "password=****", "token: ****", "private_key=****")
                .doesNotContain("secret", "abc", "private_key=key", "not included", "\n", "\r");
        assertThat((String) invoke("safeExceptionSummary", (Throwable) null)).isEmpty();
        assertThat(((String) invoke("safeExceptionSummary", new RuntimeException("x".repeat(700))))).hasSize(500);
    }

    @Test
    void resolvesExplicitOrFallbackSshErrorCodes() {
        assertThat((String) invoke("sshErrorCode", new SshRuntimeException("failure")))
                .isEqualTo(TaskErrorCode.HANDLER_FAILED);
        assertThat((String) invoke("sshErrorCode", new SshRuntimeException(" ", "failure", null)))
                .isEqualTo(TaskErrorCode.HANDLER_FAILED);
        assertThat((String) invoke("sshErrorCode", new SshRuntimeException("SSH_TIMEOUT", "failure", null)))
                .isEqualTo("SSH_TIMEOUT");
    }

    @Test
    void classifiesManagedUnmanagedAndUnknownToolOrigins() {
        assertThat((String) invoke("installOrigin", "gcc", "/usr/bin/gcc")).isEqualTo("package");
        for (String path : List.of("/usr/local/bin/tool", "/opt/tool/bin/tool", "/root/.local/bin/tool",
                "/home/alice/.local/bin/tool", "\\opt\\tool\\bin\\tool")) {
            assertThat((String) invoke("installOrigin", null, path)).isEqualTo("unmanaged");
        }
        for (String path : java.util.Arrays.asList(null, "", " ", "/usr/bin/tool", "/home/alice/bin/tool")) {
            assertThat((String) invoke("installOrigin", "", path)).isEqualTo("unknown");
        }
    }

    @Test
    void normalizesArchitectureCandidatesNamesAndPaths() {
        assertThat((String) invoke("targetArchCandidate", null, "riscv64")).isEmpty();
        assertThat((String) invoke("targetArchCandidate", "", "riscv64")).isEmpty();
        assertThat((String) invoke("targetArchCandidate", "gcc", null)).isEqualTo("gcc");
        assertThat((String) invoke("targetArchCandidate", "gcc", " ")).isEqualTo("gcc");
        assertThat((String) invoke("targetArchCandidate", "gcc", "riscv64gc")).isEqualTo("gcc-riscv64");
        assertThat((String) invoke("targetArchCandidate", "gcc", "aarch64")).isEqualTo("gcc-aarch64");

        assertThat((String) invoke("stripArchTokens", (String) null)).isEmpty();
        assertThat((String) invoke("stripArchTokens", "lib-x86_64_amd64.x64-riscv64.so"))
                .isEqualTo("lib-so");
        assertThat((String) invoke("fileName", (String) null)).isEmpty();
        assertThat((String) invoke("fileName", "/usr/lib/libc.so")).isEqualTo("libc.so");
        assertThat((String) invoke("fileName", "C:\\tools\\gcc.exe")).isEqualTo("gcc.exe");
        assertThat((String) invoke("fileName", "gcc")).isEqualTo("gcc");
    }

    @Test
    void derivesNormalizedCandidatesAndCapabilitiesWithOptionalMetadata() {
        @SuppressWarnings("unchecked")
        Map<String, String> candidates = invoke("normalizedCandidates", "lib-x86_64.so", "/opt/x86_64/lib.so",
                "pkg-amd64", "riscv64");
        assertThat(candidates).containsEntry("normalizedName", "lib-so")
                .containsEntry("queryPattern", "*/lib-so")
                .containsEntry("normalizedPackage", "pkg")
                .containsEntry("targetPackageCandidate", "pkg-riscv64")
                .containsEntry("pathContainsArchToken", "true");

        @SuppressWarnings("unchecked")
        Map<String, String> empty = invoke("normalizedCandidates", null, null, null, null);
        assertThat(empty).containsEntry("originalName", "").containsEntry("queryPattern", "");

        @SuppressWarnings("unchecked")
        Map<String, String> capabilities = invoke("capabilities", Map.of(
                "elfSoname", "/lib/libc.so.6", "name", "libc.so.6", "ownerPackage", "glibc",
                "elfNeeded", "ld-linux.so.2,libm.so.6"));
        assertThat(capabilities).containsEntry("providesCapabilities", "libc.so.6,glibc")
                .containsEntry("requiredCapabilities", "ld-linux.so.2,libm.so.6");
        assertThat((Map<?, ?>) invoke("capabilities", Map.of())).isEmpty();
    }

    @Test
    void parsesScalarListMapCsvPackageAndPipeRecordInputs() {
        assertThat((int) invoke("intValue", (String) null)).isZero();
        assertThat((int) invoke("intValue", " ")).isZero();
        assertThat((int) invoke("intValue", " 12 ")).isEqualTo(12);
        assertThat((int) invoke("intValue", "bad")).isZero();
        assertThat((int) invoke("listSize", List.of(1, 2))).isEqualTo(2);
        assertThat((int) invoke("listSize", "not-list")).isZero();
        assertThat((int) invoke("mapSize", Map.of("a", 1))).isEqualTo(1);
        assertThat((int) invoke("mapSize", (Object) null)).isZero();
        assertThat((String) invoke("stringValue", (Object) null)).isEmpty();
        assertThat((String) invoke("stringValue", 42)).isEqualTo("42");

        assertThat((List<?>) invoke("splitCsv", (String) null)).isEmpty();
        assertThat((List<?>) invoke("splitCsv", " ")).isEmpty();
        assertThat(this.<List<String>>invoke("splitCsv", " a, ,b ")).containsExactly("a", "b");
        assertThat(this.<List<String>>invoke("defaultList", null, List.of("default"))).containsExactly("default");
        assertThat(this.<List<String>>invoke("defaultList", List.of(), List.of("default"))).containsExactly("default");
        assertThat(this.<List<String>>invoke("defaultList", List.of("A", "A", "B"), List.of()))
                .containsExactly("A", "B");

        assertThat((List<?>) invoke("packages", "noise\nPACKAGE=gcc|12|x86_64\nPACKAGE=make||"))
                .hasSize(2);
        @SuppressWarnings("unchecked")
        List<Map<String, String>> records = invoke("pipeRecords", "ROW=a|b\nROW=c\nnoise", "ROW:", List.of("one"));
        assertThat(records).isEmpty();
        records = invoke("pipeRecords", "ROW=a|b\nROW=c\nnoise", "ROW=", List.of("one", "two", "three"));
        assertThat(records).containsExactly(
                Map.of("one", "a", "two", "b", "three", ""),
                Map.of("one", "c", "two", "", "three", ""));
        Map<?, ?> mapped = invoke("mapValue", Map.of("a", 1));
        assertThat(mapped.get("a")).isEqualTo(1);
        assertThat((Map<?, ?>) invoke("mapValue", "not-map")).isEmpty();
    }

    @Test
    void buildsComponentMetadataFromOnlyNonBlankKnownFields() {
        Map<String, String> input = new LinkedHashMap<>();
        input.put("name", "libc.so.6");
        input.put("ownerPackage", "glibc");
        input.put("ownerVersion", " ");
        input.put("unknown", "ignored");
        input.put("elfSoname", null);

        @SuppressWarnings("unchecked")
        Map<String, String> metadata = invoke("componentMetadata", input);
        assertThat(metadata).containsEntry("filename", "libc.so.6")
                .containsEntry("ownerPackage", "glibc")
                .doesNotContainKeys("ownerVersion", "unknown", "elfSoname");
    }

    @Test
    void parsesProbeAndCheckOutputWithoutExternalExecution() {
        SshCommandResult result = new SshCommandResult(0, """
                RVPORT_PROBE=ok
                KERNEL_NAME=Linux
                WORKDIR_EXISTS=true
                WORKDIR_READABLE=false
                TOOL_GCC_PRESENT=true
                RVPORT_CHECK=ok
                CHECK_ITEMS=CONNECTION, BASIC_TOOLS
                TOOL_VERSION_GCC=gcc 12.2
                PERMISSION_TEMP_WRITABLE=true
                PARSE_WARNING=sample warning
                """, "", Duration.ofMillis(50));
        @SuppressWarnings("unchecked")
        Map<String, Object> probe = invoke("parseProbe", result);
        @SuppressWarnings("unchecked")
        Map<String, Object> check = invoke("parseCheck", result);

        assertThat(probe).containsEntry("probe", "ok").containsEntry("durationMs", 50L);
        assertThat(((Map<?, ?>) probe.get("basicTools")).get("gcc")).isEqualTo(true);
        assertThat(check).containsEntry("check", "ok");
        assertThat((List<String>) check.get("checkItems")).containsExactly("CONNECTION", "BASIC_TOOLS");
        assertThat((List<String>) check.get("parseWarnings")).containsExactly("sample warning");
    }

    @Test
    void parsesCollectionMetadataCompletenessAndEnrichesKnownAndUnknownFiles() {
        SshCommandResult result = new SshCommandResult(0, """
                RVPORT_COLLECT=ok
                COLLECT_SCOPES=OS, NATIVE_FILES
                MACHINE_ARCH=riscv64
                REPO_SOURCE_COUNT=bad
                REPO_METADATA_STATUS=FAILED|dnf|offline
                REPO_METADATA_STATUS=AVAILABLE|rpm|cached
                TOOL_VERSION_GCC=gcc 13.2
                PROVIDER=/usr/lib/libknown.so|known-pkg|2.1|riscv64|rpm
                ELF=/usr/lib/libknown.so|libknown.so.2|libc.so.6|RISC-V|ELF64|readelf
                LIBRARY=libknown.so|/usr/lib/libknown.so
                LIBRARY=libunknown.so|/opt/libunknown.so
                PARSE_WARNING=warning
                """, "", Duration.ofMillis(7));

        @SuppressWarnings("unchecked")
        Map<String, Object> summary = invoke("parseCollect", result);
        assertThat(summary).containsEntry("collect", "ok").containsEntry("durationMs", 7L);
        assertThat(this.<Map<String, Object>>cast(summary.get("repositories")))
                .containsEntry("sourceFileCount", 0)
                .containsEntry("metadataComplete", true);
        @SuppressWarnings("unchecked")
        List<Map<String, String>> libraries = (List<Map<String, String>>) summary.get("libraries");
        assertThat(libraries.get(0))
                .containsEntry("ownerPackage", "known-pkg")
                .containsEntry("elfSoname", "libknown.so.2")
                .containsEntry("requiredCapabilities", "libc.so.6");
        assertThat(libraries.get(1))
                .containsEntry("normalizedPackage", "")
                .doesNotContainKeys("ownerPackage", "elfSoname");

        SshCommandResult incomplete = new SshCommandResult(0,
                "RVPORT_COLLECT=ok\nREPO_METADATA_STATUS=FAILED|dnf|offline\n", "", Duration.ZERO);
        Map<String, Object> incompleteSummary = invoke("parseCollect", incomplete);
        assertThat(this.<Map<String, Object>>cast(incompleteSummary.get("repositories")))
                .containsEntry("metadataComplete", false);
    }

    @Test
    void createsTargetRepositoryComponentsWithEveryNameFallback() {
        EnvironmentRepository repository = mock(EnvironmentRepository.class);
        SshRuntimeService isolated = new SshRuntimeService(
                repository, mock(CredentialService.class), mock(SshClientAdapter.class),
                mock(ToolRunRepository.class), mock(TaskScriptPayloadService.class),
                mock(TaskLogEventService.class), mock(TaskSecretPayloadService.class));
        UUID snapshotId = UUID.randomUUID();
        EnvironmentView environment = environment(EnvironmentRole.TARGET_RISCV, true, null, UUID.randomUUID());
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("arch", "riscv64");
        summary.put("repositoryProvides", List.of(
                Map.of("queryValue", "libexplicit.so", "path", "/repo/libpath.so", "packageName", "pkg-a"),
                Map.of("queryValue", "", "path", "/repo/libpath.so", "packageName", "pkg-b"),
                Map.of("queryValue", "", "packageName", "pkg-c")));

        ReflectionTestUtils.invokeMethod(isolated, "createCollectedComponents", snapshotId, environment, summary);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<EnvironmentRepository.ComponentInput>> captor = ArgumentCaptor.forClass(List.class);
        verify(repository).createComponents(org.mockito.ArgumentMatchers.eq(snapshotId),
                org.mockito.ArgumentMatchers.eq(environment.projectId()), captor.capture());
        assertThat(captor.getValue()).extracting(EnvironmentRepository.ComponentInput::name)
                .containsExactly("libexplicit.so", "libpath.so", "pkg-c");
    }

    @Test
    void resolvesBuiltInAndCustomScriptCommandsAndRejectsUnsupportedRequests() throws Exception {
        EnvironmentView environment = new EnvironmentView(
                java.util.UUID.randomUUID(), java.util.UUID.randomUUID(), "env",
                EnvironmentRole.GENERAL_EXECUTION, "x86_64", "host", 22, "user",
                java.util.UUID.randomUUID(), null, "/default work", EnvironmentStatus.UNKNOWN,
                true, null, null, java.util.UUID.randomUUID(), OffsetDateTime.now(), OffsetDateTime.now());
        Class<?> runtimeType = Class.forName(
                "cn.rvport.backend.environment.runtime.SshRuntimeService$RuntimeEnvironment");
        Constructor<?> constructor = runtimeType.getDeclaredConstructor(
                EnvironmentView.class, EnvironmentView.class, boolean.class);
        constructor.setAccessible(true);
        Object runtime = constructor.newInstance(environment, null, true);

        assertThat((String) invoke("scriptCommand", input("BUILTIN_SCRIPT", Map.of("name", "PRINT_WORKDIR"), null), runtime))
                .isEqualTo("pwd");
        assertThat((String) invoke("scriptCommand", input("BUILTIN_SCRIPT", Map.of("name", "ENV_INFO"), null), runtime))
                .contains("RVPORT_PROBE=ok", "RVPORT_WORKDIR='/default work'");
        assertThat((String) invoke("scriptCommand", input("CUSTOM_BASH", null, "/custom's work"), runtime))
                .contains("mktemp", "cd '/custom'\"'\"'s work'");
        assertThat(service.temporaryScriptCommand(null)).doesNotContain("cd ");
        assertThat(service.temporaryScriptCommand(" ")).doesNotContain("cd ");

        assertThatThrownBy(() -> invoke("scriptCommand", input("BUILTIN_SCRIPT", null, null), runtime))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("脚本类型暂不支持执行");
        assertThatThrownBy(() -> invoke("scriptCommand", input("UNKNOWN", Map.of(), null), runtime))
                .isInstanceOf(TaskExecutionException.class);
    }

    @Test
    void runtimeWorkingDirectoryUsesConfiguredValueOrEnvironmentFallback() throws Exception {
        EnvironmentView environment = environment(EnvironmentRole.GENERAL_EXECUTION, true, null, UUID.randomUUID());
        Class<?> runtimeType = Class.forName(
                "cn.rvport.backend.environment.runtime.SshRuntimeService$RuntimeEnvironment");
        Constructor<?> constructor = runtimeType.getDeclaredConstructor(
                EnvironmentView.class, EnvironmentView.class, boolean.class);
        constructor.setAccessible(true);
        Object runtime = constructor.newInstance(environment, null, false);

        assertThat((String) ReflectionTestUtils.invokeMethod(runtime, "workingDirectory",
                input(null, null, null))).isEqualTo(environment.workingDirectory());
        assertThat((String) ReflectionTestUtils.invokeMethod(runtime, "workingDirectory",
                input(null, null, "  "))).isEqualTo(environment.workingDirectory());
        assertThat((String) ReflectionTestUtils.invokeMethod(runtime, "workingDirectory",
                input(null, null, "/override"))).isEqualTo("/override");
    }

    @Test
    void targetRejectsEnvironmentWithoutAnyCredentialReference() {
        EnvironmentView environment = new EnvironmentView(
                UUID.randomUUID(), UUID.randomUUID(), "env", EnvironmentRole.GENERAL_EXECUTION,
                "x86_64", "host", 22, "user", null, null, "/work", EnvironmentStatus.UNKNOWN,
                true, null, null, UUID.randomUUID(), OffsetDateTime.now(), OffsetDateTime.now());

        assertThatThrownBy(() -> invoke("target", environment, null, null))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("SSH 凭据引用不存在");
    }

    @Test
    void buildsCheckAndCollectionCommandsForDefaultAndExplicitOptions() throws Exception {
        EnvironmentView environment = environment(EnvironmentRole.SOURCE_X86, true, null, UUID.randomUUID());
        Class<?> runtimeType = Class.forName(
                "cn.rvport.backend.environment.runtime.SshRuntimeService$RuntimeEnvironment");
        Constructor<?> constructor = runtimeType.getDeclaredConstructor(
                EnvironmentView.class, EnvironmentView.class, boolean.class);
        constructor.setAccessible(true);
        Object runtime = constructor.newInstance(environment, null, true);

        String defaultCheck = invoke("checkCommand", input(null, null, null), runtime);
        String explicitCheck = invoke("checkCommand",
                new EnvironmentTaskInput(environment.projectId(), environment.id(), null, 30, null,
                        List.of("CONNECTION", "CONNECTION"), null, "/explicit", null, null, null), runtime);
        assertThat(defaultCheck).contains("/default work", "CONNECTION,BASIC_TOOLS,WORKING_DIRECTORY,PERMISSIONS");
        assertThat(explicitCheck).contains("/explicit", "CHECK_ITEMS=%s\\n' 'CONNECTION'");

        String source = invoke("collectCommand", null, false, null);
        String target = invoke("collectCommand", List.of("OS", "OS"), true, "TARGET_RISCV");
        assertThat(source).contains("collect_repo=false", "environment_role=''");
        assertThat(target).contains("collect_repo=true", "environment_role='TARGET_RISCV'", "COLLECT_SCOPES=%s\\n' 'OS'");
    }

    @Test
    void extractsVersionMajorAndKeyValueLinesAtBoundaries() {
        assertThat((String) invoke("versionMajor", (String) null)).isEmpty();
        assertThat((String) invoke("versionMajor", "version unknown")).isEmpty();
        assertThat((String) invoke("versionMajor", "gcc 14.2.1")).isEqualTo("14");
        @SuppressWarnings("unchecked")
        Map<String, String> values = invoke("keyValues", "ignored\nA=1\n=invalid\nB=x=y\n");
        assertThat(values).hasSize(2).containsEntry("A", "1").containsEntry("B", "x=y");
    }

    private EnvironmentTaskInput input(String scriptType, Map<String, String> parameters, String workdir) {
        return new EnvironmentTaskInput(
                java.util.UUID.randomUUID(), java.util.UUID.randomUUID(), null, 30, scriptType,
                null, null, workdir, parameters, null, null);
    }

    private EnvironmentView environment(
            EnvironmentRole role,
            boolean enabled,
            UUID jumpHostId,
            UUID projectId
    ) {
        return new EnvironmentView(
                UUID.randomUUID(), projectId, "env", role, "riscv64", "host", 22, "user",
                UUID.randomUUID(), jumpHostId, "/default work",
                enabled ? EnvironmentStatus.UNKNOWN : EnvironmentStatus.DISABLED,
                enabled, null, null, UUID.randomUUID(), OffsetDateTime.now(), OffsetDateTime.now());
    }

    @SuppressWarnings("unchecked")
    private <T> T invoke(String method, Object... args) {
        return (T) ReflectionTestUtils.invokeMethod(service, method, args);
    }

    @SuppressWarnings("unchecked")
    private <T> T cast(Object value) {
        return (T) value;
    }
}
