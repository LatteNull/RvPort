package cn.rvport.backend.environment.runtime;

import cn.rvport.backend.credential.CredentialService;
import cn.rvport.backend.environment.EnvironmentRepository;
import cn.rvport.backend.environment.EnvironmentStatus;
import cn.rvport.backend.environment.EnvironmentView;
import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskExecutionException;
import cn.rvport.backend.task.TaskLogEventService;
import cn.rvport.backend.task.TaskLogType;
import cn.rvport.backend.task.TaskSecretPayloadService;
import cn.rvport.backend.task.TaskScriptPayloadService;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.ToolRunRepository;
import cn.rvport.backend.worker.TaskExecutionContext;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.Arrays;
import java.util.LinkedHashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.stereotype.Service;

@Service
public class SshRuntimeService {

    private static final String TOOL_NAME = "rvport-ssh-connectivity-probe";
    private static final String TOOL_VERSION = "1";
    private static final Pattern FIRST_NUMBER = Pattern.compile("\\d+");

    private final EnvironmentRepository environmentRepository;
    private final CredentialService credentialService;
    private final SshClientAdapter sshClientAdapter;
    private final ToolRunRepository toolRunRepository;
    private final TaskScriptPayloadService taskScriptPayloadService;
    private final TaskLogEventService taskLogEventService;
    private final TaskSecretPayloadService taskSecretPayloadService;

    public SshRuntimeService(
            EnvironmentRepository environmentRepository,
            CredentialService credentialService,
            SshClientAdapter sshClientAdapter,
            ToolRunRepository toolRunRepository,
            TaskScriptPayloadService taskScriptPayloadService,
            TaskLogEventService taskLogEventService,
            TaskSecretPayloadService taskSecretPayloadService
    ) {
        this.environmentRepository = environmentRepository;
        this.credentialService = credentialService;
        this.sshClientAdapter = sshClientAdapter;
        this.toolRunRepository = toolRunRepository;
        this.taskScriptPayloadService = taskScriptPayloadService;
        this.taskLogEventService = taskLogEventService;
        this.taskSecretPayloadService = taskSecretPayloadService;
    }

    public void testConnection(EnvironmentTaskInput input, TaskExecutionContext context) {
        RuntimeEnvironment runtime = runtimeEnvironment(input);
        UUID toolRunId = createToolRun(context, "rvport-ssh-connectivity-probe", "SSH 连接探测");
        try {
            context.progress(10, "开始 SSH 连接探测");
            context.throwIfCancellationRequested();
            SshCommandResult result = execute(runtime, input, probeCommand(runtime.workingDirectory(input)), input.timeoutSeconds(), context);
            writeLogs(context, result);
            Map<String, Object> summary = parseProbe(result);
            if (result.exitCode() != 0) {
                failProbe(context, toolRunId, runtime, result.exitCode(), summary, "SSH 探测命令执行失败");
            }
            if (!"ok".equals(summary.get("probe"))) {
                failProbe(context, toolRunId, runtime, result.exitCode(), summary, "SSH 探测输出无效");
            }
            context.publish(() -> {
                toolRunRepository.finish(toolRunId, TaskStatus.SUCCEEDED, result.exitCode(), summary);
                updateConnectionStatus(runtime, input, EnvironmentStatus.AVAILABLE, true);
                return null;
            });
            context.progress(90, "SSH 连接探测完成");
        } catch (SshRuntimeException ex) {
            context.publish(() -> {
                updateConnectionStatus(runtime, input, EnvironmentStatus.UNAVAILABLE, false);
                toolRunRepository.finish(toolRunId, TaskStatus.FAILED, null, Map.of("error", "SSH 命令执行失败"));
                return null;
            });
            throw new TaskExecutionException(sshErrorCode(ex), "SSH 命令执行失败", ex);
        }
    }

    public void checkEnvironment(EnvironmentTaskInput input, TaskExecutionContext context) {
        RuntimeEnvironment runtime = runtimeEnvironment(input);
        UUID toolRunId = createToolRun(context, "rvport-env-check", "环境检查");
        try {
            context.progress(10, "开始环境检查");
            context.throwIfCancellationRequested();
            SshCommandResult result = execute(runtime, input, checkCommand(input, runtime), input.timeoutSeconds(), context);
            writeLogs(context, result);
            Map<String, Object> summary = parseCheck(result);
            if (result.exitCode() != 0 || !"ok".equals(summary.get("check"))) {
                Map<String, Object> failedSummary = new LinkedHashMap<>(summary);
                failedSummary.put("error", "环境检查失败");
                finishTool(context, toolRunId, TaskStatus.FAILED, result.exitCode(), failedSummary);
                throw new TaskExecutionException(TaskErrorCode.REMOTE_COMMAND_FAILED, "环境检查失败", null);
            }
            context.publish(() -> {
            UUID snapshotId = environmentRepository.createSnapshot(
                    runtime.environment().id(),
                    runtime.environment().projectId(),
                    context.task().id(),
                    stringValue(summary.get("osName")),
                    stringValue(summary.get("osVersion")),
                    stringValue(summary.get("kernelVersion")),
                    stringValue(summary.get("arch")),
                    stringValue(summary.get("packageManager")),
                    Map.of(),
                    mapValue(summary.get("toolVersions")),
                    summary,
                    TaskStatus.SUCCEEDED,
                    OffsetDateTime.now(),
                    environmentConfigVersion(runtime, input)
            );
            toolRunRepository.finish(toolRunId, TaskStatus.SUCCEEDED, result.exitCode(), withBasicSnapshot(summary, snapshotId));
            updateConnectionStatus(runtime, input, EnvironmentStatus.AVAILABLE, true);
            updateLastCollectedAt(runtime, input);
            return null;
            });
            context.progress(90, "环境检查完成");
        } catch (SshRuntimeException ex) {
            context.publish(() -> {
                updateConnectionStatus(runtime, input, EnvironmentStatus.UNAVAILABLE, false);
                toolRunRepository.finish(toolRunId, TaskStatus.FAILED, null, Map.of("error", "环境检查 SSH 执行失败"));
                return null;
            });
            throw new TaskExecutionException(sshErrorCode(ex), "环境检查 SSH 执行失败", ex);
        }
    }

    public EnvironmentCollectionResult collectEnvironment(EnvironmentTaskInput input, TaskExecutionContext context) {
        RuntimeEnvironment runtime = runtimeEnvironment(input);
        UUID toolRunId = createToolRun(context, "rvport-env-collect", "环境信息采集");
        try {
            context.progress(10, "开始环境信息采集");
            context.throwIfCancellationRequested();
            SshCommandResult result = execute(runtime, input, collectCommand(input.collectScopes(),
                    "TARGET_RISCV".equals(runtime.environment().role().name()),
                    runtime.environment().role().name()), input.timeoutSeconds(), context);
            writeLogs(context, result);
            Map<String, Object> summary = parseCollect(result);
            if (result.exitCode() != 0 || !"ok".equals(summary.get("collect"))) {
                Map<String, Object> failedSummary = new LinkedHashMap<>(summary);
                failedSummary.put("error", "环境采集失败");
                finishTool(context, toolRunId, TaskStatus.FAILED, result.exitCode(), failedSummary);
                throw new TaskExecutionException(TaskErrorCode.REMOTE_COMMAND_FAILED, "环境采集失败", null);
            }
            UUID collectedSnapshotId = context.publish(() -> {
            UUID snapshotId = environmentRepository.createSnapshot(
                    runtime.environment().id(),
                    runtime.environment().projectId(),
                    context.task().id(),
                    stringValue(summary.get("osName")),
                    stringValue(summary.get("osVersion")),
                    stringValue(summary.get("kernelVersion")),
                    stringValue(summary.get("arch")),
                    stringValue(summary.get("packageManager")),
                    mapValue(summary.get("repositories")),
                    mapValue(summary.get("toolVersions")),
                    summary,
                    TaskStatus.SUCCEEDED,
                    OffsetDateTime.now(),
                    environmentConfigVersion(runtime, input)
            );
            createCollectedComponents(snapshotId, runtime.environment(), summary);
            toolRunRepository.finish(toolRunId, TaskStatus.SUCCEEDED, result.exitCode(), withSnapshot(summary, snapshotId));
            updateConnectionStatus(runtime, input, EnvironmentStatus.AVAILABLE, true);
            updateLastCollectedAt(runtime, input);
            return snapshotId;
            });
            context.progress(90, "环境信息采集完成");
            return new EnvironmentCollectionResult(collectedSnapshotId, toolRunId, result.exitCode(), summary);
        } catch (SshRuntimeException ex) {
            finishTool(context, toolRunId, TaskStatus.FAILED, null, Map.of("error", "环境采集 SSH 执行失败"));
            throw new TaskExecutionException(sshErrorCode(ex), "环境采集 SSH 执行失败", ex);
        }
    }

