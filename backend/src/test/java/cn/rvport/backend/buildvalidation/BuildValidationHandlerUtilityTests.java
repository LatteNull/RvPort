package cn.rvport.backend.buildvalidation;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.archive.ArchiveCandidateRegistrar;
import cn.rvport.backend.buildvalidation.bitcode.BitcodeArtifactService;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.credential.CredentialService;
import cn.rvport.backend.environment.EnvironmentRepository;
import cn.rvport.backend.environment.EnvironmentRole;
import cn.rvport.backend.environment.EnvironmentStatus;
import cn.rvport.backend.environment.EnvironmentView;
import cn.rvport.backend.environment.runtime.SshClientAdapter;
import cn.rvport.backend.source.deploy.SourceDeployExecutor;
import cn.rvport.backend.source.deploy.SourceDeployRunView;
import cn.rvport.backend.source.deploy.SourceDeployStrategy;
import cn.rvport.backend.task.TaskExecutionException;
import cn.rvport.backend.task.TaskLogRepository;
import cn.rvport.backend.task.TaskLogType;
import cn.rvport.backend.task.TaskScriptPayloadService;
import cn.rvport.backend.task.ToolRunRepository;
import cn.rvport.backend.worker.TaskExecutionContext;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.jooq.JSONB;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class BuildValidationHandlerUtilityTests {

    @Mock private BuildValidationRepository repository;
    @Mock private SourceDeployExecutor sourceDeployExecutor;
    @Mock private EnvironmentRepository environmentRepository;
    @Mock private CredentialService credentialService;
    @Mock private TaskScriptPayloadService scriptPayloadService;
    @Mock private SshClientAdapter sshClientAdapter;
    @Mock private TaskLogRepository taskLogRepository;
    @Mock private ToolRunRepository toolRunRepository;
    @Mock private ArchiveCandidateRegistrar archiveCandidateRegistrar;
    @Mock private StoredArtifactService storedArtifactService;
    @Mock private BitcodeArtifactService bitcodeArtifactService;
    @Mock private TaskExecutionContext context;
    private BuildValidationHandler handler;

    @BeforeEach
    void setUp() {
        handler = new BuildValidationHandler(repository, sourceDeployExecutor, environmentRepository,
                credentialService, scriptPayloadService, sshClientAdapter, taskLogRepository, toolRunRepository,
                archiveCandidateRegistrar, storedArtifactService, bitcodeArtifactService, new ObjectMapper());
    }

    @Test
    void environmentExportsHandlesAbsentEmptyNullAndQuotedValues() {
        assertThat((String) invoke("environmentExports", (Object) null)).isEqualTo("");
        assertThat((String) invoke("environmentExports", Map.of())).isEqualTo("");
        java.util.LinkedHashMap<String, String> values = new java.util.LinkedHashMap<>();
        values.put("EMPTY", null);
        values.put("QUOTED", "a'b");
        assertThat((String) invoke("environmentExports", values))
                .isEqualTo("export EMPTY=''\nexport QUOTED='a'\"'\"'b'");
    }

    @Test
    void summaryAndBuildFactsUseDefaultsForOptionalInputFields() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID environmentId = UUID.randomUUID();
        BuildValidationTaskInput input = new BuildValidationTaskInput(projectId, UUID.randomUUID(), null,
                revisionId, environmentId, null, UUID.randomUUID(), "hash", 8, null, null);
        SourceDeployRunView deployment = new SourceDeployRunView(UUID.randomUUID(), projectId, UUID.randomUUID(),
                revisionId, environmentId, "/workspace", SourceDeployStrategy.TAR_OVER_SSH, false,
                cn.rvport.backend.task.TaskStatus.SUCCEEDED, 1, 2L, 0, JSONB.valueOf("{}"),
                OffsetDateTime.now(), OffsetDateTime.now(), OffsetDateTime.now());
        var result = new cn.rvport.backend.environment.runtime.SshCommandResult(
                0, "", "", Duration.ofMillis(12));

        Map<String, Object> summary = invoke("summary", input, deployment, result);
        Map<String, Object> facts = invoke("buildFacts", input, deployment, result, null, null, null, null);

        assertThat(summary).containsEntry("buildScope", "BOTH");
        assertThat(facts).containsEntry("buildScope", "BOTH");
        assertThat(facts.get("environmentVariableNames")).isEqualTo(java.util.List.of());
        Map<?, ?> compileDatabase = (Map<?, ?>) facts.get("compileDatabase");
        assertThat(compileDatabase.get("available")).isEqualTo(false);
        assertThat(compileDatabase.get("reason")).isEqualTo("NOT_COLLECTED");
    }

    @Test
    void remoteCompileDatabaseParserRecognizesEveryWireState() {
        assertRemoteReason(null, "NOT_AVAILABLE");
        assertRemoteReason("noise", "NOT_AVAILABLE");
        assertRemoteReason("RVPORT_COMPILE_DATABASE_STATUS=missing", "NOT_AVAILABLE");
        assertRemoteReason("RVPORT_COMPILE_DATABASE_STATUS=too_large", "SIZE_LIMIT_EXCEEDED");
        assertRemoteReason("RVPORT_COMPILE_DATABASE_STATUS=present", "BASE64_MISSING");
        assertRemoteReason("""
                RVPORT_COMPILE_DATABASE_STATUS=present
                RVPORT_COMPILE_DATABASE_BASE64_BEGIN

                RVPORT_COMPILE_DATABASE_BASE64_END
                """, "BASE64_EMPTY");

        Object available = invoke("parseRemoteCompileDatabase", """
                RVPORT_COMPILE_DATABASE_STATUS=present
                RVPORT_COMPILE_DATABASE_BASE64_BEGIN
                W10=
                RVPORT_COMPILE_DATABASE_BASE64_END
                """);
        assertThat((Boolean) ReflectionTestUtils.invokeMethod(available, "available")).isTrue();
        assertThat((String) ReflectionTestUtils.invokeMethod(available, "base64Content")).isEqualTo("W10=");
    }

    @Test
    void warningFormattingHandlesMissingExceptionAndMultilineMessages() {
        Map<String, Object> withoutException = invoke("compileDatabaseWarning", context, "FETCH_FAILED", null);
        Map<String, Object> withException = invoke("compileDatabaseWarning", context, "COLLECTION_FAILED",
                new IllegalStateException("line1\r\nline2"));

        assertThat(withoutException).containsEntry("available", false).containsEntry("mode", "FALLBACK");
        assertThat(withException).containsEntry("reason", "COLLECTION_FAILED");
        verify(context).log(eq(TaskLogType.STDERR), contains("exception=unknown message="));
        verify(context).log(eq(TaskLogType.STDERR), contains("message=line1  line2"));
    }

    @Test
    void categorizesExpectedErrorsAndRecognizesTimeoutVariants() {
        assertThat((String) invoke("category", new TaskExecutionException(
                "SOURCE_DEPLOY_FAILED", "failed", null))).isEqualTo("SOURCE_DEPLOYMENT_FAILED");
        assertThat((String) invoke("category", new TaskExecutionException(
                "TASK_RESOURCE_NOT_FOUND", "missing", null))).isEqualTo("REMOTE_COMMAND_FAILED");
        assertThat((String) invoke("category", new TaskExecutionException(
                "OTHER", "failed", null))).isEqualTo("UNKNOWN");

        assertThat((Boolean) invoke("isTimeout", new cn.rvport.backend.environment.runtime.SshRuntimeException(
                "command timeout"))).isTrue();
        assertThat((Boolean) invoke("isTimeout", new cn.rvport.backend.environment.runtime.SshRuntimeException(
                "命令超时"))).isTrue();
        assertThat((Boolean) invoke("isTimeout", new cn.rvport.backend.environment.runtime.SshRuntimeException(
                "connection reset"))).isFalse();
        assertThat((Integer) invoke("effectiveTimeout", (Object) null)).isEqualTo(3600);
        assertThat((Integer) invoke("effectiveTimeout", 3)).isEqualTo(10);
        assertThat((Integer) invoke("effectiveTimeout", 90)).isEqualTo(90);
    }

    @Test
    void validatesEnvironmentOwnershipEnablementAndCredentialReference() {
        UUID projectId = UUID.randomUUID();
        UUID environmentId = UUID.randomUUID();
        BuildValidationTaskInput input = input(projectId, environmentId);

        org.mockito.Mockito.when(environmentRepository.findById(environmentId)).thenReturn(Optional.empty());
        assertTaskError(() -> invoke("requireEnvironment", input), "TASK_RESOURCE_NOT_FOUND");

        org.mockito.Mockito.when(environmentRepository.findById(environmentId))
                .thenReturn(Optional.of(environment(environmentId, UUID.randomUUID(), true, UUID.randomUUID(), null)));
        assertTaskError(() -> invoke("requireEnvironment", input), "TASK_PROJECT_MISMATCH");

        org.mockito.Mockito.when(environmentRepository.findById(environmentId))
                .thenReturn(Optional.of(environment(environmentId, projectId, false, UUID.randomUUID(), null)));
        assertTaskError(() -> invoke("requireEnvironment", input), "TASK_RESOURCE_DISABLED");

        EnvironmentView missingCredential = environment(environmentId, projectId, true, null, null);
        org.mockito.Mockito.when(environmentRepository.findById(environmentId))
                .thenReturn(Optional.of(missingCredential));
        assertThat((EnvironmentView) invoke("requireEnvironment", input)).isEqualTo(missingCredential);
        assertTaskError(() -> invoke("target", missingCredential), "TASK_INPUT_INVALID");
    }

    @Test
    void validatesJumpHostExistenceOwnershipEnablementAndNesting() {
        UUID projectId = UUID.randomUUID();
        UUID jumpId = UUID.randomUUID();
        EnvironmentView target = environment(UUID.randomUUID(), projectId, true, UUID.randomUUID(), jumpId);

        org.mockito.Mockito.when(environmentRepository.findById(jumpId)).thenReturn(Optional.empty());
        assertTaskError(() -> invoke("requireJumpHost", target), "TASK_RESOURCE_NOT_FOUND");

        org.mockito.Mockito.when(environmentRepository.findById(jumpId))
                .thenReturn(Optional.of(environment(jumpId, UUID.randomUUID(), true, UUID.randomUUID(), null)));
        assertTaskError(() -> invoke("requireJumpHost", target), "TASK_PROJECT_MISMATCH");

        org.mockito.Mockito.when(environmentRepository.findById(jumpId))
                .thenReturn(Optional.of(environment(jumpId, projectId, false, UUID.randomUUID(), null)));
        assertTaskError(() -> invoke("requireJumpHost", target), "TASK_RESOURCE_DISABLED");

        org.mockito.Mockito.when(environmentRepository.findById(jumpId))
                .thenReturn(Optional.of(environment(jumpId, projectId, true, UUID.randomUUID(), UUID.randomUUID())));
        assertTaskError(() -> invoke("requireJumpHost", target), "TASK_UNSUPPORTED_OPERATION");

        EnvironmentView valid = environment(jumpId, projectId, true, UUID.randomUUID(), null);
        org.mockito.Mockito.when(environmentRepository.findById(jumpId)).thenReturn(Optional.of(valid));
        assertThat((EnvironmentView) invoke("requireJumpHost", target)).isEqualTo(valid);
    }

    @Test
    void recognizesEveryFinishedStatusAndMissingRun() {
        UUID runId = UUID.randomUUID();
        for (cn.rvport.backend.task.TaskStatus status : new cn.rvport.backend.task.TaskStatus[]{
                cn.rvport.backend.task.TaskStatus.SUCCEEDED,
                cn.rvport.backend.task.TaskStatus.FAILED,
                cn.rvport.backend.task.TaskStatus.CANCELLED,
                cn.rvport.backend.task.TaskStatus.TIMEOUT}) {
            org.mockito.Mockito.when(repository.findById(runId)).thenReturn(Optional.of(run(status)));
            assertThat((Boolean) invoke("isAlreadyFinished", runId)).isTrue();
        }
        org.mockito.Mockito.when(repository.findById(runId)).thenReturn(Optional.of(run(cn.rvport.backend.task.TaskStatus.RUNNING)));
        assertThat((Boolean) invoke("isAlreadyFinished", runId)).isFalse();
        org.mockito.Mockito.when(repository.findById(runId)).thenReturn(Optional.empty());
        assertThat((Boolean) invoke("isAlreadyFinished", runId)).isFalse();
    }

    private void assertRemoteReason(String stdout, String reason) {
        Object parsed = invoke("parseRemoteCompileDatabase", stdout);
        assertThat((Boolean) ReflectionTestUtils.invokeMethod(parsed, "available")).isFalse();
        assertThat((String) ReflectionTestUtils.invokeMethod(parsed, "reason")).isEqualTo(reason);
    }

    private void assertTaskError(org.assertj.core.api.ThrowableAssert.ThrowingCallable action, String errorCode) {
        assertThatThrownBy(action).isInstanceOfSatisfying(TaskExecutionException.class,
                ex -> assertThat(ex.errorCode()).isEqualTo(errorCode));
    }

    private BuildValidationTaskInput input(UUID projectId, UUID environmentId) {
        return new BuildValidationTaskInput(projectId, UUID.randomUUID(), null, UUID.randomUUID(), environmentId,
                null, UUID.randomUUID(), "hash", 8, 60, Map.of());
    }

    private EnvironmentView environment(
            UUID id, UUID projectId, boolean enabled, UUID credentialId, UUID jumpHostId
    ) {
        return new EnvironmentView(id, projectId, "env", EnvironmentRole.TARGET_RISCV, "riscv64",
                "host", 22, "root", credentialId, jumpHostId, "/workspace",
                enabled ? EnvironmentStatus.AVAILABLE : EnvironmentStatus.DISABLED, enabled,
                null, null, UUID.randomUUID(), OffsetDateTime.now(), null);
    }

    private BuildValidationRunView run(cn.rvport.backend.task.TaskStatus status) {
        return new BuildValidationRunView(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
                UUID.randomUUID(), null, null, "hash", "make", "/workspace", 60, null, status, null,
                null, null, null, null, null, OffsetDateTime.now(), Map.of());
    }

    @SuppressWarnings("unchecked")
    private <T> T invoke(String method, Object... args) {
        return (T) ReflectionTestUtils.invokeMethod(handler, method, args);
    }
}
