package cn.rvport.backend.environment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.nullable;
import static org.mockito.Mockito.argThat;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.credential.CredentialKind;
import cn.rvport.backend.credential.CredentialService;
import cn.rvport.backend.credential.CredentialStatus;
import cn.rvport.backend.credential.CredentialView;
import cn.rvport.backend.credential.CreateCredentialCommand;
import cn.rvport.backend.project.ProjectRepository;
import cn.rvport.backend.project.ProjectStage;
import cn.rvport.backend.project.ProjectStatus;
import cn.rvport.backend.project.ProjectView;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.project.runtime.ProjectRuntimeEnvironmentService;
import cn.rvport.backend.task.TaskService;
import cn.rvport.backend.task.TaskCreateCommand;
import cn.rvport.backend.task.TaskResponse;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.task.TaskSecretPayloadService;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskScriptPayloadService;
import cn.rvport.backend.common.web.PageResponse;
import java.util.List;
import java.util.Map;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.jooq.JSONB;
import org.springframework.mock.web.MockHttpServletRequest;

@ExtendWith(MockitoExtension.class)
class EnvironmentServiceTests {

    @Mock
    private EnvironmentRepository environmentRepository;

    @Mock
    private CredentialService credentialService;

    @Mock
    private ProjectRepository projectRepository;

    @Mock
    private TaskService taskService;

    @Mock
    private AuditLogService auditLogService;

    @Mock
    private ProjectAccessService projectAccessService;

    @Mock
    private ProjectRuntimeEnvironmentService projectRuntimeEnvironmentService;

    @Mock
    private TaskScriptPayloadService taskScriptPayloadService;

    @Mock
    private TaskSecretPayloadService taskSecretPayloadService;

    @Test
    void createsEnvironmentWithJumpHost() {
        EnvironmentService service = service();
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID credentialId = UUID.randomUUID();
        EnvironmentView jumpHost = environment(projectId, UUID.randomUUID(), null, true);
        EnvironmentView created = environment(projectId, UUID.randomUUID(), jumpHost.id(), true);
        when(credentialService.requireActive(any(), eq(projectId))).thenReturn(credential(projectId, credentialId, actorId));
        when(environmentRepository.findById(jumpHost.id())).thenReturn(Optional.of(jumpHost));
        when(environmentRepository.create(
                eq(projectId), eq("rv-dev"), eq(EnvironmentRole.TARGET_RISCV), eq("riscv64"), eq("192.0.2.11"),
                eq(22), eq("root"), eq(credentialId), eq(jumpHost.id()), eq("/workspace"), eq(actorId)))
                .thenReturn(created);

        EnvironmentResponse response = service.create(
                projectId,
                new CreateEnvironmentRequest(
                        "rv-dev",
                        EnvironmentRole.TARGET_RISCV,
                        "riscv64",
                        "192.0.2.11",
                        22,
                        "root",
                        credentialId,
                        null,
                        null,
                        null,
                        null,
                        null,
                        jumpHost.id(),
                        "/workspace"
                ),
                actorId,
                false,
                new MockHttpServletRequest()
        );

        assertThat(response.jumpHost().id()).isEqualTo(jumpHost.id());
        assertThat(response.credential().configured()).isTrue();
    }