    public void runScript(EnvironmentTaskInput input, TaskExecutionContext context) {
        RuntimeEnvironment runtime = runtimeEnvironment(input);
        UUID toolRunId = createToolRun(context, "rvport-remote-script", "远程脚本执行");
        try {
            context.progress(10, "开始远程脚本执行");
            context.throwIfCancellationRequested();
            String scriptStdin = null;
            String command = scriptCommand(input, runtime);
            boolean streamOutput = "CUSTOM_BASH".equals(input.scriptType());
            if (streamOutput) {
                scriptStdin = taskScriptPayloadService.requireScript(input.scriptPayloadId(), input.projectId(), context.task().id(), input.scriptSha256());
            }
            SshCommandResult result = execute(runtime, input, command, scriptStdin, streamOutput, input.timeoutSeconds(), context);
            if (!streamOutput) {
                writeLogs(context, result);
            }
            Map<String, Object> summary = new LinkedHashMap<>();
            summary.put("scriptType", input.scriptType());
            summary.put("workingDirectoryConfigured", input.workingDirectory() != null && !input.workingDirectory().isBlank());
            summary.put("scriptSha256", input.scriptSha256());
            summary.put("scriptLength", input.scriptLength());
            summary.put("durationMs", result.duration().toMillis());
            summary.put("exitCode", result.exitCode());
            summary.put("logEventCount", taskLogEventService.count(context.task().id()));
            TaskStatus status = result.exitCode() == 0 ? TaskStatus.SUCCEEDED : TaskStatus.FAILED;
            finishTool(context, toolRunId, status, result.exitCode(), summary);
            if (result.exitCode() != 0) {
                throw new TaskExecutionException(TaskErrorCode.REMOTE_COMMAND_FAILED, "远程脚本执行失败", null);
            }
            context.progress(90, "远程脚本执行完成");
        } catch (TaskExecutionException ex) {
            finishTool(context, toolRunId, TaskStatus.FAILED, null, Map.of("error", ex.getMessage()));
            throw ex;
        } catch (SshRuntimeException ex) {
            finishTool(context, toolRunId, TaskStatus.FAILED, null, Map.of(
                    "error", "远程脚本 SSH 执行失败",
                    "sshError", safeExceptionSummary(ex)
            ));
            throw new TaskExecutionException(sshErrorCode(ex), "远程脚本 SSH 执行失败", ex);
        }
    }

    public SshCommandResult executeRemote(
            EnvironmentTaskInput input,
            String command,
            String stdin,
            boolean streamOutput,
            Integer timeoutSeconds,
            TaskExecutionContext context
    ) {
        return execute(runtimeEnvironment(input), input, command, stdin, streamOutput, timeoutSeconds, context);
    }

    public String temporaryScriptCommand(String workingDirectory) {
        return customBashCommand(workingDirectory);
    }

    private RuntimeEnvironment runtimeEnvironment(EnvironmentTaskInput input) {
        if (input.target() != null) {
            return targetRuntimeEnvironment(input);
        }
        EnvironmentView environment = environmentRepository.findById(input.environmentId())
                .orElseThrow(() -> new TaskExecutionException(TaskErrorCode.RESOURCE_NOT_FOUND, "环境不存在", null));
        if (!environment.projectId().equals(input.projectId())) {
            throw new TaskExecutionException(TaskErrorCode.PROJECT_MISMATCH, "环境不属于当前项目", null);
        }
        if (input.environmentConfigVersion() != null
                && input.environmentConfigVersion().longValue() != environment.configVersion()) {
            throw new TaskExecutionException(TaskErrorCode.RESOURCE_STALE, "环境配置已更新，当前任务不再有效", null);
        }
        if (!environment.enabled()) {
            throw new TaskExecutionException(TaskErrorCode.RESOURCE_DISABLED, "环境已禁用", null);
        }
        EnvironmentView jumpHost = null;
        if (environment.jumpHostEnvironmentId() != null) {
            jumpHost = environmentRepository.findById(environment.jumpHostEnvironmentId())
                    .orElseThrow(() -> new TaskExecutionException(TaskErrorCode.RESOURCE_NOT_FOUND, "跳板机环境不存在", null));
            if (!jumpHost.projectId().equals(environment.projectId())) {
                throw new TaskExecutionException(TaskErrorCode.PROJECT_MISMATCH, "跳板机不属于当前项目", null);
            }
            if (!jumpHost.enabled()) {
                throw new TaskExecutionException(TaskErrorCode.RESOURCE_DISABLED, "跳板机已禁用", null);
            }
            if (jumpHost.jumpHostEnvironmentId() != null) {
                throw new TaskExecutionException(TaskErrorCode.UNSUPPORTED_OPERATION, "不支持多级跳板机", null);
            }
        }
        return new RuntimeEnvironment(environment, jumpHost, true);
    }

    private RuntimeEnvironment targetRuntimeEnvironment(EnvironmentTaskInput input) {
        EnvironmentTaskInput.Target target = input.target();
        EnvironmentView jumpHost = null;
        if (input.jumpHostEnvironmentId() != null) {
            jumpHost = environmentRepository.findById(input.jumpHostEnvironmentId())
                    .orElseThrow(() -> new TaskExecutionException(TaskErrorCode.RESOURCE_NOT_FOUND, "跳板机环境不存在", null));
            if (!jumpHost.projectId().equals(input.projectId())) {
                throw new TaskExecutionException(TaskErrorCode.PROJECT_MISMATCH, "跳板机不属于当前项目", null);
            }
            if (!jumpHost.enabled()) {
                throw new TaskExecutionException(TaskErrorCode.RESOURCE_DISABLED, "跳板机已禁用", null);
            }
            if (jumpHost.jumpHostEnvironmentId() != null) {
                throw new TaskExecutionException(TaskErrorCode.UNSUPPORTED_OPERATION, "不支持多级跳板机", null);
            }
        }
        EnvironmentView environment = new EnvironmentView(
                null,
                input.projectId(),
                "未落库环境预检",
                target.role(),
                target.arch(),
                target.host(),
                target.sshPort(),
                target.username(),
                target.credentialId(),
                input.jumpHostEnvironmentId(),
                target.workingDirectory(),
                EnvironmentStatus.UNKNOWN,
                true,
                null,
                null,
                null,
                OffsetDateTime.now(),
                null
        );
        return new RuntimeEnvironment(environment, jumpHost, false);
    }

    private UUID createToolRun(TaskExecutionContext context, String toolName, String commandSummary) {
        return context.publish(() -> toolRunRepository.create(
                context.task().projectId(),
                context.task().id(),
                toolName,
                TOOL_VERSION,
                commandSummary,
                TaskStatus.RUNNING,
                OffsetDateTime.now()
        ));
    }

    private void finishTool(TaskExecutionContext context, UUID id, TaskStatus status, Integer exitCode, Map<String, Object> summary) {
        context.publish(() -> { toolRunRepository.finish(id, status, exitCode, summary); return null; });
    }

    private SshCommandResult execute(RuntimeEnvironment runtime, EnvironmentTaskInput input, String command, Integer timeoutSeconds, TaskExecutionContext context) {
        return execute(runtime, input, command, null, false, timeoutSeconds, context);
    }

    private SshCommandResult execute(
            RuntimeEnvironment runtime,
            EnvironmentTaskInput input,
            String command,
            String stdin,
            boolean streamOutput,
            Integer timeoutSeconds,
            TaskExecutionContext context
    ) {
        int effectiveTimeoutSeconds = timeoutSeconds == null ? 30 : timeoutSeconds;
        return sshClientAdapter.execute(new SshCommandRequest(
                target(runtime.environment(), input, context.task().id()),
                runtime.jumpHost() == null ? null : target(runtime.jumpHost()),
                command,
                stdin,
                streamOutput,
                Duration.ofSeconds(Math.max(10, effectiveTimeoutSeconds)),
                Duration.ofSeconds(effectiveTimeoutSeconds),
                context
        ));
    }

    private void writeLogs(TaskExecutionContext context, SshCommandResult result) {
        context.log(TaskLogType.STDOUT, result.stdout());
        context.log(TaskLogType.STDERR, result.stderr());
    }

    private void failProbe(TaskExecutionContext context, UUID toolRunId, RuntimeEnvironment runtime, int exitCode, Map<String, Object> summary, String message) {
        Map<String, Object> failedSummary = new LinkedHashMap<>(summary);
        failedSummary.put("error", message);
        context.publish(() -> {
            updateConnectionStatus(runtime, null, EnvironmentStatus.UNAVAILABLE, false);
            toolRunRepository.finish(toolRunId, TaskStatus.FAILED, exitCode, failedSummary);
            return null;
        });
        throw new TaskExecutionException(TaskErrorCode.REMOTE_COMMAND_FAILED, message, null);
    }

    private void updateConnectionStatus(
            RuntimeEnvironment runtime,
            EnvironmentTaskInput input,
            EnvironmentStatus status,
            boolean connected
    ) {
        if (runtime.persistedEnvironment()) {
            environmentRepository.updateConnectionStatus(
                    runtime.environment().id(),
                    environmentConfigVersion(runtime, input),
                    status,
                    connected);
        }
    }

    private void updateLastCollectedAt(RuntimeEnvironment runtime, EnvironmentTaskInput input) {
        if (runtime.persistedEnvironment()) {
            environmentRepository.updateLastCollectedAt(
                    runtime.environment().id(),
                    environmentConfigVersion(runtime, input));
        }
    }

    private long environmentConfigVersion(RuntimeEnvironment runtime, EnvironmentTaskInput input) {
        return input != null && input.environmentConfigVersion() != null
                ? input.environmentConfigVersion()
                : runtime.environment().configVersion();
    }

    private String sshErrorCode(SshRuntimeException ex) {
        return ex.errorCode() == null || ex.errorCode().isBlank() ? TaskErrorCode.HANDLER_FAILED : ex.errorCode();
    }

