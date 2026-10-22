package cn.rvport.backend.environment;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.credential.CredentialKind;
import cn.rvport.backend.credential.CredentialService;
import cn.rvport.backend.credential.CredentialSummaryResponse;
import cn.rvport.backend.credential.CredentialView;
import cn.rvport.backend.project.ProjectRepository;
import cn.rvport.backend.project.ProjectView;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.project.runtime.ProjectRuntimeEnvironmentService;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.task.TaskCreateCommand;
import cn.rvport.backend.task.TaskResponse;
import cn.rvport.backend.task.TaskService;
import cn.rvport.backend.task.TaskSecretPayloadService;
import cn.rvport.backend.task.TaskScriptPayloadService;
import jakarta.servlet.http.HttpServletRequest;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class EnvironmentService {

    private final EnvironmentRepository environmentRepository;
    private final CredentialService credentialService;
    private final ProjectRepository projectRepository;
    private final TaskService taskService;
    private final AuditLogService auditLogService;
    private final ProjectAccessService projectAccessService;
    private final ProjectRuntimeEnvironmentService projectRuntimeEnvironmentService;
    private final TaskScriptPayloadService taskScriptPayloadService;
    private final TaskSecretPayloadService taskSecretPayloadService;

    public EnvironmentService(
            EnvironmentRepository environmentRepository,
            CredentialService credentialService,
            ProjectRepository projectRepository,
            TaskService taskService,
            AuditLogService auditLogService,
            ProjectAccessService projectAccessService,
            ProjectRuntimeEnvironmentService projectRuntimeEnvironmentService,
            TaskScriptPayloadService taskScriptPayloadService,
            TaskSecretPayloadService taskSecretPayloadService
    ) {
        this.environmentRepository = environmentRepository;
        this.credentialService = credentialService;
        this.projectRepository = projectRepository;
        this.taskService = taskService;
        this.auditLogService = auditLogService;
        this.projectAccessService = projectAccessService;
        this.projectRuntimeEnvironmentService = projectRuntimeEnvironmentService;
        this.taskScriptPayloadService = taskScriptPayloadService;
        this.taskSecretPayloadService = taskSecretPayloadService;
    }

    @Transactional(readOnly = true)
    public PageResponse<EnvironmentResponse> list(UUID projectId, EnvironmentListRequest request, UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        long total = environmentRepository.count(projectId, request.role(), request.status(), request.enabled());
        List<EnvironmentResponse> items = environmentRepository.list(projectId, request.role(), request.status(), request.enabled(), page, pageSize)
                .stream()
                .map(this::toResponse)
                .toList();
        return PageResponse.of(items, page, pageSize, total);
    }

    @Transactional
    public EnvironmentResponse create(
            UUID projectId,
            CreateEnvironmentRequest request,
            UUID actorUserId,
            boolean superAdmin,
            HttpServletRequest httpRequest
    ) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        UUID credentialId = resolveCredentialForCreate(projectId, request, actorUserId);
        EnvironmentView jumpHost = validateJumpHost(projectId, null, request.jumpHostEnvironmentId());
        EnvironmentView created = environmentRepository.create(
                projectId,
                trim(request.name()),
                request.role(),
                trim(request.arch()),
                trim(request.host()),
                request.sshPort() == null ? 22 : request.sshPort(),
                trim(request.username()),
                credentialId,
                jumpHost == null ? null : jumpHost.id(),
                trimToNull(request.workingDirectory()),
                actorUserId
        );
        auditLogService.record(projectId, actorUserId, "environment.create", "environment", created.id(),
                Map.of("name", created.name(), "role", created.role().name(), "hasJumpHost", created.jumpHostEnvironmentId() != null),
                httpRequest);
        return toResponse(created);
    }

    @Transactional
    public TaskResponse precheckConnection(
            UUID projectId,
            EnvironmentPrecheckRequest request,
            UUID actorUserId,
            boolean superAdmin,
            HttpServletRequest httpRequest
    ) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        PrecheckCredentialReference credentialReference = resolveCredentialForPrecheck(projectId, request);
        EnvironmentView jumpHost = validateJumpHost(projectId, null, request.jumpHostEnvironmentId());

        Map<String, Object> target = new java.util.LinkedHashMap<>();
        target.put("role", request.role().name());
        target.put("arch", trim(request.arch()));
        target.put("host", trim(request.host()));
        target.put("sshPort", request.sshPort() == null ? 22 : request.sshPort());
        target.put("username", trim(request.username()));
        if (credentialReference.credentialId() != null) {
            target.put("credentialId", credentialReference.credentialId());
        } else {
            target.put("temporaryCredentialPayloadId", credentialReference.preparedSecret().id());
            target.put("temporaryCredentialSha256", credentialReference.preparedSecret().secretSha256());
        }
        if (request.workingDirectory() != null && !request.workingDirectory().isBlank()) {
            target.put("workingDirectory", trim(request.workingDirectory()));
        }

        Map<String, Object> input = new java.util.LinkedHashMap<>();
        input.put("projectId", projectId);
        input.put("environmentRole", request.role().name());
        input.put("jumpHostEnvironmentId", jumpHost == null ? null : jumpHost.id());
        input.put("target", target);
        if (request.timeoutSeconds() != null) {
            input.put("timeoutSeconds", request.timeoutSeconds());
        }

        TaskResponse response = taskService.create(new TaskCreateCommand(
                projectId,
                RvPortTaskTypes.ENV_TEST_CONNECTION,
                input,
                actorUserId,
                null,
                "新建环境连接预检已创建"
        ));
        auditLogService.record(projectId, actorUserId, "environment.precheck_connection", "project", projectId,
                Map.of("taskId", response.id(), "role", request.role().name(), "hasJumpHost", jumpHost != null),
                httpRequest);
        if (credentialReference.preparedSecret() != null) {
            taskSecretPayloadService.save(credentialReference.preparedSecret(), projectId, response.id(), actorUserId);
        }
        return response;
    }

    @Transactional(readOnly = true)
    public EnvironmentResponse get(UUID environmentId, UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireEnvironmentAccess(environmentId, actorUserId, superAdmin);
        return toResponse(requireEnvironment(environmentId));
    }

    @Transactional
    public EnvironmentResponse update(
            UUID environmentId,
            UpdateEnvironmentRequest request,
            UUID actorUserId,
            boolean superAdmin,
            HttpServletRequest httpRequest
    ) {
        EnvironmentView current = projectAccessService.requireEnvironmentAccess(environmentId, actorUserId, superAdmin);
        boolean enabled = request.enabled() == null ? current.enabled() : request.enabled();
        if (!enabled && environmentRepository.isReferencedAsJumpHost(environmentId)) {
            throw new ApiException(HttpStatus.CONFLICT, "JUMP_HOST_IN_USE", "跳板机仍被其他环境引用，不能禁用");
        }
        if (!enabled) {
            projectRuntimeEnvironmentService.assertEnvironmentNotSelected(environmentId);
        }

        UUID credentialId = resolveCredentialForUpdate(current, request, actorUserId);
        UUID jumpHostId = current.jumpHostEnvironmentId();
        if (Boolean.TRUE.equals(request.clearJumpHost())) {
            jumpHostId = null;
        } else if (request.jumpHostEnvironmentId() != null) {
            jumpHostId = validateJumpHost(current.projectId(), current.id(), request.jumpHostEnvironmentId()).id();
        }

        String name = valueOrCurrent(request.name(), current.name());
        EnvironmentRole role = request.role() == null ? current.role() : request.role();
        String arch = valueOrCurrent(request.arch(), current.arch());
        String host = valueOrCurrent(request.host(), current.host());
        int sshPort = request.sshPort() == null ? current.sshPort() : request.sshPort();
        String username = valueOrCurrent(request.username(), current.username());
        String workingDirectory = request.workingDirectory() == null
                ? current.workingDirectory()
                : trimToNull(request.workingDirectory());
        boolean effectiveConfigurationChanged = current.role() != role
                || !Objects.equals(current.arch(), arch)
                || !Objects.equals(current.host(), host)
                || current.sshPort() != sshPort
                || !Objects.equals(current.username(), username)
                || !Objects.equals(current.credentialId(), credentialId)
                || !Objects.equals(current.jumpHostEnvironmentId(), jumpHostId)
                || !Objects.equals(current.workingDirectory(), workingDirectory)
                || current.enabled() != enabled;

        EnvironmentView updated = environmentRepository.update(
                environmentId,
                name,
                role,
                arch,
                host,
                sshPort,
                username,
                credentialId,
                jumpHostId,
                workingDirectory,
                enabled,
                effectiveConfigurationChanged
        );
        if (updated == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "ENVIRONMENT_NOT_FOUND", "环境不存在");
        }
        auditLogService.record(updated.projectId(), actorUserId, "environment.update", "environment", updated.id(),
                Map.of("name", updated.name(), "enabled", updated.enabled(), "hasJumpHost", updated.jumpHostEnvironmentId() != null),
                httpRequest);
        if (effectiveConfigurationChanged) {
            List<UUID> dependentIds = environmentRepository.findDirectDependents(updated.id()).stream()
                    .map(EnvironmentView::id)
                    .toList();
            if (!dependentIds.isEmpty()) {
                environmentRepository.invalidateConfigurations(dependentIds);
            }
            List<UUID> affectedEnvironmentIds = new java.util.ArrayList<>();
            affectedEnvironmentIds.add(updated.id());
            affectedEnvironmentIds.addAll(dependentIds);
            projectRuntimeEnvironmentService.bumpVersionIfAnySelected(
                    updated.projectId(), affectedEnvironmentIds, actorUserId);
        }
        return toResponse(updated);
    }

    @Transactional
    public TaskResponse testConnection(
            UUID projectId,
            UUID environmentId,
            EnvironmentRunRequest runRequest,
            UUID actorUserId,
            boolean superAdmin,
            HttpServletRequest request
    ) {
        EnvironmentView environment = requireRunnableEnvironment(projectId, environmentId, actorUserId, superAdmin);
        Map<String, ?> safeInput = optionalTimeout(runRequest == null ? null : runRequest.timeoutSeconds());
        TaskResponse response = createEnvironmentTask(environment, RvPortTaskTypes.ENV_TEST_CONNECTION, safeInput, actorUserId, "环境连接测试已创建");
        auditLogService.record(environment.projectId(), actorUserId, "environment.test_connection", "environment", environment.id(),
                Map.of("taskId", response.id()), request);
        return response;
    }

    @Transactional
    public TaskResponse check(
            UUID projectId,
            UUID environmentId,
            EnvironmentCheckRequest checkRequest,
            UUID actorUserId,
            boolean superAdmin,
            HttpServletRequest request
    ) {
        EnvironmentView environment = requireRunnableEnvironment(projectId, environmentId, actorUserId, superAdmin);
        List<EnvironmentCheckItem> checkItems = defaultCheckItems(checkRequest == null ? null : checkRequest.checkItems());
        Map<String, Object> safeInput = new java.util.LinkedHashMap<>();
        safeInput.put("scriptType", EnvironmentScriptType.ENV_CHECK.name());
        safeInput.put("checkItems", checkItems.stream().map(Enum::name).toList());
        if (checkRequest != null && checkRequest.workingDirectory() != null && !checkRequest.workingDirectory().isBlank()) {
            safeInput.put("workingDirectory", checkRequest.workingDirectory().trim());
        }
        if (checkRequest != null && checkRequest.timeoutSeconds() != null) {
            safeInput.put("timeoutSeconds", checkRequest.timeoutSeconds());
        }
        TaskResponse response = createEnvironmentTask(environment, RvPortTaskTypes.ENV_RUN_SCRIPT, safeInput, actorUserId, "环境检查任务已创建");
        auditLogService.record(environment.projectId(), actorUserId, "environment.check", "environment", environment.id(),
                Map.of("taskId", response.id(), "checkItems", safeInput.get("checkItems")), request);
        return response;
    }

    @Transactional
    public TaskResponse collect(
            UUID projectId,
            UUID environmentId,
            EnvironmentCollectRequest collectRequest,
            UUID actorUserId,
            boolean superAdmin,
            HttpServletRequest request
    ) {
        EnvironmentView environment = requireRunnableEnvironment(projectId, environmentId, actorUserId, superAdmin);
        Map<String, Object> safeInput = new java.util.LinkedHashMap<>();
        safeInput.put("collectScopes", defaultCollectScopes(collectRequest == null ? null : collectRequest.collectScopes()).stream()
                .map(Enum::name)
                .toList());
        if (collectRequest != null && collectRequest.timeoutSeconds() != null) {
            safeInput.put("timeoutSeconds", collectRequest.timeoutSeconds());
        }
        TaskResponse response = createEnvironmentTask(environment, RvPortTaskTypes.ENV_COLLECT, safeInput, actorUserId, "环境采集任务已创建");
        auditLogService.record(environment.projectId(), actorUserId, "environment.collect", "environment", environment.id(),
                Map.of("taskId", response.id()), request);
        return response;
    }

    @Transactional
    public TaskResponse runScript(
            UUID projectId,
            UUID environmentId,
            RunScriptRequest runScriptRequest,
            UUID actorUserId,
            boolean superAdmin,
            HttpServletRequest request
    ) {
        EnvironmentView environment = requireRunnableEnvironment(projectId, environmentId, actorUserId, superAdmin);
        if (runScriptRequest == null || runScriptRequest.scriptType() == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "SCRIPT_TYPE_REQUIRED", "脚本类型不能为空");
        }
        SafeScriptInput safeScriptInput = safeScriptInput(runScriptRequest);
        Map<String, Object> safeInput = safeScriptInput.input();
        TaskResponse response = createEnvironmentTask(environment, RvPortTaskTypes.ENV_RUN_SCRIPT, safeInput, actorUserId, "远程脚本任务已创建");
        if (safeScriptInput.payloadId() != null) {
            taskScriptPayloadService.save(
                    safeScriptInput.payloadId(),
                    environment.projectId(),
                    response.id(),
                    runScriptRequest.script(),
                    actorUserId
            );
        }
        auditLogService.record(environment.projectId(), actorUserId, "environment.run_script", "environment", environment.id(),
                Map.of("taskId", response.id(), "scriptType", runScriptRequest.scriptType().name()),
                request);
        return response;
    }

    @Transactional(readOnly = true)
    public PageResponse<EnvironmentSnapshotResponse> snapshots(UUID environmentId, SnapshotListRequest request, UUID actorUserId, boolean superAdmin) {
        EnvironmentView environment = projectAccessService.requireEnvironmentAccess(environmentId, actorUserId, superAdmin);
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        long total = environmentRepository.countSnapshots(environment.id());
        List<EnvironmentSnapshotResponse> items = environmentRepository.listSnapshots(environment.id(), page, pageSize)
                .stream()
                .map(EnvironmentSnapshotResponse::from)
                .toList();
        return PageResponse.of(items, page, pageSize, total);
    }

    public EnvironmentSummaryResponse summary(UUID projectId) {
        return environmentRepository.summary(projectId);
    }

    public EnvironmentView requireEnvironment(UUID environmentId) {
        return environmentRepository.findById(environmentId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "ENVIRONMENT_NOT_FOUND", "环境不存在"));
    }

    private TaskResponse createEnvironmentTask(
            EnvironmentView environment,
            String type,
            Map<String, ?> extraInput,
            UUID actorUserId,
            String message
    ) {
        Map<String, Object> input = new java.util.LinkedHashMap<>();
        input.put("projectId", environment.projectId());
        input.put("environmentId", environment.id());
        input.put("environmentRole", environment.role().name());
        input.put("jumpHostEnvironmentId", environment.jumpHostEnvironmentId());
        input.put("environmentConfigVersion", environment.configVersion());
        input.putAll(extraInput);
        return taskService.create(new TaskCreateCommand(environment.projectId(), type, input, actorUserId, null, message));
    }

    private EnvironmentView requireEnabledEnvironment(UUID environmentId) {
        EnvironmentView environment = requireEnvironment(environmentId);
        if (!environment.enabled()) {
            throw new ApiException(HttpStatus.CONFLICT, "ENVIRONMENT_DISABLED", "环境已禁用，不能创建新任务");
        }
        return environment;
    }

    private EnvironmentView requireRunnableEnvironment(UUID projectId, UUID environmentId, UUID actorUserId, boolean superAdmin) {
        ProjectView project = projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        EnvironmentView environment = requireEnabledEnvironment(environmentId);
        if (!environment.projectId().equals(project.id())) {
            throw new ApiException(HttpStatus.NOT_FOUND, "ENVIRONMENT_NOT_FOUND", "环境不存在");
        }
        return environment;
    }

    private UUID resolveCredentialForCreate(UUID projectId, CreateEnvironmentRequest request, UUID actorUserId) {
        if (request.credentialId() != null) {
            return credentialService.requireActive(request.credentialId(), projectId).id();
        }
        CredentialView credential = createCredential(projectId, actorUserId, request);
        return credential.id();
    }

    private PrecheckCredentialReference resolveCredentialForPrecheck(UUID projectId, EnvironmentPrecheckRequest request) {
        if (request.credentialId() != null) {
            return new PrecheckCredentialReference(credentialService.requireActive(request.credentialId(), projectId).id(), null);
        }
        if (request.loginType() == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "CREDENTIAL_REQUIRED", "必须提供 SSH 凭据");
        }
        TaskSecretPayloadService.PreparedSecret prepared = taskSecretPayloadService.prepareSshPrecheckCredential(
                request.loginType() == EnvironmentLoginType.PASSWORD ? CredentialKind.SSH_PASSWORD : CredentialKind.SSH_KEY,
                trim(request.username()),
                request.password(),
                request.privateKey(),
                request.passphrase()
        );
        return new PrecheckCredentialReference(null, prepared);
    }

    private UUID resolveCredentialForUpdate(EnvironmentView current, UpdateEnvironmentRequest request, UUID actorUserId) {
        if (request.credentialId() != null) {
            return credentialService.requireActive(request.credentialId(), current.projectId()).id();
        }
        if (request.loginType() == null) {
            return current.credentialId();
        }
        CredentialView credential = createCredential(current.projectId(), actorUserId, request, current);
        return credential.id();
    }

    private CredentialView createCredential(UUID projectId, UUID actorUserId, CreateEnvironmentRequest request) {
        EnvironmentLoginType loginType = request.loginType();
        if (loginType == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "CREDENTIAL_REQUIRED", "必须提供 SSH 凭据");
        }
        if (loginType == EnvironmentLoginType.PASSWORD) {
            return credentialService.create(credentialService.sshPassword(
                    projectId, actorUserId, request.credentialName(), trim(request.host()), trim(request.username()), request.password()));
        }
        return credentialService.create(credentialService.sshKey(
                projectId, actorUserId, request.credentialName(), trim(request.host()), trim(request.username()), request.privateKey(), request.passphrase()));
    }

    private CredentialView createCredential(UUID projectId, UUID actorUserId, UpdateEnvironmentRequest request, EnvironmentView current) {
        String host = valueOrCurrent(request.host(), current.host());
        String username = valueOrCurrent(request.username(), current.username());
        if (request.loginType() == EnvironmentLoginType.PASSWORD) {
            return credentialService.create(credentialService.sshPassword(
                    projectId, actorUserId, request.credentialName(), host, username, request.password()));
        }
        return credentialService.create(credentialService.sshKey(
                projectId, actorUserId, request.credentialName(), host, username, request.privateKey(), request.passphrase()));
    }

    private EnvironmentView validateJumpHost(UUID projectId, UUID environmentId, UUID jumpHostEnvironmentId) {
        if (jumpHostEnvironmentId == null) {
            return null;
        }
        if (jumpHostEnvironmentId.equals(environmentId)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "JUMP_HOST_SELF_REFERENCE", "环境不能引用自己作为跳板机");
        }
        EnvironmentView jumpHost = requireEnvironment(jumpHostEnvironmentId);
        if (!jumpHost.projectId().equals(projectId)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "JUMP_HOST_PROJECT_MISMATCH", "跳板机必须属于同一项目");
        }
        if (!jumpHost.enabled()) {
            throw new ApiException(HttpStatus.CONFLICT, "JUMP_HOST_DISABLED", "跳板机已禁用");
        }
        if (jumpHost.jumpHostEnvironmentId() != null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "JUMP_HOST_CHAIN_NOT_SUPPORTED", "MVP 暂不支持多级跳板机");
        }
        return jumpHost;
    }

    private EnvironmentResponse toResponse(EnvironmentView view) {
        CredentialSummaryResponse credential = credentialService.requireActive(view.credentialId(), view.projectId()).toSummary();
        JumpHostSummaryResponse jumpHost = null;
        if (view.jumpHostEnvironmentId() != null) {
            jumpHost = JumpHostSummaryResponse.from(requireEnvironment(view.jumpHostEnvironmentId()));
        }
        EnvironmentBasicInfoResponse basicInfo = EnvironmentBasicInfoResponse.from(
                Optional.ofNullable(environmentRepository.findLatestBasicInfo(view.id(), view.configVersion()))
                        .flatMap(value -> value)
                        .orElse(null));
        return EnvironmentResponse.from(view, credential, jumpHost, basicInfo);
    }

    private ProjectView requireProject(UUID projectId) {
        return projectRepository.findById(projectId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在"));
    }

    private Map<String, ?> optionalTimeout(Integer timeoutSeconds) {
        if (timeoutSeconds == null) {
            return Map.of();
        }
        return Map.of("timeoutSeconds", timeoutSeconds);
    }

    private List<EnvironmentCheckItem> defaultCheckItems(List<EnvironmentCheckItem> checkItems) {
        if (checkItems == null || checkItems.isEmpty()) {
            return List.of(
                    EnvironmentCheckItem.CONNECTION,
                    EnvironmentCheckItem.BASIC_TOOLS,
                    EnvironmentCheckItem.WORKING_DIRECTORY,
                    EnvironmentCheckItem.PERMISSIONS
            );
        }
        return List.copyOf(checkItems);
    }

    private List<EnvironmentCollectScope> defaultCollectScopes(List<EnvironmentCollectScope> collectScopes) {
        if (collectScopes == null || collectScopes.isEmpty()) {
            return List.of(
                    EnvironmentCollectScope.OS,
                    EnvironmentCollectScope.PACKAGE_MANAGER,
                    EnvironmentCollectScope.REPOSITORIES,
                    EnvironmentCollectScope.INSTALLED_PACKAGES,
                    EnvironmentCollectScope.TOOL_VERSIONS
            );
        }
        return List.copyOf(collectScopes);
    }

    private SafeScriptInput safeScriptInput(RunScriptRequest request) {
        Map<String, Object> safeInput = new java.util.LinkedHashMap<>();
        UUID payloadId = null;
        safeInput.put("scriptType", request.scriptType().name());
        if (request.timeoutSeconds() != null) {
            safeInput.put("timeoutSeconds", request.timeoutSeconds());
        }
        if (request.workingDirectory() != null && !request.workingDirectory().isBlank()) {
            safeInput.put("workingDirectory", request.workingDirectory().trim());
        }
        if (request.parameters() != null && !request.parameters().isEmpty()) {
            safeInput.put("parameters", request.parameters());
        }
        if (request.script() != null && !request.script().isBlank()) {
            if (request.scriptType() != EnvironmentScriptType.CUSTOM_BASH) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "SCRIPT_CONTENT_NOT_ALLOWED", "当前脚本类型不允许提交脚本内容");
            }
            payloadId = UUID.randomUUID();
            safeInput.put("scriptPayloadId", payloadId);
            safeInput.put("scriptSha256", sha256(request.script()));
            safeInput.put("scriptLength", request.script().length());
        }
        if (request.scriptType() == EnvironmentScriptType.CUSTOM_BASH && (request.script() == null || request.script().isBlank())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "SCRIPT_REQUIRED", "自定义脚本不能为空");
        }
        return new SafeScriptInput(safeInput, payloadId);
    }

    private String trim(String value) {
        return value == null ? null : value.trim();
    }

    private String trimToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    private String valueOrCurrent(String value, String current) {
        return value == null ? current : trim(value);
    }

    private String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException(ex);
        }
    }

    private record SafeScriptInput(Map<String, Object> input, UUID payloadId) {
    }

    private record PrecheckCredentialReference(UUID credentialId, TaskSecretPayloadService.PreparedSecret preparedSecret) {
    }
}