    @Test
    void rejectsTaskCreationForDisabledEnvironment() {
        EnvironmentService service = service();
        EnvironmentView disabled = environment(UUID.randomUUID(), UUID.randomUUID(), null, false);
        UUID actorId = disabled.createdBy();
        when(environmentRepository.findById(disabled.id())).thenReturn(Optional.of(disabled));

        assertThatThrownBy(() -> service.testConnection(
                disabled.projectId(),
                disabled.id(),
                new EnvironmentRunRequest(null),
                actorId,
                false,
                new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessage("环境已禁用，不能创建新任务");
    }

    @Test
    void rejectsSelfJumpHostOnUpdateAsEdgeCase() {
        EnvironmentService service = service();
        EnvironmentView current = environment(UUID.randomUUID(), UUID.randomUUID(), null, true);
        when(environmentRepository.findById(current.id())).thenReturn(Optional.of(current));

        assertThatThrownBy(() -> service.update(
                current.id(),
                new UpdateEnvironmentRequest(null, null, null, null, null, null, null, null, null, null, null, null,
                        current.id(), null, null, null),
                UUID.randomUUID(),
                false,
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("环境不能引用自己作为跳板机");
    }

    @Test
    void rejectsMultiLevelJumpHostAsEdgeCase() {
        EnvironmentService service = service();
        UUID projectId = UUID.randomUUID();
        EnvironmentView jumpHost = environment(projectId, UUID.randomUUID(), UUID.randomUUID(), true);
        when(credentialService.requireActive(any(), eq(projectId))).thenReturn(credential(projectId, UUID.randomUUID(), UUID.randomUUID()));
        when(environmentRepository.findById(jumpHost.id())).thenReturn(Optional.of(jumpHost));

        assertThatThrownBy(() -> service.create(
                projectId,
                new CreateEnvironmentRequest("rv", EnvironmentRole.TARGET_RISCV, "riscv64", "192.0.2.12", 22, "root",
                        UUID.randomUUID(), null, null, null, null, null, jumpHost.id(), null),
                UUID.randomUUID(),
                false,
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("MVP 暂不支持多级跳板机");
    }

    @Test
    void rejectsMissingProjectAndMissingCredentialInput() {
        EnvironmentService service = service();
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        when(projectAccessService.requireProjectAccess(projectId, actorId, false))
                .thenThrow(new ApiException(org.springframework.http.HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在"));

        assertThatThrownBy(() -> service.create(
                projectId,
                new CreateEnvironmentRequest("rv", EnvironmentRole.TARGET_RISCV, "riscv64", "192.0.2.12", 22, "root",
                        null, null, null, null, null, null, null, null),
                actorId,
                false,
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("项目不存在");

        UUID missingCredentialActor = UUID.randomUUID();
        assertThatThrownBy(() -> service.create(
                projectId,
                new CreateEnvironmentRequest("rv", EnvironmentRole.TARGET_RISCV, "riscv64", "192.0.2.12", 22, "root",
                        null, null, null, null, null, null, null, null),
                missingCredentialActor,
                false,
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("必须提供 SSH 凭据");
    }

    @Test
    void rejectsCrossProjectDisabledAndInUseJumpHosts() {
        EnvironmentService service = service();
        UUID projectId = UUID.randomUUID();
        EnvironmentView crossProjectJump = environment(UUID.randomUUID(), UUID.randomUUID(), null, true);
        EnvironmentView disabledJump = environment(projectId, UUID.randomUUID(), null, false);
        EnvironmentView current = environment(projectId, UUID.randomUUID(), null, true);

        when(environmentRepository.findById(current.id())).thenReturn(Optional.of(current));
        when(environmentRepository.findById(crossProjectJump.id())).thenReturn(Optional.of(crossProjectJump));
        assertThatThrownBy(() -> service.update(
                current.id(),
                new UpdateEnvironmentRequest(null, null, null, null, null, null, null, null, null, null, null, null, crossProjectJump.id(), null, null, null),
                UUID.randomUUID(),
                false,
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("跳板机必须属于同一项目");

        when(environmentRepository.findById(disabledJump.id())).thenReturn(Optional.of(disabledJump));
        assertThatThrownBy(() -> service.update(
                current.id(),
                new UpdateEnvironmentRequest(null, null, null, null, null, null, null, null, null, null, null, null, disabledJump.id(), null, null, null),
                UUID.randomUUID(),
                false,
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("跳板机已禁用");

        when(environmentRepository.isReferencedAsJumpHost(current.id())).thenReturn(true);
        assertThatThrownBy(() -> service.update(
                current.id(),
                new UpdateEnvironmentRequest(null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, false),
                UUID.randomUUID(),
                false,
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("跳板机仍被其他环境引用，不能禁用");
    }

    @Test
    void updateCanClearJumpHostAndPreserveUnspecifiedFields() {
        EnvironmentService service = service();
        UUID projectId = UUID.randomUUID();
        UUID jumpId = UUID.randomUUID();
        UUID credentialId = UUID.randomUUID();
        EnvironmentView current = environment(projectId, UUID.randomUUID(), jumpId, true);
        EnvironmentView updated = new EnvironmentView(
                current.id(), projectId, current.name(), current.role(), current.arch(), "192.0.2.99", current.sshPort(),
                current.username(), current.credentialId(), null, current.workingDirectory(), EnvironmentStatus.UNKNOWN, true,
                null, null, current.createdBy(), current.createdAt(), OffsetDateTime.now());
        when(environmentRepository.findById(current.id())).thenReturn(Optional.of(current));
        when(environmentRepository.update(current.id(), current.name(), current.role(), current.arch(), "192.0.2.99",
                current.sshPort(), current.username(), current.credentialId(), null, current.workingDirectory(), true, true))
                .thenReturn(updated);
        when(credentialService.requireActive(current.credentialId(), projectId)).thenReturn(credential(projectId, credentialId, current.createdBy()));

        EnvironmentResponse response = service.update(
                current.id(),
                new UpdateEnvironmentRequest(null, null, null, "192.0.2.99", null, null, null, null, null, null, null, null, null, true, null, null),
                UUID.randomUUID(),
                false,
                new MockHttpServletRequest()
        );

        assertThat(response.host()).isEqualTo("192.0.2.99");
        assertThat(response.jumpHost()).isNull();
    }

    @Test
    void displayNameUpdatePreservesEnvironmentConfigurationVersionAndFacts() {
        EnvironmentService service = service();
        UUID actorId = UUID.randomUUID();
        EnvironmentView current = environment(UUID.randomUUID(), UUID.randomUUID(), null, true, actorId);
        EnvironmentView updated = new EnvironmentView(
                current.id(), current.projectId(), "renamed", current.role(), current.arch(), current.host(),
                current.sshPort(), current.username(), current.credentialId(), current.jumpHostEnvironmentId(),
                current.workingDirectory(), current.status(), current.enabled(), current.configVersion(),
                current.lastConnectedAt(), current.lastCollectedAt(), current.createdBy(), current.createdAt(), OffsetDateTime.now());
        when(environmentRepository.findById(current.id())).thenReturn(Optional.of(current));
        when(credentialService.requireActive(current.credentialId(), current.projectId()))
                .thenReturn(credential(current.projectId(), current.credentialId(), actorId));
        when(environmentRepository.update(
                current.id(), "renamed", current.role(), current.arch(), current.host(), current.sshPort(),
                current.username(), current.credentialId(), null, current.workingDirectory(), true, false))
                .thenReturn(updated);

        EnvironmentResponse response = service.update(
                current.id(),
                new UpdateEnvironmentRequest("renamed", null, null, null, null, null, null, null,
                        null, null, null, null, null, null, null, null),
                actorId,
                false,
                new MockHttpServletRequest());

        assertThat(response.configVersion()).isEqualTo(current.configVersion());
        verify(environmentRepository, never()).findDirectDependents(any());
        verify(projectRuntimeEnvironmentService, never()).bumpVersionIfAnySelected(any(), any(), any());
    }

    @Test
    void effectiveJumpHostConfigurationUpdateInvalidatesDependentsAndBumpsRuntimeVersionOnce() {
        EnvironmentService service = service();
        UUID actorId = UUID.randomUUID();
        EnvironmentView current = environment(UUID.randomUUID(), UUID.randomUUID(), null, true, actorId);
        EnvironmentView dependent = environment(current.projectId(), UUID.randomUUID(), current.id(), true, actorId);
        EnvironmentView updated = new EnvironmentView(
                current.id(), current.projectId(), current.name(), current.role(), current.arch(), "192.0.2.99",
                current.sshPort(), current.username(), current.credentialId(), null, current.workingDirectory(),
                EnvironmentStatus.UNKNOWN, true, current.configVersion() + 1,
                null, null, current.createdBy(), current.createdAt(), OffsetDateTime.now());
        when(environmentRepository.findById(current.id())).thenReturn(Optional.of(current));
        when(credentialService.requireActive(current.credentialId(), current.projectId()))
                .thenReturn(credential(current.projectId(), current.credentialId(), actorId));
        when(environmentRepository.update(
                current.id(), current.name(), current.role(), current.arch(), "192.0.2.99", current.sshPort(),
                current.username(), current.credentialId(), null, current.workingDirectory(), true, true))
                .thenReturn(updated);
        when(environmentRepository.findDirectDependents(current.id())).thenReturn(List.of(dependent));

        EnvironmentResponse response = service.update(
                current.id(),
                new UpdateEnvironmentRequest(null, null, null, "192.0.2.99", null, null, null, null,
                        null, null, null, null, null, null, null, null),
                actorId,
                false,
                new MockHttpServletRequest());

        assertThat(response.configVersion()).isEqualTo(current.configVersion() + 1);
        verify(environmentRepository).invalidateConfigurations(List.of(dependent.id()));
        verify(projectRuntimeEnvironmentService).bumpVersionIfAnySelected(
                current.projectId(), List.of(current.id(), dependent.id()), actorId);
    }

    @Test
    void environmentTasksUseSafeInputSnapshots() {
        EnvironmentService service = service();
        UUID actorId = UUID.randomUUID();
        EnvironmentView environment = environment(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), true, actorId);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(taskService.create(any())).thenAnswer(invocation -> task(environment.projectId(), invocation.getArgument(0)));

        service.testConnection(environment.projectId(), environment.id(), new EnvironmentRunRequest(30), actorId, false, new MockHttpServletRequest());
        service.check(environment.projectId(), environment.id(), new EnvironmentCheckRequest(null, null, 30), actorId, false, new MockHttpServletRequest());
        service.collect(environment.projectId(), environment.id(), new EnvironmentCollectRequest(null, 30), actorId, false, new MockHttpServletRequest());
        TaskResponse script = service.runScript(
                environment.projectId(),
                environment.id(),
                new RunScriptRequest(EnvironmentScriptType.CUSTOM_BASH, "echo SecretScript", 30, "/tmp", null),
                actorId,
                false,
                new MockHttpServletRequest()
        );

        assertThat(script.type()).isEqualTo(RvPortTaskTypes.ENV_RUN_SCRIPT);
        verify(taskService).create(argThat(command ->
                command.type().equals(RvPortTaskTypes.ENV_RUN_SCRIPT)
                        && command.inputSnapshot().containsKey("scriptSha256")
                        && command.inputSnapshot().containsKey("scriptLength")
                        && !command.inputSnapshot().toString().contains("SecretScript")
        ));
    }

    @Test
    void precheckConnectionCreatesTargetModeTaskWithoutPlaintextSecrets() {
        EnvironmentService service = service();
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID payloadId = UUID.randomUUID();
        String password = "PrecheckSecret123";
        TaskSecretPayloadService.PreparedSecret preparedSecret = new TaskSecretPayloadService.PreparedSecret(
                payloadId,
                TaskSecretPayloadService.SSH_PRECHECK_CREDENTIAL,
                "0".repeat(64),
                JSONB.valueOf("{}"),
                "local-v1"
        );
        when(taskSecretPayloadService.prepareSshPrecheckCredential(CredentialKind.SSH_PASSWORD, "root", password, null, null))
                .thenReturn(preparedSecret);
        when(taskService.create(any())).thenAnswer(invocation -> task(projectId, invocation.getArgument(0)));

        TaskResponse response = service.precheckConnection(
                projectId,
                new EnvironmentPrecheckRequest(
                        EnvironmentRole.TARGET_RISCV,
                        "riscv64",
                        "192.0.2.20",
                        null,
                        "root",
                        null,
                        EnvironmentLoginType.PASSWORD,
                        password,
                        null,
                        null,
                        "precheck-credential",
                        null,
                        "/workspace",
                        null
                ),
                actorId,
                false,
                new MockHttpServletRequest()
        );

        assertThat(response.type()).isEqualTo(RvPortTaskTypes.ENV_TEST_CONNECTION);
        verify(taskService).create(argThat(command -> {
            Map<String, ?> input = command.inputSnapshot();
            Object targetValue = input.get("target");
            if (!(targetValue instanceof Map<?, ?> target)) {
                return false;
            }
            return command.type().equals(RvPortTaskTypes.ENV_TEST_CONNECTION)
                    && input.get("environmentId") == null
                    && input.get("jumpHostEnvironmentId") == null
                    && target.get("role").equals("TARGET_RISCV")
                    && target.get("sshPort").equals(22)
                    && target.get("temporaryCredentialPayloadId").equals(payloadId)
                    && target.get("temporaryCredentialSha256").equals("0".repeat(64))
                    && !target.containsKey("credentialId")
                    && !input.toString().contains(password);
        }));
        verify(taskSecretPayloadService).save(preparedSecret, projectId, response.id(), actorId);
        verify(credentialService, never()).create(any());
    }

    @Test
    void precheckConnectionValidatesCredentialAndJumpHostAsExceptions() {
        EnvironmentService service = service();
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID jumpHostId = UUID.randomUUID();
        EnvironmentView disabledJump = environment(projectId, jumpHostId, null, false);

        assertThatThrownBy(() -> service.precheckConnection(
                projectId,
                new EnvironmentPrecheckRequest(EnvironmentRole.SOURCE_X86, "x86_64", "192.0.2.10", 22, "root",
                        null, null, null, null, null, null, null, null, 30),
                actorId,
                false,
                new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessage("必须提供 SSH 凭据");

        when(credentialService.requireActive(any(), eq(projectId))).thenReturn(credential(projectId, UUID.randomUUID(), actorId));
        when(environmentRepository.findById(jumpHostId)).thenReturn(Optional.of(disabledJump));
        assertThatThrownBy(() -> service.precheckConnection(
                projectId,
                new EnvironmentPrecheckRequest(EnvironmentRole.SOURCE_X86, "x86_64", "192.0.2.10", 22, "root",
                        UUID.randomUUID(), null, null, null, null, null, jumpHostId, null, 30),
                actorId,
                false,
                new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessage("跳板机已禁用");
    }

    @Test
    void precheckConnectionRejectsUnauthorizedProjectAndCredentialCreateFailure() {
        EnvironmentService service = service();
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        String password = "PrecheckSecret123";
        when(projectAccessService.requireProjectAccess(projectId, actorId, false))
                .thenThrow(new ApiException(org.springframework.http.HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在"));

        assertThatThrownBy(() -> service.precheckConnection(
                projectId,
                new EnvironmentPrecheckRequest(EnvironmentRole.SOURCE_X86, "x86_64", "192.0.2.10", 22, "root",
                        UUID.randomUUID(), null, null, null, null, null, null, null, 30),
                actorId,
                false,
                new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessage("项目不存在");

        UUID allowedProjectId = UUID.randomUUID();
        UUID allowedActorId = UUID.randomUUID();
        when(taskSecretPayloadService.prepareSshPrecheckCredential(CredentialKind.SSH_PASSWORD, "root", password, null, null))
                .thenThrow(new ApiException(org.springframework.http.HttpStatus.INTERNAL_SERVER_ERROR, "TASK_SECRET_PAYLOAD_ENCRYPT_FAILED", "临时凭据加密失败"));

        assertThatThrownBy(() -> service.precheckConnection(
                allowedProjectId,
                new EnvironmentPrecheckRequest(EnvironmentRole.SOURCE_X86, "x86_64", "192.0.2.10", 22, "root",
                        null, EnvironmentLoginType.PASSWORD, password, null, null, null, null, null, 30),
                allowedActorId,
                false,
                new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessage("临时凭据加密失败");
    }

    @Test
    void environmentListCombinesStatusRoleAndEnabledFilters() {
        EnvironmentService service = service();
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        when(environmentRepository.count(projectId, EnvironmentRole.TARGET_RISCV, EnvironmentStatus.AVAILABLE, true)).thenReturn(0L);
        when(environmentRepository.list(projectId, EnvironmentRole.TARGET_RISCV, EnvironmentStatus.AVAILABLE, true, 1, 20)).thenReturn(List.of());

        PageResponse<EnvironmentResponse> page = service.list(
                projectId,
                new EnvironmentListRequest(EnvironmentRole.TARGET_RISCV, EnvironmentStatus.AVAILABLE, true, null, null),
                actorId,
                false
        );

        assertThat(page.items()).isEmpty();
        verify(environmentRepository).count(projectId, EnvironmentRole.TARGET_RISCV, EnvironmentStatus.AVAILABLE, true);
        verify(environmentRepository).list(projectId, EnvironmentRole.TARGET_RISCV, EnvironmentStatus.AVAILABLE, true, 1, 20);
    }

    @Test
    void environmentRunApisRejectCrossProjectAndUnauthorizedUsers() {
        EnvironmentService service = service();
        UUID ownerId = UUID.randomUUID();
        UUID otherUserId = UUID.randomUUID();
        UUID projectId = UUID.randomUUID();
        EnvironmentView environment = environment(projectId, UUID.randomUUID(), null, true, ownerId);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));

        UUID missingProjectId = UUID.randomUUID();
        when(projectAccessService.requireProjectAccess(missingProjectId, ownerId, false))
                .thenThrow(new ApiException(org.springframework.http.HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在"));
        assertThatThrownBy(() -> service.testConnection(
                missingProjectId,
                environment.id(),
                new EnvironmentRunRequest(null),
                ownerId,
                false,
                new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessage("项目不存在");

        when(projectAccessService.requireProjectAccess(projectId, otherUserId, false))
                .thenThrow(new ApiException(org.springframework.http.HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在"));
        assertThatThrownBy(() -> service.testConnection(
                projectId,
                environment.id(),
                new EnvironmentRunRequest(null),
                otherUserId,
                false,
                new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessage("项目不存在");

        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        UUID anotherProjectId = UUID.randomUUID();

        assertThatThrownBy(() -> service.testConnection(
                anotherProjectId,
                environment.id(),
                new EnvironmentRunRequest(null),
                ownerId,
                false,
                new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessage("环境不存在");
    }

    @Test
    void snapshotsReturnEmptyPageAndRejectMissingEnvironment() {
        EnvironmentService service = service();
        EnvironmentView environment = environment(UUID.randomUUID(), UUID.randomUUID(), null, true);
        doReturn(environment).when(projectAccessService).requireEnvironmentAccess(environment.id(), environment.createdBy(), false);
        when(environmentRepository.countSnapshots(environment.id())).thenReturn(0L);
        when(environmentRepository.listSnapshots(environment.id(), 1, 20)).thenReturn(List.of());

        PageResponse<EnvironmentSnapshotResponse> page = service.snapshots(environment.id(), new SnapshotListRequest(1, 20), environment.createdBy(), false);

        assertThat(page.items()).isEmpty();
        assertThat(page.total()).isZero();

        UUID missingId = UUID.randomUUID();
        doThrow(new ApiException(org.springframework.http.HttpStatus.NOT_FOUND, "ENVIRONMENT_NOT_FOUND", "环境不存在"))
                .when(projectAccessService).requireEnvironmentAccess(missingId, environment.createdBy(), false);
        assertThatThrownBy(() -> service.snapshots(missingId, new SnapshotListRequest(1, 20), environment.createdBy(), false))
                .isInstanceOf(ApiException.class)
                .hasMessage("环境不存在");
    }

    @Test
    void environmentResponsesIncludeLatestBasicInfoAndSnapshotKind() {
        EnvironmentService service = service();
        UUID actorId = UUID.randomUUID();
        EnvironmentView environment = environment(UUID.randomUUID(), UUID.randomUUID(), null, true, actorId);
        UUID snapshotId = UUID.randomUUID();
        OffsetDateTime checkedAt = OffsetDateTime.now();
        EnvironmentBasicInfoView basicInfo = new EnvironmentBasicInfoView(
                snapshotId,
                "BASIC_CHECK",
                "Debian",
                "13",
                "6.12",
                "riscv64",
                "apt",
                Map.of("git", true),
                Map.of("git", "git version 2.47.0"),
                Map.of("configured", true, "exists", true),
                Map.of("temporaryWritable", true),
                "root",
                checkedAt
        );
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(credentialService.requireActive(environment.credentialId(), environment.projectId()))
                .thenReturn(credential(environment.projectId(), environment.credentialId(), actorId));
        when(environmentRepository.findLatestBasicInfo(environment.id(), environment.configVersion())).thenReturn(Optional.of(basicInfo));

        EnvironmentResponse response = service.get(environment.id(), actorId, false);

        assertThat(response.basicInfo()).isNotNull();
        assertThat(response.basicInfo().snapshotId()).isEqualTo(snapshotId);
        assertThat(response.basicInfo().snapshotKind()).isEqualTo("BASIC_CHECK");
        assertThat(response.basicInfo().osName()).isEqualTo("Debian");
        assertThat(response.basicInfo().packageManager()).isEqualTo("apt");

        doReturn(environment).when(projectAccessService).requireEnvironmentAccess(environment.id(), actorId, false);
        EnvironmentSnapshotView snapshot = new EnvironmentSnapshotView(
                snapshotId,
                environment.id(),
                environment.projectId(),
                UUID.randomUUID(),
                "Debian",
                "13",
                "6.12",
                "riscv64",
                "apt",
                "BASIC_CHECK",
                TaskStatus.SUCCEEDED,
                checkedAt
        );
        when(environmentRepository.countSnapshots(environment.id())).thenReturn(1L);
        when(environmentRepository.listSnapshots(environment.id(), 1, 20)).thenReturn(List.of(snapshot));

        PageResponse<EnvironmentSnapshotResponse> snapshots = service.snapshots(environment.id(), new SnapshotListRequest(1, 20), actorId, false);

        assertThat(snapshots.items()).singleElement()
                .extracting(EnvironmentSnapshotResponse::snapshotKind)
                .isEqualTo("BASIC_CHECK");
    }

    @Test
    void createsPasswordAndKeyCredentialsWithDefaultPortAndTrimmedValues() {
        EnvironmentService service = service();
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        CredentialView passwordCredential = credential(projectId, UUID.randomUUID(), actorId);
        CredentialView keyCredential = credential(projectId, UUID.randomUUID(), actorId);
        when(credentialService.create(nullable(CreateCredentialCommand.class)))
                .thenReturn(passwordCredential, keyCredential);
        when(credentialService.requireActive(any(), eq(projectId)))
                .thenAnswer(invocation -> credential(projectId, invocation.getArgument(0), actorId));
        when(environmentRepository.create(eq(projectId), any(), any(), any(), any(), anyInt(), any(), any(), any(), any(), eq(actorId)))
                .thenAnswer(invocation -> environment(projectId, UUID.randomUUID(), null, true, actorId));

        service.create(projectId, new CreateEnvironmentRequest(" env ", EnvironmentRole.SOURCE_X86, " x86_64 ",
                " host ", null, " root ", null, EnvironmentLoginType.PASSWORD, "secret", null, null,
                "password", null, " "), actorId, false, new MockHttpServletRequest());
        service.create(projectId, new CreateEnvironmentRequest("env", EnvironmentRole.TARGET_RISCV, "riscv64",
                "host", 2222, "root", null, EnvironmentLoginType.KEY, null, "private", "pass",
                "key", null, null), actorId, false, new MockHttpServletRequest());

        verify(credentialService).sshPassword(projectId, actorId, "password", "host", "root", "secret");
        verify(credentialService).sshKey(projectId, actorId, "key", "host", "root", "private", "pass");
        verify(environmentRepository).create(eq(projectId), eq("env"), eq(EnvironmentRole.SOURCE_X86),
                eq("x86_64"), eq("host"), eq(22), eq("root"), eq(passwordCredential.id()),
                eq(null), eq(null), eq(actorId));
    }

    @Test
    void everyEffectiveConfigurationFieldTriggersVersionRefresh() {
        EnvironmentService service = service();
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        EnvironmentView current = environment(projectId, UUID.randomUUID(), null, true, actorId);
        UUID replacementCredential = UUID.randomUUID();
        EnvironmentView jump = environment(projectId, UUID.randomUUID(), null, true, actorId);
        when(environmentRepository.findById(current.id())).thenReturn(Optional.of(current));
        when(environmentRepository.findById(jump.id())).thenReturn(Optional.of(jump));
        when(credentialService.requireActive(any(), eq(projectId)))
                .thenAnswer(invocation -> credential(projectId, invocation.getArgument(0), actorId));
        when(environmentRepository.update(eq(current.id()), any(), any(), any(), any(), anyInt(), any(), any(),
                nullable(UUID.class), nullable(String.class), anyBoolean(), anyBoolean())).thenReturn(current);
        when(environmentRepository.findDirectDependents(current.id())).thenReturn(List.of());

        List<UpdateEnvironmentRequest> changes = List.of(
                update(null, EnvironmentRole.SOURCE_X86, null, null, null, null, null, null, null, null),
                update(null, null, "new-arch", null, null, null, null, null, null, null),
                update(null, null, null, "new-host", null, null, null, null, null, null),
                update(null, null, null, null, 2222, null, null, null, null, null),
                update(null, null, null, null, null, "new-user", null, null, null, null),
                update(null, null, null, null, null, null, replacementCredential, null, null, null),
                update(null, null, null, null, null, null, null, jump.id(), null, null),
                update(null, null, null, null, null, null, null, null, "/new-work", null),
                update(null, null, null, null, null, null, null, null, null, false));

        for (UpdateEnvironmentRequest change : changes) {
            service.update(current.id(), change, actorId, false, new MockHttpServletRequest());
        }

        verify(projectRuntimeEnvironmentService, org.mockito.Mockito.times(changes.size()))
                .bumpVersionIfAnySelected(eq(projectId), eq(List.of(current.id())), eq(actorId));
    }

    @Test
    void precheckSupportsSavedCredentialAndTemporaryKeyWithOptionalFields() {
        EnvironmentService service = service();
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID credentialId = UUID.randomUUID();
        when(credentialService.requireActive(credentialId, projectId))
                .thenReturn(credential(projectId, credentialId, actorId));
        when(taskService.create(any())).thenAnswer(invocation -> task(projectId, invocation.getArgument(0)));

        service.precheckConnection(projectId, new EnvironmentPrecheckRequest(EnvironmentRole.SOURCE_X86, "x86_64",
                "host", 2222, "root", credentialId, null, null, null, null, null, null, "/work", 42),
                actorId, false, new MockHttpServletRequest());

        UUID payloadId = UUID.randomUUID();
        TaskSecretPayloadService.PreparedSecret prepared = new TaskSecretPayloadService.PreparedSecret(
                payloadId, TaskSecretPayloadService.SSH_PRECHECK_CREDENTIAL, "a".repeat(64), JSONB.valueOf("{}"), "v1");
        when(taskSecretPayloadService.prepareSshPrecheckCredential(CredentialKind.SSH_KEY, "root", null, "key", "pass"))
                .thenReturn(prepared);
        service.precheckConnection(projectId, new EnvironmentPrecheckRequest(EnvironmentRole.TARGET_RISCV, "riscv64",
                "host", null, "root", null, EnvironmentLoginType.KEY, null, "key", "pass", null,
                null, null, null), actorId, false, new MockHttpServletRequest());

        verify(taskSecretPayloadService).save(eq(prepared), eq(projectId), org.mockito.ArgumentMatchers.any(), eq(actorId));
        verify(taskService, org.mockito.Mockito.times(2)).create(any());
    }

    @Test
    void checkAndCollectApplyDefaultsAndPreserveExplicitOptions() {
        EnvironmentService service = service();
        UUID actorId = UUID.randomUUID();
        EnvironmentView environment = environment(UUID.randomUUID(), UUID.randomUUID(), null, true, actorId);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(taskService.create(any())).thenAnswer(invocation -> task(environment.projectId(), invocation.getArgument(0)));

        service.check(environment.projectId(), environment.id(), null, actorId, false, new MockHttpServletRequest());
        service.check(environment.projectId(), environment.id(), new EnvironmentCheckRequest(
                List.of(EnvironmentCheckItem.CONNECTION), " /work ", 10), actorId, false, new MockHttpServletRequest());
        service.collect(environment.projectId(), environment.id(), null, actorId, false, new MockHttpServletRequest());
        service.collect(environment.projectId(), environment.id(), new EnvironmentCollectRequest(
                List.of(EnvironmentCollectScope.OS), 11), actorId, false, new MockHttpServletRequest());

        verify(taskService, org.mockito.Mockito.times(4)).create(any());
        verify(taskService).create(argThat(command -> java.util.Objects.equals(
                        command.inputSnapshot().get("checkItems"), List.of("CONNECTION"))
                && java.util.Objects.equals(command.inputSnapshot().get("workingDirectory"), "/work")
                && java.util.Objects.equals(command.inputSnapshot().get("timeoutSeconds"), 10)));
        verify(taskService).create(argThat(command -> java.util.Objects.equals(
                        command.inputSnapshot().get("collectScopes"), List.of("OS"))
                && java.util.Objects.equals(command.inputSnapshot().get("timeoutSeconds"), 11)));
    }

    @Test
    void runScriptRejectsInvalidContentAndAllowsParameterizedBuiltinScript() {
        EnvironmentService service = service();
        UUID actorId = UUID.randomUUID();
        EnvironmentView environment = environment(UUID.randomUUID(), UUID.randomUUID(), null, true, actorId);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(taskService.create(any())).thenAnswer(invocation -> task(environment.projectId(), invocation.getArgument(0)));

        assertThatThrownBy(() -> service.runScript(environment.projectId(), environment.id(), null,
                actorId, false, new MockHttpServletRequest())).isInstanceOf(ApiException.class)
                .extracting("code").isEqualTo("SCRIPT_TYPE_REQUIRED");
        assertThatThrownBy(() -> service.runScript(environment.projectId(), environment.id(),
                new RunScriptRequest(null, null, null, null, null), actorId, false, new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class).extracting("code").isEqualTo("SCRIPT_TYPE_REQUIRED");
        assertThatThrownBy(() -> service.runScript(environment.projectId(), environment.id(),
                new RunScriptRequest(EnvironmentScriptType.ENV_CHECK, "echo no", null, null, null),
                actorId, false, new MockHttpServletRequest())).isInstanceOf(ApiException.class)
                .extracting("code").isEqualTo("SCRIPT_CONTENT_NOT_ALLOWED");
        assertThatThrownBy(() -> service.runScript(environment.projectId(), environment.id(),
                new RunScriptRequest(EnvironmentScriptType.CUSTOM_BASH, " ", null, null, null),
                actorId, false, new MockHttpServletRequest())).isInstanceOf(ApiException.class)
                .extracting("code").isEqualTo("SCRIPT_REQUIRED");

        TaskResponse response = service.runScript(environment.projectId(), environment.id(),
                new RunScriptRequest(EnvironmentScriptType.ENV_CHECK, null, 20, " /work ", Map.of("mode", "fast")),
                actorId, false, new MockHttpServletRequest());
        assertThat(response.type()).isEqualTo(RvPortTaskTypes.ENV_RUN_SCRIPT);
        verify(taskScriptPayloadService, never()).save(any(), any(), any(), any(), any());
    }

    @Test
    void taskOptionsHandleEmptyListsBlankDirectoryAndMissingTimeout() {
        EnvironmentService service = service();
        UUID actorId = UUID.randomUUID();
        EnvironmentView environment = environment(UUID.randomUUID(), UUID.randomUUID(), null, true, actorId);
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(taskService.create(any())).thenAnswer(invocation -> task(environment.projectId(), invocation.getArgument(0)));

        service.testConnection(environment.projectId(), environment.id(), null,
                actorId, false, new MockHttpServletRequest());
        service.check(environment.projectId(), environment.id(), new EnvironmentCheckRequest(List.of(), " ", null),
                actorId, false, new MockHttpServletRequest());
        service.collect(environment.projectId(), environment.id(), new EnvironmentCollectRequest(List.of(), null),
                actorId, false, new MockHttpServletRequest());

        verify(taskService, org.mockito.Mockito.times(3)).create(any());
    }

    @Test
    void updateCanReplaceCredentialWithPasswordOrKey() {
        EnvironmentService service = service();
        UUID actorId = UUID.randomUUID();
        EnvironmentView current = environment(UUID.randomUUID(), UUID.randomUUID(), null, true, actorId);
        CredentialView first = credential(current.projectId(), UUID.randomUUID(), actorId);
        CredentialView second = credential(current.projectId(), UUID.randomUUID(), actorId);
        when(environmentRepository.findById(current.id())).thenReturn(Optional.of(current));
        when(credentialService.create(nullable(CreateCredentialCommand.class))).thenReturn(first, second);
        when(credentialService.requireActive(any(), eq(current.projectId())))
                .thenAnswer(invocation -> credential(current.projectId(), invocation.getArgument(0), actorId));
        when(environmentRepository.update(eq(current.id()), any(), any(), any(), any(), anyInt(), any(), any(),
                nullable(UUID.class), nullable(String.class), anyBoolean(), anyBoolean())).thenReturn(current);
        when(environmentRepository.findDirectDependents(current.id())).thenReturn(List.of());

        service.update(current.id(), new UpdateEnvironmentRequest(null, null, null, " new-host ", null, " new-user ",
                null, EnvironmentLoginType.PASSWORD, "secret", null, null, "password", null, null, null, null),
                actorId, false, new MockHttpServletRequest());
        service.update(current.id(), new UpdateEnvironmentRequest(null, null, null, null, null, null,
                null, EnvironmentLoginType.KEY, null, "key", "pass", "key-name", null, null, null, null),
                actorId, false, new MockHttpServletRequest());

        verify(credentialService).sshPassword(current.projectId(), actorId, "password", "new-host", "new-user", "secret");
        verify(credentialService).sshKey(current.projectId(), actorId, "key-name", current.host(), current.username(), "key", "pass");
    }

    private UpdateEnvironmentRequest update(String name, EnvironmentRole role, String arch, String host,
                                             Integer port, String username, UUID credentialId, UUID jumpHostId,
                                             String workingDirectory, Boolean enabled) {
        return new UpdateEnvironmentRequest(name, role, arch, host, port, username, credentialId, null,
                null, null, null, null, jumpHostId, null, workingDirectory, enabled);
    }

    private EnvironmentService service() {
        lenient().when(projectAccessService.requireProjectAccess(any(), any(), eq(false)))
                .thenAnswer(invocation -> project(invocation.getArgument(0), invocation.getArgument(1)));
        lenient().when(projectAccessService.requireEnvironmentAccess(any(), any(), eq(false)))
                .thenAnswer(invocation -> environmentRepository.findById(invocation.getArgument(0))
                        .orElseThrow(() -> new ApiException(org.springframework.http.HttpStatus.NOT_FOUND, "ENVIRONMENT_NOT_FOUND", "环境不存在")));
        return new EnvironmentService(environmentRepository, credentialService, projectRepository, taskService, auditLogService,
                projectAccessService, projectRuntimeEnvironmentService, taskScriptPayloadService, taskSecretPayloadService);
    }

    private ProjectView project(UUID projectId, UUID createdBy) {
        return new ProjectView(
                projectId,
                "demo",
                null,
                "x86_64",
                "riscv64",
                ProjectStage.PROJECT_CREATED,
                ProjectStatus.ACTIVE,
                null,
                createdBy,
                OffsetDateTime.now(),
                null
        );
    }

    private CredentialView credential(UUID projectId, UUID credentialId, UUID ownerId) {
        return new CredentialView(
                credentialId,
                projectId,
                ownerId,
                CredentialKind.SSH_PASSWORD,
                "ssh",
                "root@host",
                "local-v1",
                CredentialStatus.ACTIVE,
                OffsetDateTime.now(),
                null
        );
    }

    private EnvironmentView environment(UUID projectId, UUID id, UUID jumpHostId, boolean enabled) {
        return environment(projectId, id, jumpHostId, enabled, UUID.randomUUID());
    }

    private EnvironmentView environment(UUID projectId, UUID id, UUID jumpHostId, boolean enabled, UUID createdBy) {
        return new EnvironmentView(
                id,
                projectId,
                "env-" + id.toString().substring(0, 4),
                EnvironmentRole.TARGET_RISCV,
                "riscv64",
                "192.0.2.10",
                22,
                "root",
                UUID.randomUUID(),
                jumpHostId,
                "/workspace",
                enabled ? EnvironmentStatus.UNKNOWN : EnvironmentStatus.DISABLED,
                enabled,
                null,
                null,
                createdBy,
                OffsetDateTime.now(),
                null
        );
    }

    private TaskResponse task(UUID projectId, TaskCreateCommand command) {
        return new TaskResponse(
                UUID.randomUUID(),
                projectId,
                command.type(),
                TaskStatus.PENDING,
                0,
                command.message(),
                OffsetDateTime.now(),
                null,
                null,
                null,
                null,
                null,
                java.util.Map.of()
        );
    }
}