    private String safeExceptionSummary(Throwable throwable) {
        StringBuilder summary = new StringBuilder();
        Throwable current = throwable;
        int depth = 0;
        while (current != null && depth < 4) {
            if (!summary.isEmpty()) {
                summary.append(" <- ");
            }
            summary.append(current.getClass().getSimpleName());
            if (current.getMessage() != null && !current.getMessage().isBlank()) {
                summary.append(": ").append(current.getMessage());
            }
            current = current.getCause();
            depth++;
        }
        String text = summary.toString()
                .replace('\r', ' ')
                .replace('\n', ' ')
                .replaceAll("(?i)(password|token|privateKey|private_key|passphrase|secret)(\\s*[=:]\\s*)\\S+", "$1$2****");
        return text.length() > 500 ? text.substring(0, 500) : text;
    }

    private SshConnectionTarget target(EnvironmentView environment) {
        return target(environment, null, null);
    }

    private SshConnectionTarget target(EnvironmentView environment, EnvironmentTaskInput input, UUID taskId) {
        CredentialService.SshRuntimeCredential credential;
        if (environment.credentialId() != null) {
            credential = credentialService.sshRuntimeCredential(
                    environment.credentialId(),
                    environment.projectId()
            );
        } else if (input != null && input.target() != null && input.target().temporaryCredentialPayloadId() != null) {
            TaskSecretPayloadService.SshPrecheckCredential temporaryCredential = taskSecretPayloadService.requireSshPrecheckCredential(
                    input.target().temporaryCredentialPayloadId(),
                    input.projectId(),
                    taskId,
                    input.target().temporaryCredentialSha256()
            );
            credential = new CredentialService.SshRuntimeCredential(
                    input.target().temporaryCredentialPayloadId(),
                    temporaryCredential.kind(),
                    temporaryCredential.username(),
                    temporaryCredential.password(),
                    temporaryCredential.privateKey(),
                    temporaryCredential.passphrase()
            );
        } else {
            throw new TaskExecutionException(TaskErrorCode.INPUT_INVALID, "SSH 凭据引用不存在", null);
        }
        return new SshConnectionTarget(
                environment.id(),
                environment.host(),
                environment.sshPort(),
                environment.username(),
                environment.workingDirectory(),
                new SshRuntimeCredential(
                        credential.kind(),
                        credential.username(),
                        credential.password(),
                        credential.privateKey(),
                        credential.passphrase()
                )
        );
    }

    private String probeCommand(String workingDirectory) {
        StringBuilder command = new StringBuilder();
        command.append("RVPORT_WORKDIR=");
        command.append(shellQuote(workingDirectory == null ? "" : workingDirectory));
        command.append("; ");
        command.append("printf 'RVPORT_PROBE=ok\\n'; ");
        command.append("printf 'KERNEL_NAME=%s\\n' \"$(uname -s 2>/dev/null || true)\"; ");
        command.append("printf 'KERNEL_VERSION=%s\\n' \"$(uname -r 2>/dev/null || true)\"; ");
        command.append("printf 'MACHINE_ARCH=%s\\n' \"$(uname -m 2>/dev/null || true)\"; ");
        command.append("printf 'REMOTE_USER=%s\\n' \"$(id -un 2>/dev/null || whoami 2>/dev/null || true)\"; ");
        command.append("printf 'REMOTE_PWD_ACCESSIBLE=%s\\n' \"$(pwd >/dev/null 2>&1 && printf true || printf false)\"; ");
        command.append("if [ -n \"$RVPORT_WORKDIR\" ]; then ");
        command.append("[ -d \"$RVPORT_WORKDIR\" ] && printf 'WORKDIR_EXISTS=true\\n' || printf 'WORKDIR_EXISTS=false\\n'; ");
        command.append("[ -r \"$RVPORT_WORKDIR\" ] && printf 'WORKDIR_READABLE=true\\n' || printf 'WORKDIR_READABLE=false\\n'; ");
        command.append("[ -w \"$RVPORT_WORKDIR\" ] && printf 'WORKDIR_WRITABLE=true\\n' || printf 'WORKDIR_WRITABLE=false\\n'; ");
        command.append("fi; ");
        command.append("for tool in sh bash git gcc g++ make cmake python3 java mvn; do ");
        command.append("if command -v \"$tool\" >/dev/null 2>&1; then printf 'TOOL_%s_PRESENT=true\\n' \"$tool\"; ");
        command.append("else printf 'TOOL_%s_PRESENT=false\\n' \"$tool\"; fi; done");
        return command.toString();
    }

    private String checkCommand(EnvironmentTaskInput input, RuntimeEnvironment runtime) {
        String workdir = input.workingDirectory() == null || input.workingDirectory().isBlank()
                ? runtime.environment().workingDirectory()
                : input.workingDirectory();
        StringBuilder command = new StringBuilder(probeCommand(workdir));
        command.append("; printf 'RVPORT_CHECK=ok\\n'; ");
        command.append("printf 'CHECK_ITEMS=%s\\n' ").append(shellQuote(String.join(",", defaultList(input.checkItems(),
                List.of("CONNECTION", "BASIC_TOOLS", "WORKING_DIRECTORY", "PERMISSIONS"))))).append("; ");
        command.append("printf 'OS_NAME=%s\\n' \"$(. /etc/os-release >/dev/null 2>&1 && printf '%s' \"$NAME\" || uname -s 2>/dev/null || true)\"; ");
        command.append("printf 'OS_VERSION=%s\\n' \"$(. /etc/os-release >/dev/null 2>&1 && printf '%s' \"$VERSION_ID\" || true)\"; ");
        command.append("pkg='unknown'; for p in apt dnf yum pacman zypper apk; do command -v \"$p\" >/dev/null 2>&1 && pkg=\"$p\" && break; done; printf 'PACKAGE_MANAGER=%s\\n' \"$pkg\"; ");
        command.append("for tool in sh bash git gcc g++ make cmake python3 java javac mvn; do if command -v \"$tool\" >/dev/null 2>&1; then v=$($tool --version 2>/dev/null | head -n 1 | tr '=' ' '); printf 'TOOL_VERSION_%s=%s\\n' \"$tool\" \"$v\"; fi; done; ");
        command.append("printf 'PERMISSION_TEMP_WRITABLE=%s\\n' \"$(tmp=${RVPORT_WORKDIR:-.}/.rvport-write-test-$$; touch \"$tmp\" >/dev/null 2>&1 && rm -f \"$tmp\" >/dev/null 2>&1 && printf true || printf false)\"");
        return command.toString();
    }

