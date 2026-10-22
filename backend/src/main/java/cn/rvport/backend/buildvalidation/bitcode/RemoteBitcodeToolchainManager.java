package cn.rvport.backend.buildvalidation.bitcode;

import cn.rvport.backend.config.RvPortProperties;
import cn.rvport.backend.environment.runtime.SshClientAdapter;
import cn.rvport.backend.environment.runtime.SshCommandRequest;
import cn.rvport.backend.environment.runtime.SshCommandResult;
import cn.rvport.backend.environment.runtime.SshFileTransferRequest;
import cn.rvport.backend.worker.TaskExecutionContext;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.HexFormat;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.locks.ReentrantLock;
import org.springframework.stereotype.Service;

@Service
public class RemoteBitcodeToolchainManager {

    private static final ConcurrentHashMap<String, ReentrantLock> DEPLOY_LOCKS = new ConcurrentHashMap<>();
    private final SshClientAdapter sshClientAdapter;
    private final RvPortProperties.Bitcode properties;

    public RemoteBitcodeToolchainManager(SshClientAdapter sshClientAdapter, RvPortProperties properties) {
        this.sshClientAdapter = sshClientAdapter;
        this.properties = properties.bitcode();
    }

    public RemoteBitcodeToolchain ensure(BitcodeGenerationRequest request) {
        Path bundle = Path.of(properties.bundlePath()).toAbsolutePath().normalize();
        verifyLocalBundle(bundle);
        String cacheRoot = joinRemote(request.target().workingDirectory(), properties.remoteCacheDirectory());
        String toolchainRoot = joinRemote(cacheRoot, properties.toolchainId());
        String lockKey = request.target().host() + ":" + request.target().port() + ":" + toolchainRoot;
        ReentrantLock localLock = DEPLOY_LOCKS.computeIfAbsent(lockKey, ignored -> new ReentrantLock());
        localLock.lock();
        try {
            if (probe(request, toolchainRoot)) {
                return toolchain(toolchainRoot);
            }
            deploy(request, bundle, cacheRoot, toolchainRoot);
            if (!probe(request, toolchainRoot)) {
                throw new BitcodeRuntimeException(BitcodeReasonCode.TOOLCHAIN_CACHE_INVALID,
                        "受管 LLVM 工具链部署后校验失败");
            }
            return toolchain(toolchainRoot);
        } finally {
            localLock.unlock();
            if (!localLock.hasQueuedThreads()) {
                DEPLOY_LOCKS.remove(lockKey, localLock);
            }
        }
    }

    private void verifyLocalBundle(Path bundle) {
        if (!Files.isRegularFile(bundle)) {
            throw new BitcodeRuntimeException(BitcodeReasonCode.TOOLCHAIN_BUNDLE_UNAVAILABLE,
                    "受管 LLVM 工具链 bundle 不存在");
        }
        try {
            String actual = sha256(bundle);
            if (!actual.equalsIgnoreCase(properties.bundleSha256())) {
                throw new BitcodeRuntimeException(BitcodeReasonCode.TOOLCHAIN_BUNDLE_INVALID,
                        "受管 LLVM 工具链 bundle 完整性校验失败");
            }
        } catch (IOException ex) {
            throw new BitcodeRuntimeException(BitcodeReasonCode.TOOLCHAIN_BUNDLE_INVALID,
                    "受管 LLVM 工具链 bundle 无法读取", ex);
        }
    }

