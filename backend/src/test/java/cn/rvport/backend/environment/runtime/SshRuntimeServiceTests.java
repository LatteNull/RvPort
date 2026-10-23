package cn.rvport.backend.environment.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.credential.CredentialKind;
import cn.rvport.backend.credential.CredentialService;
import cn.rvport.backend.environment.EnvironmentRepository;
import cn.rvport.backend.environment.EnvironmentRole;
import cn.rvport.backend.environment.EnvironmentStatus;
import cn.rvport.backend.environment.EnvironmentView;
import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskExecutionException;
import cn.rvport.backend.task.TaskLogType;
import cn.rvport.backend.task.TaskLogEventService;
import cn.rvport.backend.task.TaskSecretPayloadService;
import cn.rvport.backend.task.TaskScriptPayloadService;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskView;
import cn.rvport.backend.task.ToolRunRepository;
import cn.rvport.backend.worker.TaskExecutionContext;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class SshRuntimeServiceTests {

    @Mock
    private EnvironmentRepository environmentRepository;

    @Mock
    private CredentialService credentialService;

    @Mock
    private SshClientAdapter sshClientAdapter;

    @Mock
    private ToolRunRepository toolRunRepository;

    @Mock
    private TaskScriptPayloadService taskScriptPayloadService;

    @Mock
    private TaskLogEventService taskLogEventService;

    @Mock
    private TaskSecretPayloadService taskSecretPayloadService;

    @Mock
    private TaskExecutionContext context;

    @org.junit.jupiter.api.BeforeEach
    void executeGuardedPublications() {
        org.mockito.Mockito.lenient().when(context.publish(any())).thenAnswer(invocation ->
                invocation.<java.util.function.Supplier<?>>getArgument(0).get());
    }

    @Test
    void testConnectionRunsProbeAndStoresSafeSummary() {
        SshRuntimeService service = service();
        EnvironmentView environment = environment(null);
        TaskView task = task(environment.projectId());
        UUID toolRunId = UUID.randomUUID();
        when(context.task()).thenReturn(task);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(credentialService.sshRuntimeCredential(environment.credentialId(), environment.projectId()))
                .thenReturn(new CredentialService.SshRuntimeCredential(
                        environment.credentialId(),
                        CredentialKind.SSH_PASSWORD,
                        environment.username(),
                        "SecretPassword",
                        null,
                        null
                ));
        when(toolRunRepository.create(eq(task.projectId()), eq(task.id()), any(), any(), any(), eq(TaskStatus.RUNNING), any()))
                .thenReturn(toolRunId);
        when(sshClientAdapter.execute(any())).thenReturn(new SshCommandResult(
                0,
                """
                        RVPORT_PROBE=ok
                        KERNEL_NAME=Linux
                        KERNEL_VERSION=6.1
                        MACHINE_ARCH=x86_64
                        REMOTE_USER=deploy
                        WORKDIR_EXISTS=true
                        WORKDIR_READABLE=true
                        WORKDIR_WRITABLE=false
                        TOOL_git_PRESENT=true
                        TOOL_mvn_PRESENT=false
                        """,
                "",
                Duration.ofMillis(123)
        ));

        service.testConnection(new EnvironmentTaskInput(environment.projectId(), environment.id(), null, 20), context);

        ArgumentCaptor<SshCommandRequest> requestCaptor = ArgumentCaptor.forClass(SshCommandRequest.class);
        verify(sshClientAdapter).execute(requestCaptor.capture());
        SshCommandRequest request = requestCaptor.getValue();
        assertThat(request.target().host()).isEqualTo(environment.host());
        assertThat(request.target().credential().password()).isEqualTo("SecretPassword");
        assertThat(request.command()).contains("RVPORT_PROBE=ok");
        assertThat(request.command()).doesNotContain("SecretPassword");

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> summaryCaptor = ArgumentCaptor.forClass(Map.class);
        verify(toolRunRepository).finish(eq(toolRunId), eq(TaskStatus.SUCCEEDED), eq(0), summaryCaptor.capture());
        assertThat(summaryCaptor.getValue())
                .containsEntry("probe", "ok")
                .containsEntry("kernelName", "Linux")
                .containsEntry("durationMs", 123L);
        assertThat(summaryCaptor.getValue().toString()).doesNotContain("SecretPassword");
        verify(environmentRepository).updateConnectionStatus(
                environment.id(), environment.configVersion(), EnvironmentStatus.AVAILABLE, true);
        verify(context).progress(10, "开始 SSH 连接探测");
        verify(context).progress(90, "SSH 连接探测完成");
        verify(context).log(eq(TaskLogType.STDOUT), any());
        verify(context).log(TaskLogType.STDERR, "");
    }

    @Test
    void testConnectionMarksEnvironmentUnavailableAndKeepsExitCodeWhenProbeFails() {
        SshRuntimeService service = service();
        EnvironmentView environment = environment(null);
        TaskView task = task(environment.projectId());
        UUID toolRunId = UUID.randomUUID();
        when(context.task()).thenReturn(task);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(credentialService.sshRuntimeCredential(environment.credentialId(), environment.projectId()))
                .thenReturn(new CredentialService.SshRuntimeCredential(
                        environment.credentialId(),
                        CredentialKind.SSH_PASSWORD,
                        environment.username(),
                        "SecretPassword",
                        null,
                        null
                ));
        when(toolRunRepository.create(eq(task.projectId()), eq(task.id()), any(), any(), any(), eq(TaskStatus.RUNNING), any()))
                .thenReturn(toolRunId);
        when(sshClientAdapter.execute(any())).thenReturn(new SshCommandResult(
                7,
                "RVPORT_PROBE=ok\n",
                "permission denied",
                Duration.ofMillis(50)
        ));

        assertThatThrownBy(() -> service.testConnection(new EnvironmentTaskInput(environment.projectId(), environment.id(), null, 20), context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("SSH 探测命令执行失败")
                .extracting("errorCode")
                .isEqualTo(TaskErrorCode.REMOTE_COMMAND_FAILED);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> summaryCaptor = ArgumentCaptor.forClass(Map.class);
        verify(toolRunRepository).finish(eq(toolRunId), eq(TaskStatus.FAILED), eq(7), summaryCaptor.capture());
        assertThat(summaryCaptor.getValue()).containsEntry("error", "SSH 探测命令执行失败");
        verify(environmentRepository).updateConnectionStatus(
                environment.id(), environment.configVersion(), EnvironmentStatus.UNAVAILABLE, false);
        verify(context, never()).progress(90, "SSH 连接探测完成");
    }

    @Test
    void testConnectionRejectsSuccessfulCommandWithInvalidProbeMarker() {
        SshRuntimeService service = service();
        EnvironmentView environment = environment(null);
        TaskView task = task(environment.projectId());
        UUID toolRunId = UUID.randomUUID();
        when(context.task()).thenReturn(task);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(credentialService.sshRuntimeCredential(environment.credentialId(), environment.projectId()))
                .thenReturn(passwordCredential(environment));
        when(toolRunRepository.create(eq(task.projectId()), eq(task.id()), any(), any(), any(),
                eq(TaskStatus.RUNNING), any())).thenReturn(toolRunId);
        when(sshClientAdapter.execute(any())).thenReturn(new SshCommandResult(
                0, "RVPORT_PROBE=invalid\n", "", Duration.ZERO));

        assertThatThrownBy(() -> service.testConnection(
                new EnvironmentTaskInput(environment.projectId(), environment.id(), null, 20), context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("SSH 探测输出无效");

        verify(toolRunRepository).finish(eq(toolRunId), eq(TaskStatus.FAILED), eq(0), any());
    }

    @Test
    void testConnectionPassesJumpHostTargetToAdapter() {
        SshRuntimeService service = service();
        UUID projectId = UUID.randomUUID();
        EnvironmentView jumpHost = environment(projectId, null);
        EnvironmentView target = environment(projectId, jumpHost.id());
        TaskView task = task(target.projectId());
        when(context.task()).thenReturn(task);
        when(environmentRepository.findById(target.id())).thenReturn(Optional.of(target));
        when(environmentRepository.findById(jumpHost.id())).thenReturn(Optional.of(jumpHost));
        when(credentialService.sshRuntimeCredential(any(), eq(projectId)))
                .thenAnswer(invocation -> new CredentialService.SshRuntimeCredential(
                        invocation.getArgument(0),
                        CredentialKind.SSH_PASSWORD,
                        "deploy",
                        "SecretPassword",
                        null,
                        null
                ));
        when(toolRunRepository.create(eq(task.projectId()), eq(task.id()), any(), any(), any(), eq(TaskStatus.RUNNING), any()))
                .thenReturn(UUID.randomUUID());
        when(sshClientAdapter.execute(any())).thenReturn(new SshCommandResult(0, "RVPORT_PROBE=ok\n", "", Duration.ofMillis(1)));

        service.testConnection(new EnvironmentTaskInput(target.projectId(), target.id(), jumpHost.id(), 20), context);

        ArgumentCaptor<SshCommandRequest> requestCaptor = ArgumentCaptor.forClass(SshCommandRequest.class);
        verify(sshClientAdapter).execute(requestCaptor.capture());
        assertThat(requestCaptor.getValue().target().environmentId()).isEqualTo(target.id());
        assertThat(requestCaptor.getValue().jumpHost().environmentId()).isEqualTo(jumpHost.id());
    }

    @Test
    void testConnectionSupportsUnpersistedTargetWithoutUpdatingEnvironmentStatus() {
        SshRuntimeService service = service();
        UUID projectId = UUID.randomUUID();
        UUID credentialId = UUID.randomUUID();
        TaskView task = task(projectId);
        UUID toolRunId = UUID.randomUUID();
        when(context.task()).thenReturn(task);
        when(credentialService.sshRuntimeCredential(credentialId, projectId))
                .thenReturn(new CredentialService.SshRuntimeCredential(
                        credentialId,
                        CredentialKind.SSH_PASSWORD,
                        "root",
                        "SecretPassword",
                        null,
                        null
                ));
        when(toolRunRepository.create(eq(task.projectId()), eq(task.id()), any(), any(), any(), eq(TaskStatus.RUNNING), any()))
                .thenReturn(toolRunId);
        when(sshClientAdapter.execute(any())).thenReturn(new SshCommandResult(0, "RVPORT_PROBE=ok\n", "", Duration.ofMillis(1)));

        service.testConnection(new EnvironmentTaskInput(
                projectId,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                new EnvironmentTaskInput.Target(
                        EnvironmentRole.TARGET_RISCV,
                        "riscv64",
                        "192.0.2.30",
                        22,
                        "root",
                        credentialId,
                        null,
                        null,
                        "/workspace"
                )
        ), context);

        ArgumentCaptor<SshCommandRequest> requestCaptor = ArgumentCaptor.forClass(SshCommandRequest.class);
        verify(sshClientAdapter).execute(requestCaptor.capture());
        assertThat(requestCaptor.getValue().target().environmentId()).isNull();
        assertThat(requestCaptor.getValue().target().host()).isEqualTo("192.0.2.30");
        verify(environmentRepository, never()).findById(any());
        verify(environmentRepository, never()).updateConnectionStatus(any(), anyLong(), any(), anyBoolean());
        verify(toolRunRepository).finish(eq(toolRunId), eq(TaskStatus.SUCCEEDED), eq(0), any());
    }

    @Test
    void testConnectionUsesTemporaryCredentialPayloadForUnpersistedTarget() {
        SshRuntimeService service = service();
        UUID projectId = UUID.randomUUID();
        UUID payloadId = UUID.randomUUID();
        TaskView task = task(projectId);
        UUID toolRunId = UUID.randomUUID();
        when(context.task()).thenReturn(task);
        when(taskSecretPayloadService.requireSshPrecheckCredential(payloadId, projectId, task.id(), "1".repeat(64)))
                .thenReturn(new TaskSecretPayloadService.SshPrecheckCredential(
                        CredentialKind.SSH_KEY,
                        "root",
                        null,
                        "PRIVATE KEY",
                        "KeyPassphrase"
                ));
        when(toolRunRepository.create(eq(task.projectId()), eq(task.id()), any(), any(), any(), eq(TaskStatus.RUNNING), any()))
                .thenReturn(toolRunId);
        when(sshClientAdapter.execute(any())).thenReturn(new SshCommandResult(0, "RVPORT_PROBE=ok\n", "", Duration.ofMillis(1)));

        service.testConnection(new EnvironmentTaskInput(
                projectId,
                null,
                null,
                30,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                new EnvironmentTaskInput.Target(
                        EnvironmentRole.TARGET_RISCV,
                        "riscv64",
                        "192.0.2.31",
                        22,
                        "root",
                        null,
                        payloadId,
                        "1".repeat(64),
                        "/root"
                )
        ), context);

        ArgumentCaptor<SshCommandRequest> requestCaptor = ArgumentCaptor.forClass(SshCommandRequest.class);
        verify(sshClientAdapter).execute(requestCaptor.capture());
        assertThat(requestCaptor.getValue().target().credential().kind()).isEqualTo(CredentialKind.SSH_KEY);
        assertThat(requestCaptor.getValue().target().credential().privateKey()).isEqualTo("PRIVATE KEY");
        assertThat(requestCaptor.getValue().target().credential().passphrase()).isEqualTo("KeyPassphrase");
        verify(credentialService, never()).sshRuntimeCredential(any(), any());
        verify(environmentRepository, never()).updateConnectionStatus(any(), anyLong(), any(), anyBoolean());
    }

    @Test
    void checkEnvironmentStoresCheckResultsAndBasicSnapshot() {
        SshRuntimeService service = service();
        EnvironmentView environment = environment(null);
        TaskView task = task(environment.projectId());
        UUID toolRunId = UUID.randomUUID();
        UUID snapshotId = UUID.randomUUID();
        when(context.task()).thenReturn(task);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(credentialService.sshRuntimeCredential(environment.credentialId(), environment.projectId()))
                .thenReturn(passwordCredential(environment));
        when(toolRunRepository.create(eq(task.projectId()), eq(task.id()), eq("rvport-env-check"), any(), any(), eq(TaskStatus.RUNNING), any()))
                .thenReturn(toolRunId);
        when(environmentRepository.createSnapshot(eq(environment.id()), eq(environment.projectId()), eq(task.id()),
                eq("Debian"), eq("13"), eq("6.1"), eq("x86_64"), eq("apt"), any(), any(), any(),
                eq(TaskStatus.SUCCEEDED), any(), eq(environment.configVersion())))
                .thenReturn(snapshotId);
        when(sshClientAdapter.execute(any())).thenReturn(new SshCommandResult(
                0,
                """
                        RVPORT_PROBE=ok
                        RVPORT_CHECK=ok
                        CHECK_ITEMS=CONNECTION,BASIC_TOOLS
                        KERNEL_NAME=Linux
                        KERNEL_VERSION=6.1
                        MACHINE_ARCH=x86_64
                        OS_NAME=Debian
                        OS_VERSION=13
                        PACKAGE_MANAGER=apt
                        REMOTE_USER=deploy
                        WORKDIR_EXISTS=true
                        WORKDIR_READABLE=true
                        WORKDIR_WRITABLE=true
                        PERMISSION_TEMP_WRITABLE=true
                        TOOL_git_PRESENT=true
                        TOOL_VERSION_git=git version 2.47.0
                        """,
                "",
                Duration.ofMillis(88)
        ));

        service.checkEnvironment(new EnvironmentTaskInput(
                environment.projectId(), environment.id(), null, 20, "ENV_CHECK",
                java.util.List.of("CONNECTION", "BASIC_TOOLS"), null, "/tmp", null, null, null), context);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> summaryCaptor = ArgumentCaptor.forClass(Map.class);
        verify(toolRunRepository).finish(eq(toolRunId), eq(TaskStatus.SUCCEEDED), eq(0), summaryCaptor.capture());
        assertThat(summaryCaptor.getValue())
                .containsEntry("check", "ok")
                .containsEntry("snapshotId", snapshotId)
                .containsEntry("snapshotKind", "BASIC_CHECK")
                .containsEntry("osName", "Debian")
                .containsEntry("packageManager", "apt")
                .containsKey("checkResults")
                .containsKey("toolVersions");
        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> rawCaptor = ArgumentCaptor.forClass(Map.class);
        verify(environmentRepository).createSnapshot(eq(environment.id()), eq(environment.projectId()), eq(task.id()),
                eq("Debian"), eq("13"), eq("6.1"), eq("x86_64"), eq("apt"), eq(Map.of()), any(), rawCaptor.capture(),
                eq(TaskStatus.SUCCEEDED), any(), eq(environment.configVersion()));
        assertThat(rawCaptor.getValue())
                .containsEntry("snapshotKind", "BASIC_CHECK")
                .containsKey("basicTools")
                .containsKey("permissions");
        verify(environmentRepository).updateLastCollectedAt(environment.id(), environment.configVersion());
        verify(environmentRepository, never()).createComponents(any(), any(), any());
    }

    @Test
    void checkEnvironmentFailureDoesNotCreateSnapshotOrUpdateCollectedAt() {
        SshRuntimeService service = service();
        EnvironmentView environment = environment(null);
        TaskView task = task(environment.projectId());
        UUID toolRunId = UUID.randomUUID();
        when(context.task()).thenReturn(task);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(credentialService.sshRuntimeCredential(environment.credentialId(), environment.projectId()))
                .thenReturn(passwordCredential(environment));
        when(toolRunRepository.create(eq(task.projectId()), eq(task.id()), eq("rvport-env-check"), any(), any(), eq(TaskStatus.RUNNING), any()))
                .thenReturn(toolRunId);
        when(sshClientAdapter.execute(any())).thenReturn(new SshCommandResult(
                2,
                """
                        RVPORT_PROBE=ok
                        RVPORT_CHECK=failed
                        CHECK_ITEMS=CONNECTION
                        """,
                "failed",
                Duration.ofMillis(88)
        ));

        assertThatThrownBy(() -> service.checkEnvironment(new EnvironmentTaskInput(
                environment.projectId(), environment.id(), null, 20, "ENV_CHECK",
                java.util.List.of("CONNECTION"), null, "/tmp", null, null, null), context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("环境检查失败");

        verify(toolRunRepository).finish(eq(toolRunId), eq(TaskStatus.FAILED), eq(2), any());
        verify(environmentRepository, never()).createSnapshot(any(), any(), any(), any(), any(), any(), any(), any(),
                any(), any(), any(), any(), any(), anyLong());
        verify(environmentRepository, never()).updateLastCollectedAt(any(), anyLong());
    }

    @Test
    void collectEnvironmentCreatesSnapshotAndToolComponents() {
        SshRuntimeService service = service();
        EnvironmentView environment = environment(null);
        TaskView task = task(environment.projectId());
        UUID toolRunId = UUID.randomUUID();
        UUID snapshotId = UUID.randomUUID();
        when(context.task()).thenReturn(task);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(credentialService.sshRuntimeCredential(environment.credentialId(), environment.projectId()))
                .thenReturn(passwordCredential(environment));
        when(toolRunRepository.create(eq(task.projectId()), eq(task.id()), eq("rvport-env-collect"), any(), any(), eq(TaskStatus.RUNNING), any()))
                .thenReturn(toolRunId);
        when(environmentRepository.createSnapshot(eq(environment.id()), eq(environment.projectId()), eq(task.id()),
                eq("Debian"), eq("13"), eq("6.12"), eq("x86_64"), eq("apt"), any(), any(), any(),
                eq(TaskStatus.SUCCEEDED), any(), eq(environment.configVersion())))
                .thenReturn(snapshotId);
        when(sshClientAdapter.execute(any())).thenReturn(new SshCommandResult(
                0,
                """
                        RVPORT_COLLECT=ok
                        COLLECT_SCOPES=OS,TOOL_VERSIONS
                        OS_NAME=Debian
                        OS_VERSION=13
                        KERNEL_VERSION=6.12
                        MACHINE_ARCH=x86_64
                        PACKAGE_MANAGER=apt
                        REPO_SOURCE_COUNT=2
                        TOOL_VERSION_git=git version 2.47.0
                        TOOL_PROVIDER=git|/usr/bin/git|git|2.47.0|x86_64|rpm
                        PACKAGE=git|2.47.0|x86_64
                        PACKAGE=pkg01|1.0|x86_64
                        PACKAGE=pkg02|1.0|x86_64
                        PACKAGE=pkg03|1.0|x86_64
                        PACKAGE=pkg04|1.0|x86_64
                        PACKAGE=pkg05|1.0|x86_64
                        PACKAGE=pkg06|1.0|x86_64
                        PACKAGE=pkg07|1.0|x86_64
                        PACKAGE=pkg08|1.0|x86_64
                        PACKAGE=pkg09|1.0|x86_64
                        PACKAGE=pkg10|1.0|x86_64
                        PACKAGE=pkg11|1.0|x86_64
                        PACKAGE=pkg12|1.0|x86_64
                        PACKAGE=pkg13|1.0|x86_64
                        PACKAGE=pkg14|1.0|x86_64
                        PACKAGE=pkg15|1.0|x86_64
                        PACKAGE=pkg16|1.0|x86_64
                        PACKAGE=pkg17|1.0|x86_64
                        PACKAGE=pkg18|1.0|x86_64
                        PACKAGE=pkg19|1.0|x86_64
                        PACKAGE=pkg20|1.0|x86_64
                        PACKAGE=pkg21|1.0|x86_64
                        NATIVE_FILE=libdemo.so|/usr/lib/libdemo.so
                        ELF=/usr/lib/libdemo.so|libdemo.so.1|libc.so.6,ld-linux-x86-64.so.2|Advanced Micro Devices X86-64|ELF64|readelf
                        PROVIDER=/usr/lib/libdemo.so|demo-libs|1.2-1|x86_64|rpm
                        PARSE_WARNING=provider scanner unavailable or no owner for libmissing.so
                        """,
                "",
                Duration.ofMillis(101)
        ));

        service.collectEnvironment(new EnvironmentTaskInput(
                environment.projectId(), environment.id(), null, 20, null,
                null, java.util.List.of("OS", "TOOL_VERSIONS"), null, null, null, null), context);

        verify(environmentRepository).createSnapshot(eq(environment.id()), eq(environment.projectId()), eq(task.id()),
                eq("Debian"), eq("13"), eq("6.12"), eq("x86_64"), eq("apt"), any(), any(), any(),
                eq(TaskStatus.SUCCEEDED), any(), eq(environment.configVersion()));
        ArgumentCaptor<SshCommandRequest> requestCaptor = ArgumentCaptor.forClass(SshCommandRequest.class);
        verify(sshClientAdapter).execute(requestCaptor.capture());
        assertThat(requestCaptor.getValue().command())
                .contains("collect_repo=false")
                .contains("REPO_METADATA_STATUS=SKIPPED|source|repository evidence only collected for target environment");
        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> toolMetadataCaptor = ArgumentCaptor.forClass(Map.class);
        verify(environmentRepository).createComponent(eq(snapshotId), eq(environment.projectId()), eq("git"), eq("git version 2.47.0"),
                eq("TOOL"), eq("x86_64"), eq("/usr/bin/git"), eq("TOOL_VERSION"), toolMetadataCaptor.capture());
        assertThat(toolMetadataCaptor.getValue())
                .containsEntry("ownerPackage", "git")
                .containsEntry("ownerVersion", "2.47.0")
                .containsEntry("ownerArch", "x86_64")
                .containsEntry("providerScanner", "rpm")
                .containsEntry("toolPath", "/usr/bin/git")
                .containsEntry("installOrigin", "package")
                .containsEntry("versionText", "git version 2.47.0")
                .containsEntry("versionMajor", "2")
                .containsEntry("normalizedPackage", "git");
        @SuppressWarnings("unchecked")
        ArgumentCaptor<java.util.List<EnvironmentRepository.ComponentInput>> componentsCaptor = ArgumentCaptor.forClass(java.util.List.class);
        verify(environmentRepository).createComponents(eq(snapshotId), eq(environment.projectId()), componentsCaptor.capture());
        assertThat(componentsCaptor.getValue())
                .anySatisfy(component -> assertThat(component)
                        .extracting("name", "version", "componentType", "arch", "source")
                        .containsExactly("git", "2.47.0", "PACKAGE", "x86_64", "INSTALLED_PACKAGE"))
                .anySatisfy(component -> assertThat(component)
                        .extracting("name", "version", "componentType", "arch", "source")
                        .containsExactly("pkg21", "1.0", "PACKAGE", "x86_64", "INSTALLED_PACKAGE"));
        EnvironmentRepository.ComponentInput nativeComponent = component(componentsCaptor.getValue(), "libdemo.so", "NATIVE_FILE", "NATIVE_FILE");
        assertThat(nativeComponent.path()).isEqualTo("/usr/lib/libdemo.so");
        assertThat(metadata(nativeComponent))
                .containsEntry("ownerPackage", "demo-libs")
                .containsEntry("ownerVersion", "1.2-1")
                .containsEntry("ownerArch", "x86_64")
                .containsEntry("providerScanner", "rpm")
                .containsEntry("normalizedName", "libdemo.so")
                .containsEntry("queryPattern", "*/libdemo.so")
                .containsEntry("normalizedPackage", "demo-libs")
                .containsEntry("elfSoname", "libdemo.so.1")
                .containsEntry("elfNeeded", "libc.so.6,ld-linux-x86-64.so.2")
                .containsEntry("elfMachine", "Advanced Micro Devices X86-64")
                .containsEntry("elfClass", "ELF64")
                .containsEntry("elfScanner", "readelf")
                .containsEntry("providesCapabilities", "libdemo.so.1,libdemo.so,demo-libs")
                .containsEntry("requiredCapabilities", "libc.so.6,ld-linux-x86-64.so.2");
        verify(environmentRepository).updateLastCollectedAt(environment.id(), environment.configVersion());
        verify(toolRunRepository).finish(eq(toolRunId), eq(TaskStatus.SUCCEEDED), eq(0), any());
    }

    @Test
    void collectEnvironmentKeepsUnmanagedToolWhenProviderHasNoOwner() {
        SshRuntimeService service = service();
        EnvironmentView environment = environment(null);
        TaskView task = task(environment.projectId());
        UUID toolRunId = UUID.randomUUID();
        UUID snapshotId = UUID.randomUUID();
        when(context.task()).thenReturn(task);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(credentialService.sshRuntimeCredential(environment.credentialId(), environment.projectId()))
                .thenReturn(passwordCredential(environment));
        when(toolRunRepository.create(eq(task.projectId()), eq(task.id()), eq("rvport-env-collect"), any(), any(), eq(TaskStatus.RUNNING), any()))
                .thenReturn(toolRunId);
        when(environmentRepository.createSnapshot(eq(environment.id()), eq(environment.projectId()), eq(task.id()),
                eq("Debian"), eq("13"), eq("6.12"), eq("riscv64"), eq("apt"), any(), any(), any(),
                eq(TaskStatus.SUCCEEDED), any(), eq(environment.configVersion())))
                .thenReturn(snapshotId);
        when(sshClientAdapter.execute(any())).thenReturn(new SshCommandResult(
                0,
                """
                        RVPORT_COLLECT=ok
                        COLLECT_SCOPES=OS,TOOL_VERSIONS
                        OS_NAME=Debian
                        OS_VERSION=13
                        KERNEL_VERSION=6.12
                        MACHINE_ARCH=riscv64
                        PACKAGE_MANAGER=apt
                        TOOL_VERSION_gcc=gcc (GCC) 14.2.0
                        TOOL_PROVIDER=gcc|/opt/gcc-14/bin/gcc||||none
                        """,
                "",
                Duration.ofMillis(44)
        ));

        service.collectEnvironment(new EnvironmentTaskInput(
                environment.projectId(), environment.id(), null, 20, null,
                null, java.util.List.of("OS", "TOOL_VERSIONS"), null, null, null, null), context);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> toolMetadataCaptor = ArgumentCaptor.forClass(Map.class);
        verify(environmentRepository).createComponent(eq(snapshotId), eq(environment.projectId()), eq("gcc"), eq("gcc (GCC) 14.2.0"),
                eq("TOOL"), eq("riscv64"), eq("/opt/gcc-14/bin/gcc"), eq("TOOL_VERSION"), toolMetadataCaptor.capture());
        assertThat(toolMetadataCaptor.getValue())
                .containsEntry("toolPath", "/opt/gcc-14/bin/gcc")
                .containsEntry("providerScanner", "none")
                .containsEntry("installOrigin", "unmanaged")
                .containsEntry("versionText", "gcc (GCC) 14.2.0")
                .containsEntry("versionMajor", "14");
        assertThat(toolMetadataCaptor.getValue()).doesNotContainKey("ownerPackage");
    }

    @Test
    void collectTargetRiscvEnvironmentStoresRepositoryComponentsAndWarnings() {
        SshRuntimeService service = service();
        EnvironmentView environment = environment(UUID.randomUUID(), null, true, EnvironmentRole.TARGET_RISCV, "riscv64");
        TaskView task = task(environment.projectId());
        UUID toolRunId = UUID.randomUUID();
        UUID snapshotId = UUID.randomUUID();
        when(context.task()).thenReturn(task);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(credentialService.sshRuntimeCredential(environment.credentialId(), environment.projectId()))
                .thenReturn(passwordCredential(environment));
        when(toolRunRepository.create(eq(task.projectId()), eq(task.id()), eq("rvport-env-collect"), any(), any(), eq(TaskStatus.RUNNING), any()))
                .thenReturn(toolRunId);
        when(environmentRepository.createSnapshot(eq(environment.id()), eq(environment.projectId()), eq(task.id()),
                eq("Debian"), eq("13"), eq("6.12"), eq("riscv64"), eq("apt"), any(), any(), any(),
                eq(TaskStatus.SUCCEEDED), any(), eq(environment.configVersion())))
                .thenReturn(snapshotId);
        when(sshClientAdapter.execute(any())).thenReturn(new SshCommandResult(
                0,
                """
                        RVPORT_COLLECT=ok
                        OS_NAME=Debian
                        OS_VERSION=13
                        KERNEL_VERSION=6.12
                        MACHINE_ARCH=riscv64
                        PACKAGE_MANAGER=apt
                        REPO_METADATA_STATUS=FAILED|dnf|Could not resolve host
                        REPO_PACKAGE=openssl|3.0.9|riscv64
                        REPO_PROVIDE=openssl|3.0.9|riscv64|/usr/lib/libssl.so|apt-file|*/libssl.so|PATH|libssl.so
                        PARSE_WARNING=apt-file unavailable
                        """,
                "",
                Duration.ofMillis(101)
        ));

        service.collectEnvironment(new EnvironmentTaskInput(
                environment.projectId(), environment.id(), null, 20, null,
                null, java.util.List.of("OS", "INSTALLED_PACKAGES", "NATIVE_FILES"), null, null, null, null), context);

        ArgumentCaptor<SshCommandRequest> requestCaptor = ArgumentCaptor.forClass(SshCommandRequest.class);
        verify(sshClientAdapter).execute(requestCaptor.capture());
        assertThat(requestCaptor.getValue().command())
                .contains("collect_repo=true")
                .contains("find -L \"$libdir\" -maxdepth 4")
                .contains("find -L \"$ndir\" -maxdepth 3")
                .contains("ry_scan_native_dir")
                .doesNotContain("find /opt /usr/local/bin -maxdepth 3 -type f \\( -name '*.so*' -o -perm -111 \\)")
                .contains("ry_dpkg_bulk=false")
                .contains("ry_dpkg_library_providers")
                .contains("'/usr/lib/*/*/*.so*'")
                .contains("printf 'PROVIDER=%s|%s|||dpkg")
                .contains("[ \"$pkg\" = dnf ]")
                .contains("rpm -qa --qf")
                .contains("REPO_METADATA_STATUS=SUCCESS|dnf|makecache --refresh")
                .contains("ry_owner")
                .contains("ry_repo_provide")
                .contains("readelf -d")
                .contains("objdump -p")
                .contains("elf metadata scanner unavailable")
                .contains("skip_if_unavailable=True")
                .contains("timeout 1800s")
                .contains("PARSE_WARNING=repository package scanner");
        @SuppressWarnings("unchecked")
        ArgumentCaptor<java.util.List<EnvironmentRepository.ComponentInput>> componentsCaptor = ArgumentCaptor.forClass(java.util.List.class);
        verify(environmentRepository).createComponents(eq(snapshotId), eq(environment.projectId()), componentsCaptor.capture());
        assertThat(componentsCaptor.getValue())
                .anySatisfy(component -> assertThat(component)
                        .extracting("name", "version", "componentType", "arch", "source")
                        .containsExactly("openssl", "3.0.9", "PACKAGE", "riscv64", "REPOSITORY_PACKAGE"));
        EnvironmentRepository.ComponentInput repoProvideComponent = component(componentsCaptor.getValue(), "libssl.so", "LIBRARY", "REPOSITORY_PROVIDE");
        assertThat(repoProvideComponent.path()).isEqualTo("/usr/lib/libssl.so");
        assertThat(metadata(repoProvideComponent))
                .containsEntry("packageName", "openssl")
                .containsEntry("packageVersion", "3.0.9")
                .containsEntry("packageArch", "riscv64")
                .containsEntry("scanner", "apt-file")
                .containsEntry("queryPattern", "*/libssl.so")
                .containsEntry("provideKind", "PATH")
                .containsEntry("queryValue", "libssl.so");
        verify(toolRunRepository).finish(eq(toolRunId), eq(TaskStatus.SUCCEEDED), eq(0), any());
    }

    @Test
    void checkEnvironmentRejectsZeroExitWithoutSuccessMarker() {
        SshRuntimeService service = service();
        EnvironmentView environment = environment(null);
        TaskView task = task(environment.projectId());
        when(context.task()).thenReturn(task);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(credentialService.sshRuntimeCredential(environment.credentialId(), environment.projectId()))
                .thenReturn(passwordCredential(environment));
        when(toolRunRepository.create(eq(task.projectId()), eq(task.id()), eq("rvport-env-check"), any(), any(),
                eq(TaskStatus.RUNNING), any())).thenReturn(UUID.randomUUID());
        when(sshClientAdapter.execute(any())).thenReturn(new SshCommandResult(
                0, "RVPORT_CHECK=invalid\n", "", Duration.ZERO));

        assertThatThrownBy(() -> service.checkEnvironment(
                new EnvironmentTaskInput(environment.projectId(), environment.id(), null, 20), context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("环境检查失败");
    }

    @Test
    void collectSourceEnvironmentAttemptsScannerToolInstallAndStoresResults() {
        SshRuntimeService service = service();
        EnvironmentView environment = environment(UUID.randomUUID(), null, true, EnvironmentRole.SOURCE_X86, "x86_64");
        TaskView task = task(environment.projectId());
        UUID toolRunId = UUID.randomUUID();
        UUID snapshotId = UUID.randomUUID();
        when(context.task()).thenReturn(task);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(credentialService.sshRuntimeCredential(environment.credentialId(), environment.projectId()))
                .thenReturn(passwordCredential(environment));
        when(toolRunRepository.create(eq(task.projectId()), eq(task.id()), eq("rvport-env-collect"), any(), any(), eq(TaskStatus.RUNNING), any()))
                .thenReturn(toolRunId);
        when(environmentRepository.createSnapshot(eq(environment.id()), eq(environment.projectId()), eq(task.id()),
                eq("openEuler"), eq("24.03"), eq("6.6"), eq("x86_64"), eq("dnf"), any(), any(), any(),
                eq(TaskStatus.SUCCEEDED), any(), eq(environment.configVersion())))
                .thenReturn(snapshotId);
        when(sshClientAdapter.execute(any())).thenReturn(new SshCommandResult(
                0,
                """
                        RVPORT_COLLECT=ok
                        OS_NAME=openEuler
                        OS_VERSION=24.03
                        KERNEL_VERSION=6.6
                        MACHINE_ARCH=x86_64
                        PACKAGE_MANAGER=dnf
                        SCANNER_TOOL=find|false
                        SCANNER_TOOL=readelf|false
                        SCANNER_TOOL=objdump|true
                        SCANNER_TOOL=strace|false
                        SCANNER_TOOL=bear|false
                        SCANNER_INSTALL_ATTEMPT=environment-collect-SOURCE_X86|dnf|findutils binutils strace bear
                        SCANNER_INSTALL_RESULT=environment-collect-SOURCE_X86|FAILED|dnf|findutils binutils strace bear|repository unavailable
                        PARSE_WARNING=scanner tool missing: find
                        LIBRARY=libc.so.6|/lib64/libc.so.6
                        PROVIDER=/lib64/libc.so.6|glibc|2.38-84|x86_64|rpm
                        """,
                "",
                Duration.ofMillis(101)
        ));

        service.collectEnvironment(new EnvironmentTaskInput(
                environment.projectId(), environment.id(), null, 20, null,
                null, java.util.List.of("OS", "INSTALLED_PACKAGES", "NATIVE_FILES"), null, null, null, null), context);

        ArgumentCaptor<SshCommandRequest> requestCaptor = ArgumentCaptor.forClass(SshCommandRequest.class);
        verify(sshClientAdapter).execute(requestCaptor.capture());
        assertThat(requestCaptor.getValue().command())
                .contains("ry_prepare_scanner_tools")
                .contains("findutils")
                .contains("binutils")
                .contains("strace")
                .contains("bear")
                .contains("ry_scan_library_dir")
                .contains("find -L \"$libdir\" -maxdepth 4")
                .contains("SCANNER_INSTALL_RESULT=%s|FAILED");
        @SuppressWarnings("unchecked")
        ArgumentCaptor<java.util.List<EnvironmentRepository.ComponentInput>> componentsCaptor = ArgumentCaptor.forClass(java.util.List.class);
        verify(environmentRepository).createComponents(eq(snapshotId), eq(environment.projectId()), componentsCaptor.capture());
        EnvironmentRepository.ComponentInput libraryComponent = component(componentsCaptor.getValue(), "libc.so.6", "LIBRARY", "INSTALLED_LIBRARY");
        assertThat(metadata(libraryComponent))
                .containsEntry("ownerPackage", "glibc")
                .containsEntry("ownerVersion", "2.38-84")
                .containsEntry("providerScanner", "rpm");
        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> summaryCaptor = ArgumentCaptor.forClass(Map.class);
        verify(toolRunRepository).finish(eq(toolRunId), eq(TaskStatus.SUCCEEDED), eq(0), summaryCaptor.capture());
        assertThat(summaryCaptor.getValue().toString())
                .contains("scannerTools")
                .contains("scannerInstallResults")
                .contains("findutils binutils strace bear");
    }

    @Test
    void collectEnvironmentStoresMultiarchGconvLibraryOwnerPackage() {
        SshRuntimeService service = service();
        EnvironmentView environment = environment(UUID.randomUUID(), null, true, EnvironmentRole.TARGET_RISCV, "riscv64");
        TaskView task = task(environment.projectId());
        UUID toolRunId = UUID.randomUUID();
        UUID snapshotId = UUID.randomUUID();
        when(context.task()).thenReturn(task);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(credentialService.sshRuntimeCredential(environment.credentialId(), environment.projectId()))
                .thenReturn(passwordCredential(environment));
        when(toolRunRepository.create(eq(task.projectId()), eq(task.id()), eq("rvport-env-collect"), any(), any(), eq(TaskStatus.RUNNING), any()))
                .thenReturn(toolRunId);
        when(environmentRepository.createSnapshot(eq(environment.id()), eq(environment.projectId()), eq(task.id()),
                eq("Bianbu"), eq("2.0"), eq("6.6"), eq("riscv64"), eq("apt"), any(), any(), any(),
                eq(TaskStatus.SUCCEEDED), any(), eq(environment.configVersion())))
                .thenReturn(snapshotId);
        when(sshClientAdapter.execute(any())).thenReturn(new SshCommandResult(
                0,
                """
                        RVPORT_COLLECT=ok
                        OS_NAME=Bianbu
                        OS_VERSION=2.0
                        KERNEL_VERSION=6.6
                        MACHINE_ARCH=riscv64
                        PACKAGE_MANAGER=apt
                        LIBRARY=CP1250.so|/usr/lib/riscv64-linux-gnu/gconv/CP1250.so
                        PROVIDER=/usr/lib/riscv64-linux-gnu/gconv/CP1250.so|libc6|2.38-1|riscv64|dpkg
                        ELF=/usr/lib/riscv64-linux-gnu/gconv/CP1250.so|||||readelf
                        """,
                "",
                Duration.ofMillis(101)
        ));

        service.collectEnvironment(new EnvironmentTaskInput(
                environment.projectId(), environment.id(), null, 20, null,
                null, java.util.List.of("NATIVE_FILES"), null, null, null, null), context);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<java.util.List<EnvironmentRepository.ComponentInput>> componentsCaptor = ArgumentCaptor.forClass(java.util.List.class);
        verify(environmentRepository).createComponents(eq(snapshotId), eq(environment.projectId()), componentsCaptor.capture());
        EnvironmentRepository.ComponentInput libraryComponent = component(componentsCaptor.getValue(), "CP1250.so", "LIBRARY", "INSTALLED_LIBRARY");
        assertThat(libraryComponent.path()).isEqualTo("/usr/lib/riscv64-linux-gnu/gconv/CP1250.so");
        assertThat(metadata(libraryComponent))
                .containsEntry("ownerPackage", "libc6")
                .containsEntry("ownerVersion", "2.38-1")
                .containsEntry("ownerArch", "riscv64")
                .containsEntry("providerScanner", "dpkg")
                .containsEntry("normalizedName", "CP1250.so")
                .containsEntry("queryPattern", "*/CP1250.so")
                .containsEntry("providesCapabilities", "CP1250.so,libc6");
    }

    @Test
    void collectEnvironmentKeepsObjdumpFallbackElfMetadataAndToolMissingWarning() {
        SshRuntimeService service = service();
        EnvironmentView environment = environment(null);
        TaskView task = task(environment.projectId());
        UUID toolRunId = UUID.randomUUID();
        UUID snapshotId = UUID.randomUUID();
        when(context.task()).thenReturn(task);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(credentialService.sshRuntimeCredential(environment.credentialId(), environment.projectId()))
                .thenReturn(passwordCredential(environment));
        when(toolRunRepository.create(eq(task.projectId()), eq(task.id()), eq("rvport-env-collect"), any(), any(), eq(TaskStatus.RUNNING), any()))
                .thenReturn(toolRunId);
        when(environmentRepository.createSnapshot(eq(environment.id()), eq(environment.projectId()), eq(task.id()),
                eq("Debian"), eq("13"), eq("6.12"), eq("x86_64"), eq("apt"), any(), any(), any(),
                eq(TaskStatus.SUCCEEDED), any(), eq(environment.configVersion())))
                .thenReturn(snapshotId);
        when(sshClientAdapter.execute(any())).thenReturn(new SshCommandResult(
                0,
                """
                        RVPORT_COLLECT=ok
                        OS_NAME=Debian
                        OS_VERSION=13
                        KERNEL_VERSION=6.12
                        MACHINE_ARCH=x86_64
                        PACKAGE_MANAGER=apt
                        NATIVE_FILE=libfallback.so|/usr/lib/libfallback.so
                        ELF=/usr/lib/libfallback.so|libfallback.so.2|libc.so.6|ELF 64-bit LSB shared object|x86-64|objdump
                        PARSE_WARNING=elf metadata scanner unavailable
                        """,
                "",
                Duration.ofMillis(22)
        ));

        service.collectEnvironment(new EnvironmentTaskInput(
                environment.projectId(), environment.id(), null, 20, null,
                null, java.util.List.of("NATIVE_FILES"), null, null, null, null), context);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<java.util.List<EnvironmentRepository.ComponentInput>> componentsCaptor = ArgumentCaptor.forClass(java.util.List.class);
        verify(environmentRepository).createComponents(eq(snapshotId), eq(environment.projectId()), componentsCaptor.capture());
        EnvironmentRepository.ComponentInput nativeComponent = component(componentsCaptor.getValue(), "libfallback.so", "NATIVE_FILE", "NATIVE_FILE");
        assertThat(nativeComponent.path()).isEqualTo("/usr/lib/libfallback.so");
        assertThat(metadata(nativeComponent))
                .containsEntry("elfSoname", "libfallback.so.2")
                .containsEntry("elfNeeded", "libc.so.6")
                .containsEntry("elfMachine", "ELF 64-bit LSB shared object")
                .containsEntry("elfClass", "x86-64")
                .containsEntry("elfScanner", "objdump")
                .containsEntry("providesCapabilities", "libfallback.so.2,libfallback.so");
        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> summaryCaptor = ArgumentCaptor.forClass(Map.class);
        verify(toolRunRepository).finish(eq(toolRunId), eq(TaskStatus.SUCCEEDED), eq(0), summaryCaptor.capture());
        assertThat(summaryCaptor.getValue().toString()).contains("parseWarnings=1");
    }

    @Test
    void runtimeRejectsDisabledEnvironmentBeforeSsh() {
        SshRuntimeService service = service();
        EnvironmentView environment = environment(UUID.randomUUID(), null, false);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));

        assertThatThrownBy(() -> service.testConnection(new EnvironmentTaskInput(environment.projectId(), environment.id(), null, 20), context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("环境已禁用");

        verify(sshClientAdapter, never()).execute(any());
    }

    @Test
    void runtimeRejectsTaskCreatedForOlderEnvironmentConfiguration() {
        SshRuntimeService service = service();
        EnvironmentView environment = environment(null);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        EnvironmentTaskInput staleInput = new EnvironmentTaskInput(
                environment.projectId(), environment.id(), environment.jumpHostEnvironmentId(), 20,
                null, null, null, null, null, null, null, null,
                environment.configVersion() - 1, null);

        assertThatThrownBy(() -> service.testConnection(staleInput, context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("环境配置已更新，当前任务不再有效")
                .extracting("errorCode")
                .isEqualTo(TaskErrorCode.RESOURCE_STALE);

        verify(sshClientAdapter, never()).execute(any());
        verify(toolRunRepository, never()).create(any(), any(), any(), any(), any(), any(), any());
        verify(environmentRepository, never()).updateConnectionStatus(any(), anyLong(), any(), anyBoolean());
    }

    @Test
    void runtimeRejectsMultiLevelJumpHostBeforeSsh() {
        SshRuntimeService service = service();
        UUID projectId = UUID.randomUUID();
        EnvironmentView parentJump = environment(projectId, null);
        EnvironmentView jumpHost = environment(projectId, parentJump.id());
        EnvironmentView target = environment(projectId, jumpHost.id());
        when(environmentRepository.findById(target.id())).thenReturn(Optional.of(target));
        when(environmentRepository.findById(jumpHost.id())).thenReturn(Optional.of(jumpHost));

        assertThatThrownBy(() -> service.testConnection(new EnvironmentTaskInput(projectId, target.id(), jumpHost.id(), 20), context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("不支持多级跳板机");

        verify(sshClientAdapter, never()).execute(any());
    }

    @Test
    void runtimeRejectsMissingForeignAndDisabledPersistedJumpHosts() {
        SshRuntimeService service = service();
        UUID projectId = UUID.randomUUID();
        UUID jumpHostId = UUID.randomUUID();
        EnvironmentView target = environment(projectId, jumpHostId);
        when(environmentRepository.findById(target.id())).thenReturn(Optional.of(target));
        when(environmentRepository.findById(jumpHostId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.testConnection(
                new EnvironmentTaskInput(projectId, target.id(), jumpHostId, 20), context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("跳板机环境不存在");

        EnvironmentView foreignJump = environment(UUID.randomUUID(), null);
        when(environmentRepository.findById(jumpHostId)).thenReturn(Optional.of(foreignJump));
        assertThatThrownBy(() -> service.testConnection(
                new EnvironmentTaskInput(projectId, target.id(), jumpHostId, 20), context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("跳板机不属于当前项目");

        EnvironmentView disabledJump = environment(projectId, null, false);
        when(environmentRepository.findById(jumpHostId)).thenReturn(Optional.of(disabledJump));
        assertThatThrownBy(() -> service.testConnection(
                new EnvironmentTaskInput(projectId, target.id(), jumpHostId, 20), context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("跳板机已禁用");

        verify(sshClientAdapter, never()).execute(any());
    }

    @Test
    void runtimeRejectsProjectMismatchAndMissingEnvironmentBeforeSsh() {
        SshRuntimeService service = service();
        UUID requestedProject = UUID.randomUUID();
        UUID environmentId = UUID.randomUUID();
        when(environmentRepository.findById(environmentId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.testConnection(
                new EnvironmentTaskInput(requestedProject, environmentId, null, 20), context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("环境不存在");

        EnvironmentView foreign = environment(UUID.randomUUID(), null);
        when(environmentRepository.findById(environmentId)).thenReturn(Optional.of(foreign));
        assertThatThrownBy(() -> service.testConnection(
                new EnvironmentTaskInput(requestedProject, environmentId, null, 20), context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("环境不属于当前项目");

        verify(sshClientAdapter, never()).execute(any());
    }

    @Test
    void temporaryTargetRejectsInvalidJumpHostConfigurationsBeforeSsh() {
        SshRuntimeService service = service();
        UUID projectId = UUID.randomUUID();
        UUID jumpHostId = UUID.randomUUID();
        EnvironmentTaskInput input = temporaryTargetInput(projectId, jumpHostId);
        when(environmentRepository.findById(jumpHostId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.testConnection(input, context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("跳板机环境不存在");

        EnvironmentView foreignJump = environment(UUID.randomUUID(), null);
        when(environmentRepository.findById(jumpHostId)).thenReturn(Optional.of(foreignJump));
        assertThatThrownBy(() -> service.testConnection(input, context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("跳板机不属于当前项目");

        EnvironmentView disabledJump = environment(projectId, null, false);
        when(environmentRepository.findById(jumpHostId)).thenReturn(Optional.of(disabledJump));
        assertThatThrownBy(() -> service.testConnection(input, context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("跳板机已禁用");

        EnvironmentView parent = environment(projectId, null);
        EnvironmentView nestedJump = environment(projectId, parent.id());
        when(environmentRepository.findById(jumpHostId)).thenReturn(Optional.of(nestedJump));
        assertThatThrownBy(() -> service.testConnection(input, context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("不支持多级跳板机");

        verify(sshClientAdapter, never()).execute(any());
    }

    @Test
    void temporaryTargetRejectsMissingCredentialReferenceBeforeAdapterCall() {
        SshRuntimeService service = service();
        UUID projectId = UUID.randomUUID();
        TaskView task = task(projectId);
        when(context.task()).thenReturn(task);
        when(toolRunRepository.create(eq(projectId), eq(task.id()), any(), any(), any(),
                eq(TaskStatus.RUNNING), any())).thenReturn(UUID.randomUUID());
        EnvironmentTaskInput input = new EnvironmentTaskInput(
                projectId, null, null, 20, null, null, null, null, null, null, null, null,
                new EnvironmentTaskInput.Target(
                        EnvironmentRole.TARGET_RISCV, "riscv64", "192.0.2.50", 22, "root",
                        null, null, null, "/workspace"));

        assertThatThrownBy(() -> service.testConnection(input, context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("SSH 凭据引用不存在");

        verify(sshClientAdapter, never()).execute(any());
    }

    @Test
    void customBashUploadsScriptThroughStdinAndDoesNotExposeBodyInCommand() {
        SshRuntimeService service = service();
        EnvironmentView environment = environment(null);
        TaskView task = task(environment.projectId());
        UUID toolRunId = UUID.randomUUID();
        UUID payloadId = UUID.randomUUID();
        when(context.task()).thenReturn(task);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(credentialService.sshRuntimeCredential(environment.credentialId(), environment.projectId()))
                .thenReturn(passwordCredential(environment));
        when(toolRunRepository.create(eq(task.projectId()), eq(task.id()), eq("rvport-remote-script"), any(), any(), eq(TaskStatus.RUNNING), any()))
                .thenReturn(toolRunId);
        when(taskScriptPayloadService.requireScript(payloadId, environment.projectId(), task.id(), "abc"))
                .thenReturn("echo \"a'b;$PATH\"\nprintf 'done\\n'");
        when(sshClientAdapter.execute(any())).thenReturn(new SshCommandResult(0, "", "", Duration.ofMillis(10)));

        service.runScript(new EnvironmentTaskInput(
                environment.projectId(), environment.id(), null, 20, "CUSTOM_BASH",
                null, null, null, null, payloadId, "abc", 12), context);

        ArgumentCaptor<SshCommandRequest> requestCaptor = ArgumentCaptor.forClass(SshCommandRequest.class);
        verify(sshClientAdapter).execute(requestCaptor.capture());
        SshCommandRequest request = requestCaptor.getValue();
        assertThat(request.command())
                .contains("mktemp")
                .contains("cat > \"$tmp\"")
                .contains("trap cleanup EXIT INT TERM")
                .contains("rm -f \"$tmp\"")
                .doesNotContain("a'b;$PATH");
        assertThat(request.stdin()).isEqualTo("echo \"a'b;$PATH\"\nprintf 'done\\n'");
        assertThat(request.streamOutput()).isTrue();
    }

    @Test
    void builtInScriptWritesBufferedLogsAndPropagatesNonZeroExit() {
        SshRuntimeService service = service();
        EnvironmentView environment = environment(null);
        TaskView task = task(environment.projectId());
        UUID toolRunId = UUID.randomUUID();
        when(context.task()).thenReturn(task);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(credentialService.sshRuntimeCredential(environment.credentialId(), environment.projectId()))
                .thenReturn(passwordCredential(environment));
        when(toolRunRepository.create(eq(task.projectId()), eq(task.id()), eq("rvport-remote-script"), any(), any(),
                eq(TaskStatus.RUNNING), any())).thenReturn(toolRunId);
        when(taskLogEventService.count(task.id())).thenReturn(2L);
        when(sshClientAdapter.execute(any())).thenReturn(new SshCommandResult(
                3, "partial output", "failure", Duration.ofMillis(9)));

        EnvironmentTaskInput input = new EnvironmentTaskInput(
                environment.projectId(), environment.id(), null, 20, "BUILTIN_SCRIPT", null, null,
                "/explicit", Map.of("name", "PRINT_WORKDIR"), null, null);
        assertThatThrownBy(() -> service.runScript(input, context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("远程脚本执行失败");

        verify(context).log(TaskLogType.STDOUT, "partial output");
        verify(context).log(TaskLogType.STDERR, "failure");
        verify(toolRunRepository).finish(eq(toolRunId), eq(TaskStatus.FAILED), eq(3), any());
    }

    private SshRuntimeService service() {
        return new SshRuntimeService(environmentRepository, credentialService, sshClientAdapter, toolRunRepository,
                taskScriptPayloadService, taskLogEventService, taskSecretPayloadService);
    }

    private EnvironmentTaskInput temporaryTargetInput(UUID projectId, UUID jumpHostId) {
        return new EnvironmentTaskInput(
                projectId, null, jumpHostId, 20, null, null, null, null, null, null, null, null,
                new EnvironmentTaskInput.Target(
                        EnvironmentRole.TARGET_RISCV, "riscv64", "192.0.2.50", 22, "root",
                        UUID.randomUUID(), null, null, "/workspace"));
    }

    private EnvironmentRepository.ComponentInput component(
            java.util.List<EnvironmentRepository.ComponentInput> components,
            String name,
            String componentType,
            String source
    ) {
        return components.stream()
                .filter(component -> name.equals(component.name())
                        && componentType.equals(component.componentType())
                        && source.equals(component.source()))
                .findFirst()
                .orElseThrow();
    }

    private Map<String, Object> metadata(EnvironmentRepository.ComponentInput component) {
        return new java.util.LinkedHashMap<>(component.metadata());
    }

    private TaskView task(UUID projectId) {
        return new TaskView(
                UUID.randomUUID(),
                projectId,
                "ENV_TEST_CONNECTION",
                TaskStatus.RUNNING,
                0,
                "开始",
                UUID.randomUUID(),
                OffsetDateTime.now(),
                OffsetDateTime.now(),
                OffsetDateTime.now(),
                null,
                300,
                null,
                null,
                0
        );
    }

    private EnvironmentView environment(UUID jumpHostEnvironmentId) {
        return environment(UUID.randomUUID(), jumpHostEnvironmentId);
    }

    private EnvironmentView environment(UUID projectId, UUID jumpHostEnvironmentId) {
        return environment(projectId, jumpHostEnvironmentId, true);
    }

    private EnvironmentView environment(UUID projectId, UUID jumpHostEnvironmentId, boolean enabled) {
        return environment(projectId, jumpHostEnvironmentId, enabled, EnvironmentRole.GENERAL_EXECUTION, "x86_64");
    }

    private EnvironmentView environment(UUID projectId, UUID jumpHostEnvironmentId, boolean enabled, EnvironmentRole role, String arch) {
        return new EnvironmentView(
                UUID.randomUUID(),
                projectId,
                "env",
                role,
                arch,
                "192.0.2.10",
                22,
                "deploy",
                UUID.randomUUID(),
                jumpHostEnvironmentId,
                "/opt/app's data",
                enabled ? EnvironmentStatus.UNKNOWN : EnvironmentStatus.DISABLED,
                enabled,
                null,
                null,
                UUID.randomUUID(),
                OffsetDateTime.now(),
                OffsetDateTime.now()
        );
    }

    private CredentialService.SshRuntimeCredential passwordCredential(EnvironmentView environment) {
        return new CredentialService.SshRuntimeCredential(
                environment.credentialId(),
                CredentialKind.SSH_PASSWORD,
                environment.username(),
                "SecretPassword",
                null,
                null
        );
    }
}