    private String collectCommand(List<String> collectScopes, boolean collectRepositoryEvidence, String environmentRole) {
        StringBuilder command = new StringBuilder();
        command.append("printf 'RVPORT_COLLECT=ok\\n'; ");
        command.append("printf 'COLLECT_SCOPES=%s\\n' ").append(shellQuote(String.join(",", defaultList(collectScopes, List.of(
                "OS", "PACKAGE_MANAGER", "REPOSITORIES", "INSTALLED_PACKAGES", "TOOL_VERSIONS"))))).append("; ");
        command.append("collect_repo=").append(collectRepositoryEvidence ? "true" : "false").append("; ");
        command.append("environment_role=").append(shellQuote(environmentRole == null ? "" : environmentRole)).append("; ");
        command.append("ry_dpkg_bulk=false; ");
        command.append("ry_tool_present(){ t=\"$1\"; if command -v \"$t\" >/dev/null 2>&1; then printf 'SCANNER_TOOL=%s|true\\n' \"$t\"; else printf 'SCANNER_TOOL=%s|false\\n' \"$t\"; fi; }; ");
        command.append("ry_install_packages(){ reason=\"$1\"; shift; pkgs=\"\"; for p in \"$@\"; do case \" $pkgs \" in *\" $p \"*) ;; *) pkgs=\"$pkgs $p\";; esac; done; pkgs=$(printf '%s' \"$pkgs\" | sed 's/^ *//;s/ *$//'); [ -z \"$pkgs\" ] && return 0; ");
        command.append("if command -v dnf >/dev/null 2>&1; then printf 'SCANNER_INSTALL_ATTEMPT=%s|dnf|%s\\n' \"$reason\" \"$pkgs\"; if dnf --setopt=timeout=5 --setopt=retries=0 --setopt=skip_if_unavailable=True install -y $pkgs >/tmp/rvport-scanner-install.log 2>&1; then printf 'SCANNER_INSTALL_RESULT=%s|SUCCESS|dnf|%s\\n' \"$reason\" \"$pkgs\"; else printf 'SCANNER_INSTALL_RESULT=%s|FAILED|dnf|%s|%s\\n' \"$reason\" \"$pkgs\" \"$(tr '\\n' ' ' </tmp/rvport-scanner-install.log | head -c 300)\"; printf 'PARSE_WARNING=scanner tool auto install failed: %s via dnf\\n' \"$pkgs\"; fi; rm -f /tmp/rvport-scanner-install.log; ");
        command.append("elif command -v yum >/dev/null 2>&1; then printf 'SCANNER_INSTALL_ATTEMPT=%s|yum|%s\\n' \"$reason\" \"$pkgs\"; if yum --setopt=timeout=5 --setopt=retries=0 --setopt=skip_if_unavailable=True install -y $pkgs >/tmp/rvport-scanner-install.log 2>&1; then printf 'SCANNER_INSTALL_RESULT=%s|SUCCESS|yum|%s\\n' \"$reason\" \"$pkgs\"; else printf 'SCANNER_INSTALL_RESULT=%s|FAILED|yum|%s|%s\\n' \"$reason\" \"$pkgs\" \"$(tr '\\n' ' ' </tmp/rvport-scanner-install.log | head -c 300)\"; printf 'PARSE_WARNING=scanner tool auto install failed: %s via yum\\n' \"$pkgs\"; fi; rm -f /tmp/rvport-scanner-install.log; ");
        command.append("elif command -v apt-get >/dev/null 2>&1; then printf 'SCANNER_INSTALL_ATTEMPT=%s|apt-get|%s\\n' \"$reason\" \"$pkgs\"; if DEBIAN_FRONTEND=noninteractive apt-get install -y $pkgs >/tmp/rvport-scanner-install.log 2>&1; then printf 'SCANNER_INSTALL_RESULT=%s|SUCCESS|apt-get|%s\\n' \"$reason\" \"$pkgs\"; else printf 'SCANNER_INSTALL_RESULT=%s|FAILED|apt-get|%s|%s\\n' \"$reason\" \"$pkgs\" \"$(tr '\\n' ' ' </tmp/rvport-scanner-install.log | head -c 300)\"; printf 'PARSE_WARNING=scanner tool auto install failed: %s via apt-get\\n' \"$pkgs\"; fi; rm -f /tmp/rvport-scanner-install.log; ");
        command.append("else printf 'SCANNER_INSTALL_RESULT=%s|SKIPPED|unsupported-package-manager|%s\\n' \"$reason\" \"$pkgs\"; printf 'PARSE_WARNING=scanner tool auto install skipped: unsupported package manager for %s\\n' \"$pkgs\"; fi; }; ");
        command.append("ry_prepare_scanner_tools(){ pkgs=''; command -v find >/dev/null 2>&1 || pkgs=\"$pkgs findutils\"; if ! command -v readelf >/dev/null 2>&1 || ! command -v objdump >/dev/null 2>&1; then pkgs=\"$pkgs binutils\"; fi; if [ \"$environment_role\" = SOURCE_X86 ]; then command -v strace >/dev/null 2>&1 || pkgs=\"$pkgs strace\"; command -v bear >/dev/null 2>&1 || pkgs=\"$pkgs bear\"; fi; ry_install_packages \"environment-collect-$environment_role\" $pkgs; ");
        command.append("for t in find readelf objdump rpm dpkg-query; do ry_tool_present \"$t\"; command -v \"$t\" >/dev/null 2>&1 || printf 'PARSE_WARNING=scanner tool missing: %s affects environment collection\\n' \"$t\"; done; if [ \"$environment_role\" = SOURCE_X86 ]; then for t in strace bear; do ry_tool_present \"$t\"; command -v \"$t\" >/dev/null 2>&1 || printf 'PARSE_WARNING=scanner tool missing: %s affects source build observation\\n' \"$t\"; done; fi; }; ");
        command.append("ry_owner(){ f=\"$1\"; ");
        command.append("if command -v rpm >/dev/null 2>&1; then o=$(rpm -qf --qf '%{NAME}|%{VERSION}-%{RELEASE}|%{ARCH}' \"$f\" 2>/dev/null || true); [ -n \"$o\" ] && [ \"${o#*is not owned}\" = \"$o\" ] && printf 'PROVIDER=%s|%s|rpm\\n' \"$f\" \"$o\" && return 0; ");
        command.append("elif command -v dpkg-query >/dev/null 2>&1; then case \"$f\" in /lib/*|/lib64/*|/usr/lib/*|/usr/lib64/*|/usr/local/lib/*) [ \"$ry_dpkg_bulk\" = true ] && return 0;; esac; p=$(dpkg-query -S \"$f\" 2>/dev/null | head -n 1 | cut -d: -f1 || true); [ -n \"$p\" ] && v=$(dpkg-query -W -f='${Version}|${Architecture}' \"$p\" 2>/dev/null || true) && printf 'PROVIDER=%s|%s|%s|dpkg\\n' \"$f\" \"$p\" \"$v\" && return 0; fi; ");
        command.append("printf 'PARSE_WARNING=provider scanner unavailable or no owner for %s\\n' \"$(basename \"$f\" | tr '=' ' ')\"; }; ");
        command.append("ry_dpkg_library_providers(){ command -v dpkg-query >/dev/null 2>&1 || return 0; ry_dpkg_bulk=true; ");
        command.append("for pat in '/lib/*.so*' '/lib/*/*.so*' '/lib/*/*/*.so*' '/lib/*/*/*/*.so*' '/lib64/*.so*' '/lib64/*/*.so*' '/lib64/*/*/*.so*' '/lib64/*/*/*/*.so*' '/usr/lib/*.so*' '/usr/lib/*/*.so*' '/usr/lib/*/*/*.so*' '/usr/lib/*/*/*/*.so*' '/usr/lib64/*.so*' '/usr/lib64/*/*.so*' '/usr/lib64/*/*/*.so*' '/usr/lib64/*/*/*/*.so*' '/usr/local/lib/*.so*' '/usr/local/lib/*/*.so*' '/usr/local/lib/*/*/*.so*' '/usr/local/lib/*/*/*/*.so*'; do dpkg-query -S \"$pat\" 2>/dev/null || true; done | sort -u | while IFS= read -r line; do pkg=${line%%:*}; path=${line#*: }; [ -z \"$pkg\" ] && continue; [ \"$path\" = \"$line\" ] && continue; printf 'PROVIDER=%s|%s|||dpkg\\n' \"$path\" \"$pkg\"; done; }; ");
        command.append("ry_tool_owner(){ t=\"$1\"; p=$(command -v \"$t\" 2>/dev/null || true); [ -z \"$p\" ] && return 0; real=$(readlink -f \"$p\" 2>/dev/null || printf '%s' \"$p\"); ");
        command.append("if command -v rpm >/dev/null 2>&1; then o=$(rpm -qf --qf '%{NAME}|%{VERSION}-%{RELEASE}|%{ARCH}' \"$real\" 2>/dev/null || true); [ -n \"$o\" ] && [ \"${o#*is not owned}\" = \"$o\" ] && printf 'TOOL_PROVIDER=%s|%s|%s|rpm\\n' \"$t\" \"$real\" \"$o\" && return 0; ");
        command.append("elif command -v dpkg-query >/dev/null 2>&1; then pkg=$(dpkg-query -S \"$real\" 2>/dev/null | head -n 1 | cut -d: -f1 || true); [ -n \"$pkg\" ] && v=$(dpkg-query -W -f='${Version}|${Architecture}' \"$pkg\" 2>/dev/null || true) && printf 'TOOL_PROVIDER=%s|%s|%s|%s|dpkg\\n' \"$t\" \"$real\" \"$pkg\" \"$v\" && return 0; fi; ");
        command.append("printf 'TOOL_PROVIDER=%s|%s||||none\\n' \"$t\" \"$real\"; printf 'PARSE_WARNING=tool provider scanner unavailable or no owner for %s\\n' \"$t\"; }; ");
        command.append("ry_timeout(){ if command -v timeout >/dev/null 2>&1; then timeout 5s \"$@\"; else \"$@\"; fi; }; ");
        command.append("ry_soname(){ f=\"$1\"; tmp=$(mktemp 2>/dev/null || printf '/tmp/rvport-elf-$$'); ");
        command.append("if command -v readelf >/dev/null 2>&1; then ry_timeout readelf -d \"$f\" >\"$tmp\" 2>/dev/null && awk '/\\(SONAME\\)/{gsub(/[][]/,\"\",$NF); print $NF; exit}' \"$tmp\"; ");
        command.append("elif command -v objdump >/dev/null 2>&1; then ry_timeout objdump -p \"$f\" >\"$tmp\" 2>/dev/null && awk '/SONAME/{print $2; exit}' \"$tmp\"; fi; rm -f \"$tmp\"; }; ");
        command.append("ry_needed(){ f=\"$1\"; tmp=$(mktemp 2>/dev/null || printf '/tmp/rvport-elf-$$'); ");
        command.append("if command -v readelf >/dev/null 2>&1; then ry_timeout readelf -d \"$f\" >\"$tmp\" 2>/dev/null && awk '/\\(NEEDED\\)/{gsub(/[][]/,\"\",$NF); print $NF}' \"$tmp\" | paste -sd, -; ");
        command.append("elif command -v objdump >/dev/null 2>&1; then ry_timeout objdump -p \"$f\" >\"$tmp\" 2>/dev/null && awk '/NEEDED/{print $2}' \"$tmp\" | paste -sd, -; fi; rm -f \"$tmp\"; }; ");
        command.append("ry_elf(){ f=\"$1\"; scanner=''; soname=''; needed=''; machine=''; class=''; ");
        command.append("if command -v readelf >/dev/null 2>&1; then scanner='readelf'; soname=$(ry_soname \"$f\"); needed=$(ry_needed \"$f\"); tmp=$(mktemp 2>/dev/null || printf '/tmp/rvport-elfh-$$'); if ry_timeout readelf -h \"$f\" >\"$tmp\" 2>/dev/null; then machine=$(awk -F: '/Machine:/{gsub(/^ +/,\"\",$2); print $2; exit}' \"$tmp\"); class=$(awk -F: '/Class:/{gsub(/^ +/,\"\",$2); print $2; exit}' \"$tmp\"); fi; rm -f \"$tmp\"; ");
        command.append("elif command -v objdump >/dev/null 2>&1; then scanner='objdump'; soname=$(ry_soname \"$f\"); needed=$(ry_needed \"$f\"); hdr=$(ry_timeout file -b \"$f\" 2>/dev/null || true); class=$(printf '%s' \"$hdr\" | awk -F, '{gsub(/^ +/,\"\",$1); print $1}'); machine=$(printf '%s' \"$hdr\" | awk -F, '{gsub(/^ +/,\"\",$2); print $2}'); ");
        command.append("else printf 'PARSE_WARNING=elf metadata scanner unavailable\\n'; return 0; fi; ");
        command.append("[ -n \"$soname$needed$machine$class\" ] && printf 'ELF=%s|%s|%s|%s|%s|%s\\n' \"$f\" \"$(printf '%s' \"$soname\" | tr '|' ' ')\" \"$(printf '%s' \"$needed\" | tr '|' ' ')\" \"$(printf '%s' \"$machine\" | tr '|' ' ')\" \"$(printf '%s' \"$class\" | tr '|' ' ')\" \"$scanner\"; }; ");
        command.append("ry_emit_library(){ f=\"$1\"; [ -e \"$f\" ] || return 0; [ -f \"$f\" ] || [ -L \"$f\" ] || return 0; b=$(basename \"$f\" | tr '=' ' '); printf 'LIBRARY=%s|%s\\n' \"$b\" \"$f\"; [ \"$environment_role\" = TARGET_RISCV ] || { ry_elf \"$f\"; ry_owner \"$f\"; }; }; ");
        command.append("ry_scan_library_dir(){ libdir=\"$1\"; [ -d \"$libdir\" ] || return 0; if command -v find >/dev/null 2>&1; then find -L \"$libdir\" -maxdepth 4 \\( -type f -o -type l \\) -name '*.so*' 2>/dev/null | while IFS= read -r f; do ry_emit_library \"$f\"; done; else printf 'PARSE_WARNING=find unavailable; using fallback library scan for %s\\n' \"$libdir\"; for f in \"$libdir\"/*.so* \"$libdir\"/*/*.so* \"$libdir\"/*/*/*.so* \"$libdir\"/*/*/*/*.so* \"$libdir\"/*/*/*/*/*.so*; do ry_emit_library \"$f\"; done; fi; }; ");
        command.append("ry_emit_native(){ f=\"$1\"; [ -e \"$f\" ] || return 0; [ -f \"$f\" ] || [ -L \"$f\" ] || return 0; b=$(basename \"$f\" | tr '=' ' '); printf 'NATIVE_FILE=%s|%s\\n' \"$b\" \"$f\"; [ \"$environment_role\" = TARGET_RISCV ] || { ry_elf \"$f\"; ry_owner \"$f\"; }; }; ");
        command.append("ry_scan_native_dir(){ ndir=\"$1\"; [ -d \"$ndir\" ] || return 0; if command -v find >/dev/null 2>&1; then find -L \"$ndir\" -maxdepth 3 \\( -type f -o -type l \\) -name '*.so*' 2>/dev/null | while IFS= read -r f; do ry_emit_native \"$f\"; done; else printf 'PARSE_WARNING=find unavailable; using fallback native scan for %s\\n' \"$ndir\"; for f in \"$ndir\"/*.so* \"$ndir\"/*/*.so* \"$ndir\"/*/*/*.so* \"$ndir\"/*/*/*/*.so*; do ry_emit_native \"$f\"; done; fi; }; ");
        command.append("ry_repo_provide(){ q=\"$1\"; kind=\"$2\"; [ -z \"$q\" ] && return 0; pat=\"$q\"; [ \"$kind\" = PATH ] && pat=\"*/$q\"; ");
        command.append("if command -v dnf >/dev/null 2>&1; then err=$(mktemp 2>/dev/null || printf '/tmp/rvport-provide-err-$$'); runner=''; command -v timeout >/dev/null 2>&1 && runner='timeout 60s'; $runner dnf --disablerepo='*source' --disablerepo='debuginfo' --disablerepo='*-debuginfo' --setopt=timeout=5 --setopt=retries=0 --setopt=skip_if_unavailable=True repoquery --whatprovides \"$pat\" --qf \"REPO_PROVIDE=%{name}|%{version}-%{release}|%{arch}|%{location}|dnf|$pat|$kind|$q\" 2>\"$err\"; [ -s \"$err\" ] && printf 'PARSE_WARNING=repository provides scanner: %s\\n' \"$(tr '\\n' ' ' < \"$err\" | head -c 300)\"; rm -f \"$err\"; ");
        command.append("elif command -v yum >/dev/null 2>&1; then err=$(mktemp 2>/dev/null || printf '/tmp/rvport-provide-err-$$'); runner=''; command -v timeout >/dev/null 2>&1 && runner='timeout 60s'; $runner yum --disablerepo='*source' --disablerepo='debuginfo' --disablerepo='*-debuginfo' --setopt=timeout=5 --setopt=retries=0 --setopt=skip_if_unavailable=True repoquery --whatprovides \"$pat\" --qf \"REPO_PROVIDE=%{name}|%{version}-%{release}|%{arch}|%{location}|yum|$pat|$kind|$q\" 2>\"$err\"; [ -s \"$err\" ] && printf 'PARSE_WARNING=repository provides scanner: %s\\n' \"$(tr '\\n' ' ' < \"$err\" | head -c 300)\"; rm -f \"$err\"; ");
        command.append("elif command -v apt-file >/dev/null 2>&1; then apt-file search \"$q\" 2>/dev/null | sed 's/: /|/' | while IFS='|' read p f; do printf 'REPO_PROVIDE=%s|||%s|apt-file|%s|%s|%s\\n' \"$p\" \"$f\" \"$pat\" \"$kind\" \"$q\"; done; fi; }; ");
        command.append("printf 'OS_NAME=%s\\n' \"$(. /etc/os-release >/dev/null 2>&1 && printf '%s' \"$NAME\" || uname -s 2>/dev/null || true)\"; ");
        command.append("printf 'OS_VERSION=%s\\n' \"$(. /etc/os-release >/dev/null 2>&1 && printf '%s' \"$VERSION_ID\" || true)\"; ");
        command.append("printf 'KERNEL_VERSION=%s\\n' \"$(uname -r 2>/dev/null || true)\"; ");
        command.append("printf 'MACHINE_ARCH=%s\\n' \"$(uname -m 2>/dev/null || true)\"; ");
        command.append("pkg='unknown'; for p in apt dnf yum pacman zypper apk; do command -v \"$p\" >/dev/null 2>&1 && pkg=\"$p\" && break; done; printf 'PACKAGE_MANAGER=%s\\n' \"$pkg\"; ");
        command.append("ry_prepare_scanner_tools; ");
        command.append("if command -v find >/dev/null 2>&1; then printf 'REPO_SOURCE_COUNT=%s\\n' \"$(find /etc/apt/sources.list /etc/apt/sources.list.d /etc/yum.repos.d -type f 2>/dev/null | wc -l | tr -d ' ')\"; else printf 'REPO_SOURCE_COUNT=0\\n'; printf 'PARSE_WARNING=find unavailable; repository source count skipped\\n'; fi; ");
        command.append("for tool in sh bash git gcc g++ cc c++ clang clang++ make cmake ninja meson rpmbuild configure autoconf automake libtool pkg-config ar as ld ranlib strip objcopy objdump readelf python3 java javac mvn; do if command -v \"$tool\" >/dev/null 2>&1; then v=$($tool --version 2>/dev/null | head -n 1 | tr '=' ' '); printf 'TOOL_VERSION_%s=%s\\n' \"$tool\" \"$v\"; ry_tool_owner \"$tool\"; fi; done; ");
        command.append("if [ \"$pkg\" = apt ] && command -v dpkg-query >/dev/null 2>&1; then dpkg-query -W -f='PACKAGE=${binary:Package}|${Version}|${Architecture}\\n' 2>/dev/null; ");
        command.append("elif { [ \"$pkg\" = dnf ] || [ \"$pkg\" = yum ]; } && command -v rpm >/dev/null 2>&1; then rpm -qa --qf 'PACKAGE=%{NAME}|%{VERSION}-%{RELEASE}|%{ARCH}\\n' 2>/dev/null; ");
        command.append("elif command -v rpm >/dev/null 2>&1; then rpm -qa --qf 'PACKAGE=%{NAME}|%{VERSION}-%{RELEASE}|%{ARCH}\\n' 2>/dev/null; ");
        command.append("elif command -v dpkg-query >/dev/null 2>&1; then dpkg-query -W -f='PACKAGE=${binary:Package}|${Version}|${Architecture}\\n' 2>/dev/null; fi; ");
        command.append("ry_dpkg_library_providers; ");
        command.append("for libdir in /lib /lib64 /usr/lib /usr/lib64 /usr/local/lib; do ry_scan_library_dir \"$libdir\"; done; ");
        command.append("for ndir in /opt /usr/local/bin; do ry_scan_native_dir \"$ndir\"; done; ");
        command.append("if [ \"$collect_repo\" = true ]; then if command -v apt-cache >/dev/null 2>&1; then apt-cache pkgnames 2>/dev/null | while read p; do printf 'REPO_PACKAGE=%s|||apt\\n' \"$p\"; done; ");
        command.append("elif command -v dnf >/dev/null 2>&1; then merr=$(mktemp 2>/dev/null || printf '/tmp/rvport-dnf-metadata-err-$$'); runner=''; command -v timeout >/dev/null 2>&1 && runner='timeout 1800s'; if $runner dnf --disablerepo='*source' --disablerepo='debuginfo' --disablerepo='*-debuginfo' --setopt=timeout=5 --setopt=retries=0 --setopt=skip_if_unavailable=True makecache --refresh -q 2>\"$merr\"; then printf 'REPO_METADATA_STATUS=SUCCESS|dnf|makecache --refresh\\n'; else printf 'REPO_METADATA_STATUS=FAILED|dnf|%s\\n' \"$(tr '\\n' ' ' < \"$merr\" | head -c 300)\"; fi; rm -f \"$merr\"; err=$(mktemp 2>/dev/null || printf '/tmp/rvport-dnf-err-$$'); runner=''; command -v timeout >/dev/null 2>&1 && runner='timeout 1800s'; $runner dnf --disablerepo='*source' --disablerepo='debuginfo' --disablerepo='*-debuginfo' --setopt=timeout=5 --setopt=retries=0 --setopt=skip_if_unavailable=True repoquery --available --qf 'REPO_PACKAGE=%{name}|%{version}-%{release}|%{arch}|dnf' 2>\"$err\" | grep '^REPO_PACKAGE='; [ -s \"$err\" ] && printf 'PARSE_WARNING=repository package scanner: %s\\n' \"$(tr '\\n' ' ' < \"$err\" | head -c 300)\"; rm -f \"$err\"; ");
        command.append("elif command -v yum >/dev/null 2>&1; then merr=$(mktemp 2>/dev/null || printf '/tmp/rvport-yum-metadata-err-$$'); runner=''; command -v timeout >/dev/null 2>&1 && runner='timeout 1800s'; if $runner yum --disablerepo='*source' --disablerepo='debuginfo' --disablerepo='*-debuginfo' --setopt=timeout=5 --setopt=retries=0 --setopt=skip_if_unavailable=True makecache -q 2>\"$merr\"; then printf 'REPO_METADATA_STATUS=SUCCESS|yum|makecache\\n'; else printf 'REPO_METADATA_STATUS=FAILED|yum|%s\\n' \"$(tr '\\n' ' ' < \"$merr\" | head -c 300)\"; fi; rm -f \"$merr\"; err=$(mktemp 2>/dev/null || printf '/tmp/rvport-yum-err-$$'); runner=''; command -v timeout >/dev/null 2>&1 && runner='timeout 1800s'; $runner yum --disablerepo='*source' --disablerepo='debuginfo' --disablerepo='*-debuginfo' --setopt=timeout=5 --setopt=retries=0 --setopt=skip_if_unavailable=True repoquery --available --qf 'REPO_PACKAGE=%{name}|%{version}-%{release}|%{arch}|yum' 2>\"$err\" | grep '^REPO_PACKAGE='; [ -s \"$err\" ] && printf 'PARSE_WARNING=repository package scanner: %s\\n' \"$(tr '\\n' ' ' < \"$err\" | head -c 300)\"; rm -f \"$err\"; fi; ");
        command.append("if command -v apt-file >/dev/null 2>&1; then printf 'REPO_METADATA_STATUS=AVAILABLE|apt-file|apt-file cache\\n'; apt-file search --regexp '/[^/]+\\.so(\\..*)?$' 2>/dev/null | sed 's/: /|/' | while IFS='|' read p f; do printf 'REPO_PROVIDE=%s|||%s|apt-file|*.so|PATH|*.so\\n' \"$p\" \"$f\"; done; ");
        command.append("else printf 'PARSE_WARNING=repository provides scanner unavailable\\n'; fi; else printf 'REPO_METADATA_STATUS=SKIPPED|source|repository evidence only collected for target environment\\n'; fi");
        return command.toString();
    }