    private boolean probe(BitcodeGenerationRequest request, String root) {
        SshCommandResult result = execute(request, """
                set -eu
                ROOT=__ROOT__
                [ "$(uname -m)" = "x86_64" ] || exit 21
                [ -x "$ROOT/bin/clang" ] && [ -x "$ROOT/bin/clang++" ] && [ -x "$ROOT/bin/llvm-dis" ] || exit 22
                [ -f "$ROOT/.rvport-toolchain" ] || exit 23
                grep -Fx 'toolchainId=__TOOLCHAIN_ID__' "$ROOT/.rvport-toolchain" >/dev/null || exit 24
                grep -Fx 'bundleSha256=__BUNDLE_SHA__' "$ROOT/.rvport-toolchain" >/dev/null || exit 25
                "$ROOT/bin/clang" --version | head -n 1 | grep -F '__VERSION__' >/dev/null || exit 26
                echo RVPORT_BITCODE_TOOLCHAIN_READY
                """
                .replace("__ROOT__", shellQuote(root))
                .replace("__TOOLCHAIN_ID__", properties.toolchainId())
                .replace("__BUNDLE_SHA__", properties.bundleSha256().toLowerCase())
                .replace("__VERSION__", properties.toolchainVersion()), Duration.ofSeconds(60), null);
        return result.exitCode() == 0 && result.stdout().contains("RVPORT_BITCODE_TOOLCHAIN_READY");
    }

    private void deploy(BitcodeGenerationRequest request, Path bundle, String cacheRoot, String toolchainRoot) {
        String token = request.taskId().toString();
        String remoteBundle = joinRemote(cacheRoot, "." + properties.toolchainId() + "-" + token + ".tar.xz");
        String lock = toolchainRoot + ".lock";
        SshCommandResult prepared = execute(request, """
                set -eu
                CACHE_ROOT=__CACHE_ROOT__
                LOCK=__LOCK__
                mkdir -p "$CACHE_ROOT"
                attempts=0
                while ! mkdir "$LOCK" 2>/dev/null; do
                  if find "$LOCK" -maxdepth 0 -mmin +60 -print 2>/dev/null | grep -q .; then
                    rm -rf "$LOCK"
                    continue
                  fi
                  attempts=$((attempts + 1))
                  [ "$attempts" -lt 120 ] || exit 31
                  sleep 1
                done
                echo RVPORT_BITCODE_TOOLCHAIN_LOCK_ACQUIRED
                """
                .replace("__CACHE_ROOT__", shellQuote(cacheRoot))
                .replace("__LOCK__", shellQuote(lock)), Duration.ofSeconds(150), request.executionContext());
        if (prepared.exitCode() != 0) {
            throw new BitcodeRuntimeException(BitcodeReasonCode.TOOLCHAIN_LOCK_TIMEOUT,
                    "等待远端 LLVM 工具链部署锁超时");
        }
        try {
            ensureExtractionPrerequisite(request);
            sshClientAdapter.upload(new SshFileTransferRequest(
                    request.target(), request.jumpHost(), bundle, remoteBundle, properties.maxBundleBytes(),
                    Duration.ofSeconds(30), Duration.ofSeconds(properties.transferTimeoutSeconds()),
                    request.executionContext()
            ));
            SshCommandResult published = execute(request, """
                    set -eu
                    ROOT=__ROOT__
                    LOCK=__LOCK__
                    BUNDLE=__BUNDLE__
                    TMP="$ROOT.tmp-__TOKEN__"
                    cleanup() { rm -rf "$TMP" "$BUNDLE" "$LOCK"; }
                    trap cleanup EXIT INT TERM
                    [ "$(uname -m)" = "x86_64" ] || exit 41
                    printf '%s  %s\n' '__BUNDLE_SHA__' "$BUNDLE" | sha256sum -c - >/dev/null || exit 42
                    rm -rf "$TMP"
                    mkdir -p "$TMP"
                    tar -xJf "$BUNDLE" -C "$TMP" --strip-components=1 || exit 43
                    [ -x "$TMP/bin/clang" ] && [ -x "$TMP/bin/clang++" ] && [ -x "$TMP/bin/llvm-dis" ] || exit 44
                    "$TMP/bin/clang" --version | head -n 1 | grep -F '__VERSION__' >/dev/null || exit 45
                    printf 'toolchainId=%s\nbundleSha256=%s\nversion=%s\n' \
                      '__TOOLCHAIN_ID__' '__BUNDLE_SHA__' '__VERSION__' > "$TMP/.rvport-toolchain"
                    if [ -e "$ROOT" ]; then mv "$ROOT" "$ROOT.corrupt-__TOKEN__"; fi
                    mv "$TMP" "$ROOT"
                    echo RVPORT_BITCODE_TOOLCHAIN_PUBLISHED
                    """
                    .replace("__ROOT__", shellQuote(toolchainRoot))
                    .replace("__LOCK__", shellQuote(lock))
                    .replace("__BUNDLE__", shellQuote(remoteBundle))
                    .replace("__TOKEN__", token)
                    .replace("__BUNDLE_SHA__", properties.bundleSha256().toLowerCase())
                    .replace("__VERSION__", properties.toolchainVersion())
                    .replace("__TOOLCHAIN_ID__", properties.toolchainId()),
                    Duration.ofSeconds(properties.timeoutSeconds()), request.executionContext());
            if (published.exitCode() != 0 || !published.stdout().contains("RVPORT_BITCODE_TOOLCHAIN_PUBLISHED")) {
                throw new BitcodeRuntimeException(BitcodeReasonCode.TOOLCHAIN_CACHE_INVALID,
                        "远端 LLVM 工具链发布失败");
            }
        } catch (RuntimeException ex) {
            execute(request, "rm -rf " + shellQuote(lock) + " " + shellQuote(remoteBundle),
                    Duration.ofSeconds(30), null);
            throw ex;
        }
    }