    private String scriptCommand(EnvironmentTaskInput input, RuntimeEnvironment runtime) {
        if ("BUILTIN_SCRIPT".equals(input.scriptType())) {
            String name = input.parameters() == null ? "" : input.parameters().getOrDefault("name", "");
            if ("PRINT_WORKDIR".equals(name)) {
                return "pwd";
            }
            if ("ENV_INFO".equals(name)) {
                return probeCommand(runtime.workingDirectory(input));
            }
        }
        if ("CUSTOM_BASH".equals(input.scriptType())) {
            return customBashCommand(runtime.workingDirectory(input));
        }
        throw new TaskExecutionException(TaskErrorCode.UNSUPPORTED_OPERATION, "脚本类型暂不支持执行", null);
    }

    private String customBashCommand(String workingDirectory) {
        StringBuilder command = new StringBuilder();
        command.append("tmp=$(mktemp \"${TMPDIR:-/tmp}/rvport-custom-bash.XXXXXX\") || exit 120; ");
        command.append("cleanup(){ rm -f \"$tmp\"; }; trap cleanup EXIT INT TERM; ");
        command.append("umask 077; cat > \"$tmp\" || exit 121; chmod 700 \"$tmp\" || exit 122; ");
        if (workingDirectory != null && !workingDirectory.isBlank()) {
            command.append("cd ").append(shellQuote(workingDirectory)).append(" || exit 123; ");
        }
        command.append("if command -v bash >/dev/null 2>&1; then bash \"$tmp\"; else sh \"$tmp\"; fi");
        return command.toString();
    }

    private Map<String, Object> parseProbe(SshCommandResult result) {
        Map<String, String> values = keyValues(result.stdout());
        return probeSummary(values, result.duration());
    }

    private Map<String, Object> parseCheck(SshCommandResult result) {
        Map<String, String> values = keyValues(result.stdout());
        Map<String, Object> summary = probeSummary(values, result.duration());
        summary.put("snapshotKind", "BASIC_CHECK");
        summary.put("checkVersion", TOOL_VERSION);
        summary.put("check", values.get("RVPORT_CHECK"));
        summary.put("checkItems", splitCsv(values.get("CHECK_ITEMS")));
        summary.put("osName", values.getOrDefault("OS_NAME", ""));
        summary.put("osVersion", values.getOrDefault("OS_VERSION", ""));
        summary.put("arch", values.getOrDefault("MACHINE_ARCH", ""));
        summary.put("packageManager", values.getOrDefault("PACKAGE_MANAGER", ""));
        Map<String, String> tools = new LinkedHashMap<>();
        values.forEach((key, value) -> {
            if (key.startsWith("TOOL_VERSION_")) {
                tools.put(key.substring("TOOL_VERSION_".length()).toLowerCase(), value);
            }
        });
        summary.put("toolVersions", tools);
        Map<String, Object> permissions = Map.of("temporaryWritable", booleanValue(values.get("PERMISSION_TEMP_WRITABLE")));
        summary.put("permissions", permissions);
        summary.put("checkResults", Map.of(
                "connection", "ok".equals(values.get("RVPORT_PROBE")),
                "workingDirectory", summary.get("workingDirectory"),
                "basicTools", summary.get("basicTools"),
                "permissions", permissions
        ));
        summary.put("parseWarnings", result.stdout().lines()
                .filter(line -> line.startsWith("PARSE_WARNING="))
                .map(line -> line.substring("PARSE_WARNING=".length()))
                .limit(20)
                .toList());
        return summary;
    }

    private Map<String, Object> parseCollect(SshCommandResult result) {
        Map<String, String> values = keyValues(result.stdout());
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("collectVersion", TOOL_VERSION);
        summary.put("collect", values.get("RVPORT_COLLECT"));
        summary.put("collectScopes", splitCsv(values.get("COLLECT_SCOPES")));
        summary.put("osName", values.getOrDefault("OS_NAME", ""));
        summary.put("osVersion", values.getOrDefault("OS_VERSION", ""));
        summary.put("kernelVersion", values.getOrDefault("KERNEL_VERSION", ""));
        summary.put("arch", values.getOrDefault("MACHINE_ARCH", ""));
        summary.put("packageManager", values.getOrDefault("PACKAGE_MANAGER", ""));
        List<Map<String, String>> repositoryMetadata = pipeRecords(result.stdout(), "REPO_METADATA_STATUS=", List.of("status", "scanner", "detail"));
        summary.put("repositories", Map.of(
                "sourceFileCount", intValue(values.get("REPO_SOURCE_COUNT")),
                "metadata", repositoryMetadata,
                "metadataComplete", repositoryMetadata.stream().anyMatch(item -> "SUCCESS".equals(item.get("status")) || "AVAILABLE".equals(item.get("status")))
        ));
        Map<String, String> tools = new LinkedHashMap<>();
        values.forEach((key, value) -> {
            if (key.startsWith("TOOL_VERSION_")) {
                tools.put(key.substring("TOOL_VERSION_".length()).toLowerCase(), value);
            }
        });
        summary.put("toolVersions", tools);
        summary.put("toolProviders", pipeRecords(result.stdout(), "TOOL_PROVIDER=", List.of("name", "path", "ownerPackage", "ownerVersion", "ownerArch", "scanner")));
        summary.put("scannerTools", pipeRecords(result.stdout(), "SCANNER_TOOL=", List.of("name", "available")));
        summary.put("scannerInstallAttempts", pipeRecords(result.stdout(), "SCANNER_INSTALL_ATTEMPT=", List.of("reason", "packageManager", "packages")));
        summary.put("scannerInstallResults", pipeRecords(result.stdout(), "SCANNER_INSTALL_RESULT=", List.of("reason", "status", "packageManager", "packages", "detail")));
        summary.put("packages", packages(result.stdout()));
        List<Map<String, String>> providers = pipeRecords(result.stdout(), "PROVIDER=", List.of("path", "ownerPackage", "ownerVersion", "ownerArch", "scanner"));
        List<Map<String, String>> elfMetadata = pipeRecords(result.stdout(), "ELF=", List.of("path", "elfSoname", "elfNeeded", "elfMachine", "elfClass", "elfScanner"));
        summary.put("providers", providers);
        summary.put("elfMetadata", elfMetadata);
        summary.put("libraries", enrichFileRecords(pipeRecords(result.stdout(), "LIBRARY=", List.of("name", "path")), providers, elfMetadata, values.getOrDefault("MACHINE_ARCH", "")));
        summary.put("nativeFiles", enrichFileRecords(pipeRecords(result.stdout(), "NATIVE_FILE=", List.of("name", "path")), providers, elfMetadata, values.getOrDefault("MACHINE_ARCH", "")));
        summary.put("repositoryPackages", pipeRecords(result.stdout(), "REPO_PACKAGE=", List.of("name", "version", "arch", "packageManager")));
        summary.put("repositoryProvides", pipeRecords(result.stdout(), "REPO_PROVIDE=", List.of("packageName", "packageVersion", "packageArch", "path", "scanner", "queryPattern", "provideKind", "queryValue")));
        summary.put("parseWarnings", result.stdout().lines()
                .filter(line -> line.startsWith("PARSE_WARNING="))
                .map(line -> line.substring("PARSE_WARNING=".length()))
                .limit(20)
                .toList());
        summary.put("durationMs", result.duration().toMillis());
        return summary;
    }