    private void ensureExtractionPrerequisite(BitcodeGenerationRequest request) {
        SshCommandResult result = execute(request, """
                set -u
                if command -v xz >/dev/null 2>&1; then
                  echo RVPORT_BITCODE_XZ_READY
                  exit 0
                fi
                if command -v dnf >/dev/null 2>&1; then
                  dnf --setopt=timeout=30 --setopt=retries=1 --setopt=skip_if_unavailable=True install -y xz
                elif command -v yum >/dev/null 2>&1; then
                  yum --setopt=timeout=30 --setopt=retries=1 --setopt=skip_if_unavailable=True install -y xz
                elif command -v apt-get >/dev/null 2>&1; then
                  DEBIAN_FRONTEND=noninteractive apt-get install -y xz-utils \
                    || (apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y xz-utils)
                elif command -v zypper >/dev/null 2>&1; then
                  zypper --non-interactive install xz
                elif command -v apk >/dev/null 2>&1; then
                  apk add --no-cache xz
                elif command -v pacman >/dev/null 2>&1; then
                  pacman -Sy --noconfirm xz
                else
                  exit 51
                fi
                command -v xz >/dev/null 2>&1 || exit 52
                echo RVPORT_BITCODE_XZ_READY
                """, Duration.ofSeconds(300), request.executionContext());
        if (result.exitCode() != 0 || !result.stdout().contains("RVPORT_BITCODE_XZ_READY")) {
            throw new BitcodeRuntimeException(BitcodeReasonCode.TOOLCHAIN_PREREQUISITE_UNAVAILABLE,
                    "远端 x86 环境缺少 xz，且自动安装失败");
        }
    }

    private RemoteBitcodeToolchain toolchain(String root) {
        return new RemoteBitcodeToolchain(root, joinRemote(root, "bin/clang"), joinRemote(root, "bin/clang++"),
                joinRemote(root, "bin/llvm-dis"), properties.toolchainId(), properties.toolchainVersion());
    }

    private SshCommandResult execute(
            BitcodeGenerationRequest request,
            String command,
            Duration timeout,
            TaskExecutionContext context
    ) {
        return sshClientAdapter.execute(new SshCommandRequest(
                request.target(), request.jumpHost(), command, null, false,
                Duration.ofSeconds(30), timeout, context
        ));
    }

    private String sha256(Path path) throws IOException {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (InputStream input = Files.newInputStream(path)) {
                byte[] buffer = new byte[64 * 1024];
                int read;
                while ((read = input.read(buffer)) >= 0) {
                    if (read > 0) {
                        digest.update(buffer, 0, read);
                    }
                }
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (java.security.NoSuchAlgorithmException ex) {
            throw new IllegalStateException(ex);
        }
    }

    private String joinRemote(String base, String child) {
        return base.replaceAll("/+$", "") + "/" + child.replaceAll("^/+", "");
    }

    private String shellQuote(String value) {
        return "'" + value.replace("'", "'\"'\"'") + "'";
    }
}