    private List<Map<String, String>> enrichFileRecords(List<Map<String, String>> records, List<Map<String, String>> providers, List<Map<String, String>> elfMetadata, String arch) {
        Map<String, Map<String, String>> providerByPath = new LinkedHashMap<>();
        for (Map<String, String> provider : providers) {
            providerByPath.put(provider.get("path"), provider);
        }
        Map<String, Map<String, String>> elfByPath = new LinkedHashMap<>();
        for (Map<String, String> elf : elfMetadata) {
            elfByPath.put(elf.get("path"), elf);
        }
        return records.stream().map(item -> {
            Map<String, String> enriched = new LinkedHashMap<>(item);
            Map<String, String> provider = providerByPath.get(item.get("path"));
            if (provider != null) {
                enriched.put("ownerPackage", provider.get("ownerPackage"));
                enriched.put("ownerVersion", provider.get("ownerVersion"));
                enriched.put("ownerArch", provider.get("ownerArch"));
                enriched.put("providerScanner", provider.get("scanner"));
            }
            Map<String, String> elf = elfByPath.get(item.get("path"));
            if (elf != null) {
                enriched.put("elfSoname", elf.get("elfSoname"));
                enriched.put("elfNeeded", elf.get("elfNeeded"));
                enriched.put("elfMachine", elf.get("elfMachine"));
                enriched.put("elfClass", elf.get("elfClass"));
                enriched.put("elfScanner", elf.get("elfScanner"));
            }
            enriched.putAll(normalizedCandidates(item.get("name"), item.get("path"), provider == null ? null : provider.get("ownerPackage"), arch));
            enriched.putAll(capabilities(enriched));
            return enriched;
        }).toList();
    }

    private Map<String, String> capabilities(Map<String, String> item) {
        Map<String, String> metadata = new LinkedHashMap<>();
        java.util.LinkedHashSet<String> provides = new java.util.LinkedHashSet<>();
        addCapability(provides, item.get("elfSoname"));
        addCapability(provides, item.get("name"));
        addCapability(provides, item.get("ownerPackage"));
        if (!provides.isEmpty()) {
            metadata.put("providesCapabilities", String.join(",", provides));
        }
        String needed = item.get("elfNeeded");
        if (needed != null && !needed.isBlank()) {
            metadata.put("requiredCapabilities", needed);
        }
        return metadata;
    }

    private void addCapability(java.util.Set<String> capabilities, String value) {
        String normalized = fileName(value);
        if (normalized != null && !normalized.isBlank()) {
            capabilities.add(normalized.trim());
        }
    }

    private Map<String, String> normalizedCandidates(String name, String path, String ownerPackage, String arch) {
        Map<String, String> metadata = new LinkedHashMap<>();
        String normalizedName = stripArchTokens(fileName(name));
        String normalizedPackage = stripArchTokens(ownerPackage);
        metadata.put("originalName", name == null ? "" : name);
        metadata.put("normalizedName", normalizedName);
        metadata.put("queryPattern", normalizedName.isBlank() ? "" : "*/" + normalizedName);
        metadata.put("normalizedPackage", normalizedPackage);
        metadata.put("targetPackageCandidate", targetArchCandidate(normalizedPackage, arch));
        metadata.put("normalizationSource", "arch-token-strip");
        if (path != null && !path.isBlank()) {
            metadata.put("pathContainsArchToken", Boolean.toString(!path.equals(stripArchTokens(path))));
        }
        return metadata;
    }

    private String targetArchCandidate(String value, String arch) {
        if (value == null || value.isBlank() || arch == null || arch.isBlank()) {
            return value == null ? "" : value;
        }
        String token = arch.toLowerCase().contains("riscv") ? "riscv64" : arch.toLowerCase();
        return value + "-" + token;
    }

    private String stripArchTokens(String value) {
        if (value == null) {
            return "";
        }
        return value
                .replaceAll("(?i)(^|[-_./])x86_64($|[-_./])", "$1")
                .replaceAll("(?i)(^|[-_./])amd64($|[-_./])", "$1")
                .replaceAll("(?i)(^|[-_./])x64($|[-_./])", "$1")
                .replaceAll("(?i)(^|[-_./])riscv64($|[-_./])", "$1")
                .replaceAll("[-_.]{2,}", "-")
                .replaceAll("^-|-$", "")
                .trim();
    }

    private String fileName(String value) {
        if (value == null) {
            return "";
        }
        int index = Math.max(value.lastIndexOf('/'), value.lastIndexOf('\\'));
        return index >= 0 ? value.substring(index + 1) : value;
    }

    private Map<String, String> keyValues(String stdout) {
        Map<String, String> values = new LinkedHashMap<>();
        for (String line : stdout.split("\\R")) {
            int index = line.indexOf('=');
            if (index > 0) {
                values.put(line.substring(0, index), line.substring(index + 1));
            }
        }
        return values;
    }

    private Map<String, Object> probeSummary(Map<String, String> values, Duration duration) {
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("probeVersion", TOOL_VERSION);
        summary.put("probe", values.get("RVPORT_PROBE"));
        summary.put("kernelName", values.getOrDefault("KERNEL_NAME", ""));
        summary.put("kernelVersion", values.getOrDefault("KERNEL_VERSION", ""));
        summary.put("machineArch", values.getOrDefault("MACHINE_ARCH", ""));
        summary.put("remoteUser", values.getOrDefault("REMOTE_USER", ""));
        summary.put("durationMs", duration.toMillis());
        summary.put("workingDirectory", Map.of(
                "configured", values.containsKey("WORKDIR_EXISTS"),
                "exists", booleanValue(values.get("WORKDIR_EXISTS")),
                "readable", booleanValue(values.get("WORKDIR_READABLE")),
                "writable", booleanValue(values.get("WORKDIR_WRITABLE"))
        ));
        Map<String, Boolean> tools = new LinkedHashMap<>();
        values.forEach((key, value) -> {
            if (key.startsWith("TOOL_") && key.endsWith("_PRESENT")) {
                String tool = key.substring("TOOL_".length(), key.length() - "_PRESENT".length()).toLowerCase();
                tools.put(tool, booleanValue(value));
            }
        });
        summary.put("basicTools", tools);
        return summary;
    }

    @SuppressWarnings("unchecked")
    private void createCollectedComponents(UUID snapshotId, EnvironmentView environment, Map<String, Object> summary) {
        UUID projectId = environment.projectId();
        String arch = stringValue(summary.get("arch"));
        createToolComponents(snapshotId, projectId, arch, mapValue(summary.get("toolVersions")),
                (List<Map<String, String>>) summary.getOrDefault("toolProviders", List.of()));
        List<EnvironmentRepository.ComponentInput> components = new java.util.ArrayList<>();
        for (Map<String, String> item : (List<Map<String, String>>) summary.getOrDefault("packages", List.of())) {
            components.add(new EnvironmentRepository.ComponentInput(item.get("name"), item.get("version"),
                    "PACKAGE", item.getOrDefault("arch", arch), null, "INSTALLED_PACKAGE", Map.of()));
        }
        for (Map<String, String> item : (List<Map<String, String>>) summary.getOrDefault("libraries", List.of())) {
            components.add(new EnvironmentRepository.ComponentInput(item.get("name"), null,
                    "LIBRARY", arch, item.get("path"), "INSTALLED_LIBRARY", componentMetadata(item)));
        }
        for (Map<String, String> item : (List<Map<String, String>>) summary.getOrDefault("nativeFiles", List.of())) {
            components.add(new EnvironmentRepository.ComponentInput(item.get("name"), null,
                    "NATIVE_FILE", arch, item.get("path"), "NATIVE_FILE", componentMetadata(item)));
        }
        if ("TARGET_RISCV".equals(environment.role().name())) {
            for (Map<String, String> item : (List<Map<String, String>>) summary.getOrDefault("repositoryPackages", List.of())) {
                components.add(new EnvironmentRepository.ComponentInput(item.get("name"), item.get("version"),
                        "PACKAGE", item.get("arch"), null, "REPOSITORY_PACKAGE", Map.of("packageManager", item.get("packageManager"))));
            }
            for (Map<String, String> item : (List<Map<String, String>>) summary.getOrDefault("repositoryProvides", List.of())) {
                String path = item.get("path");
                String queryValue = item.get("queryValue");
                String name = queryValue == null || queryValue.isBlank()
                        ? path == null ? item.get("packageName") : path.substring(path.lastIndexOf('/') + 1)
                        : queryValue;
                components.add(new EnvironmentRepository.ComponentInput(name, item.get("packageVersion"),
                        "LIBRARY", item.getOrDefault("packageArch", arch), path, "REPOSITORY_PROVIDE", componentMetadata(item)));
            }
        }
        environmentRepository.createComponents(snapshotId, projectId, components);
    }

    private Map<String, String> componentMetadata(Map<String, String> item) {
        Map<String, String> metadata = new LinkedHashMap<>();
        metadata.put("filename", item.get("name"));
        for (String key : List.of("ownerPackage", "ownerVersion", "ownerArch", "providerScanner", "toolPath",
                "installOrigin", "versionText", "versionMajor",
                "originalName",
                "normalizedName", "queryPattern", "normalizedPackage", "targetPackageCandidate",
                "normalizationSource", "pathContainsArchToken", "elfSoname", "elfNeeded", "elfMachine",
                "elfClass", "elfScanner", "providesCapabilities", "requiredCapabilities", "packageName",
                "scanner", "provideKind", "queryValue", "packageVersion", "packageArch")) {
            String value = item.get(key);
            if (value != null && !value.isBlank()) {
                metadata.put(key, value);
            }
        }
        return metadata;
    }

    private void createToolComponents(UUID snapshotId, UUID projectId, String arch, Map<String, ?> toolVersions, List<Map<String, String>> toolProviders) {
        Map<String, Map<String, String>> providerByName = new LinkedHashMap<>();
        for (Map<String, String> provider : toolProviders) {
            providerByName.put(provider.get("name"), provider);
        }
        toolVersions.forEach((name, version) -> {
            Map<String, String> provider = providerByName.getOrDefault(name, Map.of());
            String ownerArch = provider.get("ownerArch");
            String toolPath = provider.get("path");
            String versionText = stringValue(version);
            Map<String, String> item = new LinkedHashMap<>();
            item.put("name", name);
            item.put("toolPath", toolPath);
            item.put("ownerPackage", provider.get("ownerPackage"));
            item.put("ownerVersion", provider.get("ownerVersion"));
            item.put("ownerArch", ownerArch);
            item.put("providerScanner", provider.getOrDefault("scanner", "none"));
            item.put("installOrigin", installOrigin(provider.get("ownerPackage"), toolPath));
            item.put("versionText", versionText);
            item.put("versionMajor", versionMajor(versionText));
            item.putAll(normalizedCandidates(name, toolPath, provider.get("ownerPackage"), arch));
            environmentRepository.createComponent(
                    snapshotId,
                    projectId,
                    name,
                    versionText,
                    "TOOL",
                    ownerArch == null || ownerArch.isBlank() ? arch : ownerArch,
                    toolPath,
                    "TOOL_VERSION",
                    componentMetadata(item)
            );
        });
    }

    private String installOrigin(String ownerPackage, String toolPath) {
        if (ownerPackage != null && !ownerPackage.isBlank()) {
            return "package";
        }
        if (isUnmanagedToolPath(toolPath)) {
            return "unmanaged";
        }
        return "unknown";
    }

    private boolean isUnmanagedToolPath(String toolPath) {
        if (toolPath == null || toolPath.isBlank()) {
            return false;
        }
        String normalized = toolPath.replace('\\', '/');
        return normalized.startsWith("/usr/local/")
                || normalized.startsWith("/opt/")
                || normalized.startsWith("/root/.local/")
                || normalized.matches("^/home/[^/]+/\\.local/.*");
    }

    private String versionMajor(String versionText) {
        Matcher matcher = FIRST_NUMBER.matcher(versionText == null ? "" : versionText);
        return matcher.find() ? matcher.group() : "";
    }

    private Map<String, Object> withSnapshot(Map<String, Object> summary, UUID snapshotId) {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("snapshotId", snapshotId);
        value.put("collectVersion", summary.get("collectVersion"));
        value.put("osName", summary.get("osName"));
        value.put("osVersion", summary.get("osVersion"));
        value.put("kernelVersion", summary.get("kernelVersion"));
        value.put("arch", summary.get("arch"));
        value.put("packageManager", summary.get("packageManager"));
        value.put("collectScopes", summary.get("collectScopes"));
        value.put("repositories", summary.get("repositories"));
        value.put("counts", Map.of(
                "packages", listSize(summary.get("packages")),
                "toolVersions", mapSize(summary.get("toolVersions")),
                "libraries", listSize(summary.get("libraries")),
                "nativeFiles", listSize(summary.get("nativeFiles")),
                "repositoryPackages", listSize(summary.get("repositoryPackages")),
                "repositoryProvides", listSize(summary.get("repositoryProvides")),
                "parseWarnings", listSize(summary.get("parseWarnings")),
                "scannerInstallResults", listSize(summary.get("scannerInstallResults"))
        ));
        value.put("scannerTools", summary.get("scannerTools"));
        value.put("scannerInstallResults", summary.get("scannerInstallResults"));
        return value;
    }

    private Map<String, Object> withBasicSnapshot(Map<String, Object> summary, UUID snapshotId) {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("snapshotId", snapshotId);
        value.put("snapshotKind", summary.get("snapshotKind"));
        value.put("checkVersion", summary.get("checkVersion"));
        value.put("check", summary.get("check"));
        value.put("osName", summary.get("osName"));
        value.put("osVersion", summary.get("osVersion"));
        value.put("kernelVersion", summary.get("kernelVersion"));
        value.put("arch", summary.get("arch"));
        value.put("packageManager", summary.get("packageManager"));
        value.put("remoteUser", summary.get("remoteUser"));
        value.put("checkItems", summary.get("checkItems"));
        value.put("checkResults", summary.get("checkResults"));
        value.put("basicTools", summary.get("basicTools"));
        value.put("toolVersions", summary.get("toolVersions"));
        value.put("workingDirectory", summary.get("workingDirectory"));
        value.put("permissions", summary.get("permissions"));
        value.put("parseWarnings", summary.get("parseWarnings"));
        value.put("durationMs", summary.get("durationMs"));
        return value;
    }

    private int listSize(Object value) {
        return value instanceof List<?> list ? list.size() : 0;
    }

    private int mapSize(Object value) {
        return value instanceof Map<?, ?> map ? map.size() : 0;
    }

    private boolean booleanValue(String value) {
        return Boolean.parseBoolean(value);
    }

    private int intValue(String value) {
        try {
            return value == null || value.isBlank() ? 0 : Integer.parseInt(value.trim());
        } catch (NumberFormatException ex) {
            return 0;
        }
    }

    private List<String> splitCsv(String value) {
        if (value == null || value.isBlank()) {
            return List.of();
        }
        return Arrays.stream(value.split(","))
                .map(String::trim)
                .filter(item -> !item.isEmpty())
                .toList();
    }

    private List<String> defaultList(List<String> requested, List<String> defaults) {
        if (requested == null || requested.isEmpty()) {
            return defaults;
        }
        Set<String> deduped = new LinkedHashSet<>(requested);
        return List.copyOf(deduped);
    }

    private List<Map<String, String>> packages(String stdout) {
        return stdout.lines()
                .filter(line -> line.startsWith("PACKAGE="))
                .map(line -> line.substring("PACKAGE=".length()).split("\\|", -1))
                .map(parts -> Map.of(
                        "name", parts.length > 0 ? parts[0] : "",
                        "version", parts.length > 1 ? parts[1] : "",
                        "arch", parts.length > 2 ? parts[2] : ""
                ))
                .toList();
    }

    private List<Map<String, String>> pipeRecords(String stdout, String prefix, List<String> keys) {
        return stdout.lines()
                .filter(line -> line.startsWith(prefix))
                .map(line -> line.substring(prefix.length()).split("\\|", -1))
                .map(parts -> {
                    Map<String, String> item = new LinkedHashMap<>();
                    for (int i = 0; i < keys.size(); i++) {
                        item.put(keys.get(i), parts.length > i ? parts[i] : "");
                    }
                    return item;
                })
                .toList();
    }

    @SuppressWarnings("unchecked")
    private Map<String, ?> mapValue(Object value) {
        return value instanceof Map<?, ?> map ? (Map<String, ?>) map : Map.of();
    }

    private String stringValue(Object value) {
        return value == null ? "" : value.toString();
    }

    private String shellQuote(String value) {
        return "'" + value.replace("'", "'\"'\"'") + "'";
    }

    private record RuntimeEnvironment(EnvironmentView environment, EnvironmentView jumpHost, boolean persistedEnvironment) {
        String workingDirectory(EnvironmentTaskInput input) {
            return input.workingDirectory() == null || input.workingDirectory().isBlank()
                    ? environment.workingDirectory()
                    : input.workingDirectory();
        }
    }
}
