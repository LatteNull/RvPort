package cn.rvport.backend.dependency;

import cn.rvport.backend.buildvalidation.BuildValidationRunView;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.stereotype.Component;

@Component
class DependencyFactExtractor {

    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();
    private static final int MAX_COMPILE_DATABASE_ENTRIES = 10_000;
    private static final int MAX_COMMAND_LENGTH = 16_384;
    private static final Pattern TOOL_PATTERN = Pattern.compile("\\b(cmake|make|ninja|gcc|g\\+\\+|clang|clang\\+\\+|pkg-config|rpmbuild|configure|meson)\\b");
    private static final Pattern LINK_LIB_PATTERN = Pattern.compile("(?<!\\S)-l([A-Za-z0-9_+.-]+)");
    private static final Pattern HEADER_PATTERN = Pattern.compile("([A-Za-z0-9_+./-]+\\.h):\\s+No such file or directory");
    private static final Pattern INCLUDE_FLAG_PATTERN = Pattern.compile("(?<!\\S)-I\\s*([^\\s]+)|(?<!\\S)-I([^\\s]+)");
    private static final Pattern LIBRARY_PATH_FLAG_PATTERN = Pattern.compile("(?<!\\S)-L\\s*([^\\s]+)|(?<!\\S)-L([^\\s]+)");
    private static final Pattern PKG_CONFIG_PATTERN = Pattern.compile("No package '([^']+)' found|Package ([A-Za-z0-9_+.-]+) was not found|pkg-config\\s+(?:--[^\\s]+\\s+)*([A-Za-z0-9_+.-]+)");
    private static final Pattern LOADER_PATTERN = Pattern.compile("error while loading shared libraries:\\s+([^:\\s]+)");
    private static final Pattern TRACE_PATTERN = Pattern.compile("RVPORT_TRACE\\s+ts=\\S+\\s+pwd=([^\\s]+)\\s+line=(\\d+)\\s+cmd=(.*)");
    private static final Pattern COMPILE_DATABASE_PATTERN = Pattern.compile("RVPORT_OBSERVATION compileDatabase\\s+([^\\t\\r\\n ]+)(?:\\t([^\\r\\n]+))?");
    private static final Pattern CMAKE_CACHE_PATTERN = Pattern.compile("RVPORT_OBSERVATION cmakeCache\\s+([^\\t\\r\\n ]+)(?:\\t([^\\r\\n]+))?");
    private static final Pattern BUILD_NINJA_PATTERN = Pattern.compile("RVPORT_OBSERVATION buildNinja\\s+([^\\t\\r\\n ]+)(?:\\t([^\\r\\n]+))?");
    private static final Pattern COMPILER_BUILTIN_MACROS_PATTERN = Pattern.compile("RVPORT_OBSERVATION compilerBuiltinMacros\\s+([^\\t\\r\\n ]+)(?:\\t([^\\r\\n]+))?");
    private static final Pattern CMAKE_COMPILER_FLAG_PROBE_PATTERN = Pattern.compile("RVPORT_OBSERVATION cmakeCompilerFlagProbe\\s+([^\\t\\r\\n ]+)(?:\\t([^\\r\\n]+))?");
    private static final Pattern EXECVE_SUMMARY_PATTERN = Pattern.compile("RVPORT_OBSERVATION execveSummary\\s+([^\\t\\r\\n ]+)(?:\\t([^\\r\\n]+))?");
    private static final Pattern EXECVE_TOOL_PATTERN = Pattern.compile("RVPORT_OBSERVATION execveTool\\s+([^\\t\\r\\n ]+)(?:\\t([^\\r\\n]+))?");
    private static final Pattern REPOSITORY_BUNDLED_ELF_PATTERN = Pattern.compile("RVPORT_OBSERVATION repositoryBundledElf\\s+([^\\t\\r\\n]+)(?:\\t([^\\r\\n]+))?");
    private static final Pattern BUILD_PRODUCED_ELF_PATTERN = Pattern.compile("RVPORT_OBSERVATION buildProducedElf\\s+([^\\t\\r\\n]+)(?:\\t([^\\r\\n]+))?");
    private static final Pattern ELF_NEEDED_PATTERN = Pattern.compile("RVPORT_OBSERVATION elfNeeded\\s+([^\\t\\r\\n]+)\\t([^\\r\\n]+)");
    private static final Pattern ELF_SONAME_PATTERN = Pattern.compile("RVPORT_OBSERVATION elfSoname\\s+([^\\t\\r\\n]+)\\t([^\\r\\n]+)");
    private static final Pattern RESOLVED_NEEDED_LIBRARY_PATTERN = Pattern.compile("RVPORT_OBSERVATION resolvedNeededLibrary\\s+([^\\t\\r\\n]+)(?:\\t([^\\r\\n]+))?");
    private static final Pattern OWNER_PACKAGE_PATTERN = Pattern.compile("RVPORT_OBSERVATION ownerPackage\\s+([^\\t\\r\\n]+)\\t([^\\r\\n]+)");
    private static final Pattern LINKING_SHARED_LIBRARY_PATTERN = Pattern.compile("Linking\\s+(?:[A-Za-z+]+\\s+)?shared library\\s+([^\\s]+)");
    private static final Set<String> INTERNAL_OBSERVABILITY_TOOLS = Set.of("bear", "strace");
    private static final Set<String> TOOLCHAIN_COMPONENTS = Set.of("ar", "as", "ld", "ranlib", "strip", "objcopy", "objdump");
    private static final Set<String> COMMON_COMPILER_BUILTIN_MACROS = Set.of(
            "__GNUC__", "__GNUC_MINOR__", "__GNUC_PATCHLEVEL__", "__VERSION__", "__OPTIMIZE__",
            "__clang__", "__clang_major__", "__clang_minor__", "__clang_patchlevel__",
            "__cplusplus", "__STDC__", "__STDC_VERSION__", "__STDC_HOSTED__",
            "__linux__", "__unix__", "__ELF__", "__SIZEOF_POINTER__", "__BYTE_ORDER__",
            "__ORDER_LITTLE_ENDIAN__", "__ORDER_BIG_ENDIAN__", "__riscv", "__riscv_xlen",
            "__x86_64__", "__i386__", "__aarch64__", "__arm__"
    );

    List<DependencyAnalysisResultItem> extract(
            DependencyAnalysisView run,
            BuildValidationRunView buildRun,
            String mergedLogExcerpt
    ) {
        return extract(run, buildRun, mergedLogExcerpt, List.of());
    }

    List<DependencyAnalysisResultItem> extract(
            DependencyAnalysisView run,
            BuildValidationRunView buildRun,
            String mergedLogExcerpt,
            Collection<DependencyAnalysisRepository.TargetComponentView> targetComponents
    ) {
        return extract(run, buildRun, mergedLogExcerpt, List.of(), targetComponents);
    }

    List<DependencyAnalysisResultItem> extract(
            DependencyAnalysisView run,
            BuildValidationRunView buildRun,
            String mergedLogExcerpt,
            Collection<DependencyAnalysisRepository.TargetComponentView> sourceComponents,
            Collection<DependencyAnalysisRepository.TargetComponentView> targetComponents
    ) {
        return extract(run, buildRun, mergedLogExcerpt, sourceComponents, targetComponents, null);
    }

    List<DependencyAnalysisResultItem> extract(
            DependencyAnalysisView run,
            BuildValidationRunView buildRun,
            String mergedLogExcerpt,
            Collection<DependencyAnalysisRepository.TargetComponentView> sourceComponents,
            Collection<DependencyAnalysisRepository.TargetComponentView> targetComponents,
            String compileDatabaseJson
    ) {
        List<DependencyAnalysisResultItem> items = new ArrayList<>();
        SourceCapabilityIndex sourceIndex = new SourceCapabilityIndex(sourceComponents);
        TargetCapabilityIndex targetIndex = new TargetCapabilityIndex(targetComponents);
        String text = String.join("\n", safe(buildRun.command()), safe(mergedLogExcerpt));
        SourceOwnerIndex sourceOwnerIndex = new SourceOwnerIndex(text);
        BuildProducedElfIndex buildProducedElfIndex = new BuildProducedElfIndex(text, compileDatabaseJson);
        Set<String> compilerBuiltinMacros = compilerBuiltinMacros(text);
        Map<String, List<CMakeCompilerFlagProbe>> cmakeCompilerFlagProbes = cmakeCompilerFlagProbes(text);
        addTools(items, run, text, sourceIndex, targetIndex, buildRun);
        addCompileDatabases(items, run, text, sourceIndex, targetIndex, compilerBuiltinMacros, cmakeCompilerFlagProbes);
        addExecveTrace(items, run, text, sourceIndex, targetIndex, compilerBuiltinMacros, cmakeCompilerFlagProbes);
        addCompilerAndLinkerArgs(items, run, text);
        addLinkLibraries(items, run, text, sourceIndex, targetIndex);
        addHeaders(items, run, text, targetIndex);
        addPkgConfig(items, run, text, targetIndex);
        addRuntimeLibraries(items, run, text, targetIndex);
        addRepositoryBundledElf(items, run, text, targetIndex, sourceOwnerIndex, buildProducedElfIndex);
        addElfDynamicDependencies(items, run, text, targetIndex, sourceOwnerIndex, buildProducedElfIndex);
        if (items.isEmpty()) {
            items.add(item(run, DependencyType.BUILD_TOOL, "build-script", null,
                    DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED,
                    DependencyRiskLevel.INFO,
                    "build:build-script",
                    "构建成功但未提取到明确依赖线索，建议人工确认构建脚本和产物",
                    DependencyConfidence.LOW,
                    Map.of("source", "BUILD_RUN", "buildRunId", buildRun.id().toString())));
        }
        return dedupe(items);
    }

    private void addTools(List<DependencyAnalysisResultItem> items, DependencyAnalysisView run, String text,
                          SourceCapabilityIndex sourceIndex, TargetCapabilityIndex targetIndex,
                          BuildValidationRunView buildRun) {
        for (String line : text.split("\\R")) {
            if (line.startsWith("RVPORT_OBSERVATION ")) {
                continue;
            }
            if (isBuildSystemDiscoveryLine(line)) {
                continue;
            }
            Matcher matcher = TOOL_PATTERN.matcher(line);
            while (matcher.find()) {
                String tool = matcher.group(1);
                if (isInternalTool(tool)) {
                    continue;
                }
                if (isToolFileNameReference(line, matcher.start(), matcher.end())) {
                    continue;
                }
                Map<String, Object> sourceProvider = sourceIndex.toolEvidence(tool);
                MatchDecision match = targetIndex.matchTool(tool, sourceProviderPackage(sourceProvider));
                items.add(item(run, DependencyType.BUILD_TOOL, tool, match.version(),
                        match.status(),
                        riskFor(match.status(), DependencyRiskLevel.INFO),
                        "build:" + tool,
                        recommendation("确认 RISC-V 构建环境是否具备工具 " + tool, match),
                        DependencyConfidence.OBSERVED,
                        evidence("tool_pattern", matcher.group(), match.evidence(), mergeExtra(sourceProvider, Map.of(
                                "environmentVariableNames", buildRun.environmentVariables() == null
                                        ? List.of()
                                        : buildRun.environmentVariables().keySet().stream().sorted().toList()
                        )))));
            }
        }
    }

    private boolean isBuildSystemDiscoveryLine(String line) {
        return line.contains("CMakeLists.txt")
                && line.contains("Makefile")
                && line.contains("meson.build")
                && line.contains("build.ninja");
    }

    private boolean isToolFileNameReference(String line, int start, int end) {
        return (start > 0 && line.charAt(start - 1) == '.')
                || (end < line.length() && line.charAt(end) == '.');
    }

    private void addCompileDatabases(List<DependencyAnalysisResultItem> items, DependencyAnalysisView run, String text,
                                     SourceCapabilityIndex sourceIndex,
                                     TargetCapabilityIndex targetIndex,
                                     Set<String> compilerBuiltinMacros,
                                     Map<String, List<CMakeCompilerFlagProbe>> cmakeCompilerFlagProbes) {
        Matcher matcher = COMPILE_DATABASE_PATTERN.matcher(text);
        while (matcher.find()) {
            Map<String, String> properties = properties(matcher.group(2));
            List<String> compilers = csv(properties.get("compilers"));
            List<String> includes = csv(properties.get("includes"));
            List<String> defines = csv(properties.get("defines"));
            List<String> libPaths = csv(properties.get("libPaths"));
            List<String> linkLibs = csv(properties.get("linkLibs"));
            List<String> standards = csv(properties.get("standards"));
            if (compilers.isEmpty() && includes.isEmpty() && defines.isEmpty() && libPaths.isEmpty()
                    && linkLibs.isEmpty() && standards.isEmpty()) {
                continue;
            }
            for (String compiler : compilers) {
                Map<String, Object> sourceProvider = sourceIndex.toolEvidence(compiler);
                MatchDecision match = targetIndex.matchTool(compiler, sourceProviderPackage(sourceProvider));
                items.add(item(run, DependencyType.BUILD_TOOL, compiler, match.version(),
                        match.status(),
                        riskFor(match.status(), DependencyRiskLevel.INFO),
                        "build:" + compiler,
                        recommendation("compile_commands.json 中使用编译器 " + compiler, match),
                        DependencyConfidence.HIGH,
                        evidence("compile_database_compiler", matcher.group(), match.evidence(), mergeExtra(sourceProvider, Map.of(
                                "compileDatabasePath", matcher.group(1),
                                "commandCount", properties.getOrDefault("commands", "")
                        )))));
            }
            for (String library : linkLibs) {
                String soname = "lib" + library + ".so";
                Map<String, Object> sourceProvider = sourceIndex.libraryEvidence(soname);
                ProviderMatch match = targetIndex.matchProvider(soname, sourcePackage(sourceProvider), soname);
                items.add(providerItem(run, DependencyType.LINK_LIBRARY, match,
                        "compile_database_link_library", matcher.group(), mergeExtra(sourceProvider, Map.of(
                                "compileDatabasePath", matcher.group(1),
                                "linkName", library,
                                "librarySearchPaths", libPaths
                        ))));
            }
            for (String include : includes) {
                if (isTrivialPath(include)) {
                    continue;
                }
                items.add(item(run, DependencyType.BUILD_PACKAGE, include, null,
                        DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED,
                        DependencyRiskLevel.INFO,
                        "include:" + include,
                        "compile_commands.json 中出现 include 路径，建议结合 header/provider 继续确认",
                        DependencyConfidence.OBSERVED,
                        evidence("compile_database_include_path", matcher.group(), Map.of(), Map.of(
                                "compileDatabasePath", matcher.group(1),
                                "includePath", include
                        ))));
            }
            for (String define : defines) {
                classifyMacro(define, compilerBuiltinMacros, cmakeCompilerFlagProbes);
            }
        }
        addBuildNinja(items, run, text, sourceIndex, targetIndex);
    }

    private void addBuildNinja(List<DependencyAnalysisResultItem> items, DependencyAnalysisView run, String text,
                               SourceCapabilityIndex sourceIndex, TargetCapabilityIndex targetIndex) {
        Matcher matcher = BUILD_NINJA_PATTERN.matcher(text);
        while (matcher.find()) {
            Map<String, String> props = properties(matcher.group(2));
            String commands = props.getOrDefault("commands", "");
            if (commands.isBlank()) {
                continue;
            }
            addCompilerAndLinkerArgs(items, run, commands);
            addLinkLibraries(items, run, commands, sourceIndex, targetIndex);
        }
    }

    private void addExecveTrace(List<DependencyAnalysisResultItem> items, DependencyAnalysisView run, String text,
                                SourceCapabilityIndex sourceIndex,
                                TargetCapabilityIndex targetIndex,
                                Set<String> compilerBuiltinMacros,
                                Map<String, List<CMakeCompilerFlagProbe>> cmakeCompilerFlagProbes) {
        Matcher summary = EXECVE_SUMMARY_PATTERN.matcher(text);
        while (summary.find()) {
            Map<String, String> props = properties(summary.group(2));
            for (String toolCount : csv(props.get("tools"))) {
                String tool = toolCount.split(":", 2)[0];
                if (tool.isBlank() || isInternalTool(tool)) {
                    continue;
                }
                Map<String, Object> sourceProvider = sourceIndex.toolEvidence(tool);
                MatchDecision match = targetIndex.matchTool(tool, sourceProviderPackage(sourceProvider));
                items.add(item(run, DependencyType.BUILD_TOOL, tool, match.version(),
                        match.status(),
                        riskFor(match.status(), DependencyRiskLevel.INFO),
                        "execve-summary:" + tool,
                        recommendation("strace execve 观测到工具 " + tool, match),
                        DependencyConfidence.HIGH,
                        evidence("strace_execve_summary", summary.group(), match.evidence(), mergeExtra(sourceProvider, Map.of(
                                "tracePath", summary.group(1),
                                "execveCount", props.getOrDefault("execve", ""),
                                "toolCount", toolCount.contains(":") ? toolCount.split(":", 2)[1] : ""
                        )))));
            }
        }
        Matcher tool = EXECVE_TOOL_PATTERN.matcher(text);
        while (tool.find()) {
            String toolName = tool.group(1);
            if (isInternalTool(toolName)) {
                continue;
            }
            Map<String, String> props = properties(tool.group(2));
            Map<String, Object> sourceToolProvider = sourceIndex.toolEvidence(toolName, props.getOrDefault("path", ""));
            MatchDecision toolMatch = targetIndex.matchTool(toolName, sourceProviderPackage(sourceToolProvider));
            items.add(item(run, DependencyType.BUILD_TOOL, toolName, toolMatch.version(),
                    toolMatch.status(),
                    riskFor(toolMatch.status(), DependencyRiskLevel.INFO),
                    "execve:" + toolName,
                    recommendation("strace execve 观测到工具 " + toolName, toolMatch),
                    DependencyConfidence.HIGH,
                    evidence("strace_execve_tool", tool.group(), toolMatch.evidence(), mergeExtra(sourceToolProvider, Map.of(
                            "path", props.getOrDefault("path", ""),
                            "count", props.getOrDefault("count", "")
                    )))));
            for (String library : csv(props.get("linkLibs"))) {
                String soname = "lib" + library + ".so";
                Map<String, Object> sourceProvider = sourceIndex.libraryEvidence(soname);
                ProviderMatch match = targetIndex.matchProvider(soname, sourcePackage(sourceProvider), soname);
                items.add(providerItem(run, DependencyType.LINK_LIBRARY, match,
                        "strace_execve_link_library", tool.group(), mergeExtra(sourceProvider, Map.of(
                                "tool", toolName,
                                "linkName", library,
                                "librarySearchPaths", csv(props.get("libPaths"))
                        ))));
            }
            for (String include : csv(props.get("includes"))) {
                if (isTrivialPath(include)) {
                    continue;
                }
                items.add(item(run, DependencyType.BUILD_PACKAGE, include, null,
                        DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED,
                        DependencyRiskLevel.INFO,
                        "include:" + include,
                        "strace execve 观测到 include 路径，建议结合 header/provider 继续确认",
                        DependencyConfidence.OBSERVED,
                        evidence("strace_execve_include_path", tool.group(), Map.of(), Map.of("tool", toolName, "includePath", include))));
            }
            for (String define : csv(props.get("defines"))) {
                classifyMacro(define, compilerBuiltinMacros, cmakeCompilerFlagProbes);
            }
        }
    }

    private void addCompilerAndLinkerArgs(List<DependencyAnalysisResultItem> items, DependencyAnalysisView run, String text) {
        addArgObservations(items, run, INCLUDE_FLAG_PATTERN, text, "include_path", "include:");
    }

    private void addArgObservations(List<DependencyAnalysisResultItem> items, DependencyAnalysisView run, Pattern pattern,
                                    String text, String source, String locationPrefix) {
        Matcher matcher = pattern.matcher(text);
        while (matcher.find()) {
            String value = firstNonBlank(matcher.group(1), matcher.group(2));
            if (isTrivialPath(value)) {
                continue;
            }
            items.add(item(run, DependencyType.BUILD_PACKAGE, value, null,
                    DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED,
                    DependencyRiskLevel.INFO,
                    locationPrefix + value,
                    "已采集构建参数，作为依赖定位辅助证据",
                    DependencyConfidence.OBSERVED,
                    evidence(source, matcher.group())));
        }
    }

    private void addLinkLibraries(List<DependencyAnalysisResultItem> items, DependencyAnalysisView run, String text,
                                  SourceCapabilityIndex sourceIndex, TargetCapabilityIndex targetIndex) {
        Matcher matcher = LINK_LIB_PATTERN.matcher(text);
        while (matcher.find()) {
            String name = matcher.group(1);
            String library = "lib" + name + ".so";
            Map<String, Object> sourceProvider = sourceIndex.libraryEvidence(library);
            ProviderMatch match = targetIndex.matchProvider(library, sourcePackage(sourceProvider), library);
            items.add(providerItem(run, DependencyType.LINK_LIBRARY, match,
                    "linker_flag", matcher.group(), mergeExtra(sourceProvider, Map.of("linkName", name))));
        }
    }

    private void addHeaders(List<DependencyAnalysisResultItem> items, DependencyAnalysisView run, String text,
                            TargetCapabilityIndex targetIndex) {
        Matcher matcher = HEADER_PATTERN.matcher(text);
        while (matcher.find()) {
            String header = matcher.group(1);
            MatchDecision match = targetIndex.matchHeader(header);
            items.add(item(run, DependencyType.BUILD_PACKAGE, header, match.version(),
                    match.status(),
                    riskFor(match.status(), DependencyRiskLevel.HIGH),
                    "header:" + header,
                    recommendation("查询目标环境 header provider，例如 dnf provides '*/" + header + "'", match),
                    DependencyConfidence.HIGH,
                    evidence("missing_header", matcher.group(), match.evidence(), Map.of("header", header))));
        }
    }

    private void addPkgConfig(List<DependencyAnalysisResultItem> items, DependencyAnalysisView run, String text,
                              TargetCapabilityIndex targetIndex) {
        Matcher matcher = PKG_CONFIG_PATTERN.matcher(text);
        while (matcher.find()) {
            String module = firstNonBlank(matcher.group(1), matcher.group(2), matcher.group(3));
            MatchDecision match = targetIndex.matchPkgConfig(module);
            items.add(item(run, DependencyType.BUILD_PACKAGE, module, match.version(),
                    match.status(),
                    riskFor(match.status(), DependencyRiskLevel.HIGH),
                    "package:" + module,
                    recommendation("查询目标环境是否存在 pkg-config module " + module + " 及其 provider", match),
                    DependencyConfidence.HIGH,
                    evidence("pkg_config", matcher.group(), match.evidence(), Map.of("module", module))));
        }
    }

    private void addRuntimeLibraries(List<DependencyAnalysisResultItem> items, DependencyAnalysisView run, String text,
                                     TargetCapabilityIndex targetIndex) {
        Matcher matcher = LOADER_PATTERN.matcher(text);
        while (matcher.find()) {
            String library = matcher.group(1);
            MatchDecision match = targetIndex.matchLibrary(library);
            items.add(item(run, DependencyType.RUNTIME_LIBRARY, library, match.version(),
                    match.status(),
                    riskFor(match.status(), DependencyRiskLevel.HIGH),
                    "lib:" + library,
                    recommendation("查询目标环境运行时库 provider", match),
                    DependencyConfidence.HIGH,
                    evidence("runtime_loader_error", matcher.group(), match.evidence(), Map.of("library", library))));
        }
    }

    private void addRepositoryBundledElf(List<DependencyAnalysisResultItem> items, DependencyAnalysisView run, String text,
                                         TargetCapabilityIndex targetIndex,
                                         SourceOwnerIndex sourceOwnerIndex,
                                         BuildProducedElfIndex buildProducedElfIndex) {
        Matcher matcher = REPOSITORY_BUNDLED_ELF_PATTERN.matcher(text);
        while (matcher.find()) {
            String relativePath = matcher.group(1);
            if (buildProducedElfIndex.isProducedPath(relativePath)) {
                continue;
            }
            String fileType = matcher.group(2) == null ? "" : matcher.group(2);
            String name = fileName(relativePath);
            if (buildProducedElfIndex.isProducedLibrary(name)) {
                continue;
            }
            DependencyType dependencyType = name.contains(".so") ? DependencyType.RUNTIME_LIBRARY : DependencyType.BUILD_PACKAGE;
            if (!name.contains(".so")) {
                continue;
            }
            ProviderMatch providerMatch = targetIndex.matchProvider(name, sourceOwnerIndex.owner(relativePath), relativePath);
            items.add(providerItem(run, dependencyType, providerMatch, "repository_bundled_elf", relativePath, Map.of(
                    "relativePath", sanitize(relativePath),
                    "fileType", sanitize(fileType),
                    "buildProducedArtifact", false
            )));
        }
    }

    private void addElfDynamicDependencies(List<DependencyAnalysisResultItem> items, DependencyAnalysisView run, String text,
                                           TargetCapabilityIndex targetIndex,
                                           SourceOwnerIndex sourceOwnerIndex,
                                           BuildProducedElfIndex buildProducedElfIndex) {
        Matcher needed = ELF_NEEDED_PATTERN.matcher(text);
        while (needed.find()) {
            String elfPath = needed.group(1);
            String library = needed.group(2);
            if (buildProducedElfIndex.isProducedLibrary(library)) {
                continue;
            }
            ResolvedNeededLibrary resolved = sourceOwnerIndex.resolvedNeeded(elfPath, library);
            ProviderMatch providerMatch = targetIndex.matchProvider(library, resolved.sourcePackage(sourceOwnerIndex.owner(elfPath)), resolved.sourcePath(elfPath));
            items.add(providerItem(run, DependencyType.RUNTIME_LIBRARY, providerMatch, "elf_needed", needed.group(), mergeExtra(resolved.evidence(), Map.of(
                    "elfPath", sanitize(elfPath)
            ))));
        }
        Matcher soname = ELF_SONAME_PATTERN.matcher(text);
        while (soname.find()) {
            String elfPath = soname.group(1);
            String library = soname.group(2);
            if (buildProducedElfIndex.isProducedPath(elfPath) || buildProducedElfIndex.isProducedLibrary(library)) {
                continue;
            }
            ResolvedNeededLibrary resolved = sourceOwnerIndex.resolvedNeeded(elfPath, library);
            ProviderMatch providerMatch = targetIndex.matchProvider(library, resolved.sourcePackage(sourceOwnerIndex.owner(elfPath)), resolved.sourcePath(elfPath));
            items.add(providerItem(run, DependencyType.RUNTIME_LIBRARY, providerMatch, "elf_soname", soname.group(), mergeExtra(resolved.evidence(), Map.of(
                    "elfPath", sanitize(elfPath)
            ))));
        }
    }

    private DependencyRiskLevel riskFor(DependencyTargetMatchStatus status, DependencyRiskLevel fallback) {
        return switch (status) {
            case SAME_MAJOR -> DependencyRiskLevel.INFO;
            case TARGET_NEWER -> DependencyRiskLevel.LOW;
            case TARGET_OLDER -> DependencyRiskLevel.HIGH;
            case TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED -> DependencyRiskLevel.MEDIUM;
            case NO_TARGET_VERSION_FOUND -> DependencyRiskLevel.CRITICAL;
            case TARGET_INSTALLED -> DependencyRiskLevel.LOW;
            case REPO_AVAILABLE, PROVIDES_MATCH -> DependencyRiskLevel.MEDIUM;
            case VERSION_MISMATCH, SOURCE_BUILD_REQUIRED, MISSING -> DependencyRiskLevel.HIGH;
            case MANUAL_CONFIRM_REQUIRED -> fallback;
        };
    }

    private String recommendation(String base, MatchDecision match) {
        return switch (match.status()) {
            case SAME_MAJOR -> base + "；目标 provider 与源 provider 大版本一致，迁移风险较低。";
            case TARGET_NEWER -> base + "；目标 provider 版本高于源版本，建议确认向后兼容。";
            case TARGET_OLDER -> base + "；目标 provider 版本低于源版本，存在兼容性风险。";
            case TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED -> base + "；源侧无法确认 owner 包，但目标存在 provider，建议人工确认 ABI。";
            case NO_TARGET_VERSION_FOUND -> base + "；源侧无 owner 且目标无可确认 provider，风险较高。";
            case TARGET_INSTALLED -> base + "；目标环境已安装匹配项，建议确认版本和 ABI。";
            case REPO_AVAILABLE -> base + "；目标仓库存在候选包，建议安装后复跑构建。";
            case PROVIDES_MATCH -> base + "；目标环境 provides/路径存在匹配，建议确认 provider 包。";
            case VERSION_MISMATCH -> base + "；目标存在同名项但版本不同，建议确认兼容性。";
            case SOURCE_BUILD_REQUIRED -> base + "；目标未发现直接包或 provider，可能需要源码构建。";
            case MISSING -> base + "；目标环境未发现可用项。";
            case MANUAL_CONFIRM_REQUIRED -> base + "；当前证据不足，需要人工确认。";
        };
    }

    private DependencyAnalysisResultItem providerItem(
            DependencyAnalysisView run,
            DependencyType type,
            ProviderMatch match,
            String source,
            String snippet,
            Map<String, ?> extra
    ) {
        String name = firstNonBlank(match.sourceOwnerPackage(), match.libraryName());
        String version = firstNonBlank(match.sourceOwnerVersion(), match.sourceVersionEvidence());
        String location = match.sourceOwnerPackage().isBlank()
                ? "lib:" + firstNonBlank(match.sourceSoname(), match.sourceLibraryPath(), match.libraryName())
                : "package:" + match.sourceOwnerPackage() + "@" + firstNonBlank(match.sourceOwnerVersion(), "unknown");
        Map<String, Object> evidence = providerEvidence(source, snippet, match, extra);
        return item(run, type, name, version,
                match.versionRelation(),
                match.riskLevel(),
                location,
                providerRecommendation(match),
                match.confidence(),
                evidence);
    }

    private String providerRecommendation(ProviderMatch match) {
        return switch (match.versionRelation()) {
            case SAME_MAJOR -> "源环境和目标环境存在大版本一致的 provider package，建议继续进行构建验证。";
            case TARGET_NEWER -> "目标环境 provider package 版本高于源环境，建议确认 ABI 和行为兼容。";
            case TARGET_OLDER -> "目标环境 provider package 版本低于源环境，建议优先升级目标依赖或确认兼容性。";
            case TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED -> "源侧文件无法归属软件包，但目标环境存在候选 provider，建议人工确认该库来源和 ABI。";
            case NO_TARGET_VERSION_FOUND -> "源侧文件无法归属软件包，目标环境也没有可确认 provider，可能需要补包、源码构建或替换实现。";
            case TARGET_INSTALLED, REPO_AVAILABLE, PROVIDES_MATCH, VERSION_MISMATCH, SOURCE_BUILD_REQUIRED, MISSING, MANUAL_CONFIRM_REQUIRED ->
                    "目标 provider 证据不足，建议人工确认。";
        };
    }

    private SourcePackage sourcePackage(Map<String, Object> sourceProvider) {
        if (sourceProvider == null || sourceProvider.isEmpty()) {
            return SourcePackage.empty();
        }
        String name = stringValue(sourceProvider.get("sourceProviderPackage"));
        if (name.isBlank()) {
            return SourcePackage.empty();
        }
        return new SourcePackage(
                name,
                stringValue(sourceProvider.get("sourceProviderVersion")),
                stringValue(sourceProvider.get("sourceProviderSource"))
        );
    }

    private Map<String, Object> providerEvidence(String source, String snippet, ProviderMatch match, Map<String, ?> extra) {
        Map<String, Object> value = evidence(source, snippet, Map.of(), extra);
        value.put("sourceLibraryPath", sanitize(match.sourceLibraryPath()));
        value.put("sourceLibraryName", sanitize(match.libraryName()));
        value.put("sourceSoname", sanitize(match.sourceSoname()));
        value.put("sourceOwnerPackage", sanitize(match.sourceOwnerPackage()));
        value.put("sourceOwnerVersion", sanitize(match.sourceOwnerVersion()));
        value.put("sourceOwnerSource", sanitize(match.sourceOwnerSource()));
        value.put("sourceVersionEvidence", sanitize(match.sourceVersionEvidence()));
        value.put("targetProviderPackage", sanitize(match.targetProviderPackage()));
        value.put("targetProviderVersion", sanitize(match.targetProviderVersion()));
        value.put("targetProviderSource", sanitize(match.targetProviderSource()));
        value.put("versionRelation", match.versionRelation().name());
        value.put("riskMappingRule", sanitize(match.riskMappingRule()));
        value.put("matchEvidence", match.matchEvidence());
        value.put("evidencePaths", match.evidencePaths());
        return value;
    }

    private DependencyAnalysisResultItem item(
            DependencyAnalysisView run,
            DependencyType type,
            String name,
            String version,
            DependencyTargetMatchStatus status,
            DependencyRiskLevel risk,
            String location,
            String recommendation,
            DependencyConfidence confidence,
            Map<String, Object> evidence
    ) {
        ProviderFields providerFields = ProviderFields.from(version, status, evidence);
        return new DependencyAnalysisResultItem(
                run.projectId(),
                run.sourceRevisionId(),
                run.taskId(),
                run.id(),
                type,
                name,
                version,
                providerFields.sourceProviderPackage(),
                providerFields.sourceProviderVersion(),
                providerFields.sourceDetectedVersion(),
                providerFields.targetProviderPackage(),
                providerFields.targetProviderVersion(),
                providerFields.targetDetectedVersion(),
                providerFields.providerVersionStatus(),
                providerFields.versionEvidenceConfidence(),
                status,
                risk,
                location,
                recommendation,
                confidence,
                evidence
        );
    }

    private List<DependencyAnalysisResultItem> dedupe(List<DependencyAnalysisResultItem> items) {
        Map<String, DependencyAnalysisResultItem> byKey = new LinkedHashMap<>();
        for (DependencyAnalysisResultItem item : items) {
            String key = dedupeKey(item);
            DependencyAnalysisResultItem existing = byKey.get(key);
            if (existing != null && isProviderItem(existing) && isProviderItem(item)) {
                byKey.put(key, mergeProviderItems(existing, item));
            } else if (existing == null || shouldReplace(existing, item)) {
                byKey.put(key, item);
            }
        }
        return List.copyOf(byKey.values());
    }

    private boolean isProviderItem(DependencyAnalysisResultItem item) {
        return item.evidence() != null && item.evidence().containsKey("versionRelation");
    }

    private DependencyAnalysisResultItem mergeProviderItems(DependencyAnalysisResultItem left, DependencyAnalysisResultItem right) {
        Map<String, Object> evidence = new LinkedHashMap<>(left.evidence());
        List<String> paths = new ArrayList<>();
        paths.addAll(stringList(left.evidence().get("evidencePaths")));
        paths.addAll(stringList(right.evidence().get("evidencePaths")));
        paths = paths.stream().filter(path -> !path.isBlank()).distinct().toList();
        evidence.put("evidencePaths", paths);
        List<Object> grouped = new ArrayList<>();
        grouped.addAll(objectList(left.evidence().get("groupedEvidence")));
        grouped.add(Map.of(
                "sourceLibraryPath", right.evidence().getOrDefault("sourceLibraryPath", ""),
                "sourceLibraryName", right.evidence().getOrDefault("sourceLibraryName", ""),
                "sourceSoname", right.evidence().getOrDefault("sourceSoname", ""),
                "source", right.evidence().getOrDefault("source", "")
        ));
        evidence.put("groupedEvidence", grouped);
        return new DependencyAnalysisResultItem(
                left.projectId(),
                left.sourceRevisionId(),
                left.taskId(),
                left.dependencyAnalysisRunId(),
                left.dependencyType(),
                left.dependencyName(),
                left.dependencyVersion(),
                left.sourceProviderPackage(),
                left.sourceProviderVersion(),
                left.sourceDetectedVersion(),
                left.targetProviderPackage(),
                left.targetProviderVersion(),
                left.targetDetectedVersion(),
                left.providerVersionStatus(),
                left.versionEvidenceConfidence(),
                left.targetMatchStatus(),
                left.riskLevel(),
                left.locationLabel(),
                left.recommendation(),
                left.confidence(),
                evidence
        );
    }

    private boolean shouldReplace(DependencyAnalysisResultItem existing, DependencyAnalysisResultItem candidate) {
        int candidateStatus = statusRank(candidate.targetMatchStatus());
        int existingStatus = statusRank(existing.targetMatchStatus());
        if (candidateStatus != existingStatus) {
            return candidateStatus > existingStatus;
        }
        int candidateSource = sourceRank(candidate);
        int existingSource = sourceRank(existing);
        if (candidateSource != existingSource) {
            return candidateSource > existingSource;
        }
        return confidenceRank(candidate.confidence()) > confidenceRank(existing.confidence());
    }

    private String dedupeKey(DependencyAnalysisResultItem item) {
        String source = normalize(item.evidence() == null ? "" : String.valueOf(item.evidence().get("source")));
        String name = normalize(item.dependencyName());
        if ("repository_bundled_elf".equals(source)) {
            if (isProviderItem(item)) {
                return providerDedupeKey(item);
            }
            return item.dependencyType().name() + "|" + name + "|" + normalize(item.locationLabel());
        }
        if (isProviderItem(item)) {
            return providerDedupeKey(item);
        }
        return item.dependencyType().name() + "|" + name;
    }

    private String providerDedupeKey(DependencyAnalysisResultItem item) {
        Map<String, Object> evidence = item.evidence();
        return item.dependencyType().name()
                + "|" + normalize(String.valueOf(evidence.getOrDefault("sourceOwnerPackage", "")))
                + "|" + majorVersion(String.valueOf(evidence.getOrDefault("sourceOwnerVersion", "")))
                + "|" + normalize(String.valueOf(evidence.getOrDefault("sourceLibraryName", "")))
                + "|" + normalize(String.valueOf(evidence.getOrDefault("sourceVersionEvidence", "")))
                + "|" + normalize(String.valueOf(evidence.getOrDefault("targetProviderPackage", "")))
                + "|" + majorVersion(String.valueOf(evidence.getOrDefault("targetProviderVersion", "")))
                + "|" + normalize(String.valueOf(evidence.getOrDefault("versionRelation", "")));
    }

    private List<String> stringList(Object value) {
        if (value instanceof Collection<?> collection) {
            return collection.stream().map(String::valueOf).toList();
        }
        return List.of();
    }

    private List<Object> objectList(Object value) {
        if (value instanceof Collection<?> collection) {
            return new ArrayList<>(collection.stream().toList());
        }
        return new ArrayList<>();
    }

    private int statusRank(DependencyTargetMatchStatus status) {
        return switch (status) {
            case SAME_MAJOR -> 12;
            case TARGET_NEWER -> 11;
            case TARGET_OLDER -> 10;
            case TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED -> 9;
            case NO_TARGET_VERSION_FOUND -> 8;
            case TARGET_INSTALLED -> 7;
            case PROVIDES_MATCH -> 6;
            case REPO_AVAILABLE -> 5;
            case VERSION_MISMATCH -> 4;
            case SOURCE_BUILD_REQUIRED -> 3;
            case MISSING -> 2;
            case MANUAL_CONFIRM_REQUIRED -> 1;
        };
    }

    private int sourceRank(DependencyAnalysisResultItem item) {
        String source = normalize(item.evidence() == null ? "" : String.valueOf(item.evidence().get("source")));
        return switch (source) {
            case "strace_execve_tool", "strace_execve_link_library" -> 80;
            case "compile_database_compiler", "compile_database_link_library" -> 70;
            case "elf_needed", "elf_soname", "runtime_loader_error" -> 60;
            case "missing_header", "pkg_config" -> 50;
            case "build_system_hint", "build_ninja" -> 40;
            case "tool_pattern" -> 10;
            default -> 20;
        };
    }

    private int confidenceRank(DependencyConfidence confidence) {
        return switch (confidence) {
            case HIGH -> 4;
            case MEDIUM -> 3;
            case OBSERVED -> 2;
            case LOW -> 1;
        };
    }

    private Map<String, Object> evidence(String source, String snippet) {
        return evidence(source, snippet, Map.of(), Map.of());
    }

    private Map<String, Object> evidence(String source, String snippet, Map<String, Object> matchEvidence, Map<String, ?> extra) {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("source", source);
        value.put("snippet", sanitize(snippet));
        if (matchEvidence != null && !matchEvidence.isEmpty()) {
            value.put("targetMatchEvidence", matchEvidence);
        }
        if (extra != null) {
            extra.forEach((key, item) -> value.put(key, item instanceof String text ? sanitize(text) : item));
        }
        return value;
    }

    private Map<String, Object> mergeExtra(Map<String, ?> left, Map<String, ?> right) {
        Map<String, Object> value = new LinkedHashMap<>();
        if (left != null) {
            left.forEach(value::put);
        }
        if (right != null) {
            right.forEach(value::put);
        }
        return value;
    }

    private String sanitize(String value) {
        if (value == null) {
            return "";
        }
        return value.replaceAll("(?i)(password|passphrase|token|secret|private[_-]?key)=\\S+", "$1=***");
    }

    private String safe(String value) {
        return value == null ? "" : value;
    }

    private static String sanitizeStatic(String value) {
        if (value == null) {
            return "";
        }
        return value.replaceAll("(?i)(password|passphrase|token|secret|private[_-]?key)=\\S+", "$1=***");
    }

    private static String safeStatic(String value) {
        return value == null ? "" : value;
    }

    private static SourcePackage parseSourcePackageStatic(String ownerText) {
        String raw = safeStatic(ownerText).trim();
        if (raw.isBlank() || raw.contains("is not owned by")) {
            return SourcePackage.empty();
        }
        String value = raw;
        int colon = value.indexOf(':');
        if (colon > 0 && !value.substring(0, colon).contains("-")) {
            value = value.substring(colon + 1).trim();
        }
        value = value.replaceFirst("\\.(x86_64|riscv64|aarch64|noarch|i[3-6]86)$", "");
        Matcher rpm = Pattern.compile("^(.+)-([^-]+)-([^-]+)$").matcher(value);
        if (rpm.matches()) {
            return new SourcePackage(rpm.group(1), rpm.group(2) + "-" + rpm.group(3), "package-database");
        }
        return new SourcePackage(value, "", "package-database");
    }

    private boolean isInternalTool(String tool) {
        return INTERNAL_OBSERVABILITY_TOOLS.contains(normalize(tool));
    }

    private Set<String> compilerBuiltinMacros(String text) {
        Set<String> macros = new LinkedHashSet<>(COMMON_COMPILER_BUILTIN_MACROS);
        Matcher matcher = COMPILER_BUILTIN_MACROS_PATTERN.matcher(text);
        while (matcher.find()) {
            Map<String, String> properties = properties(matcher.group(2));
            macros.addAll(csv(properties.get("macros")));
        }
        return macros;
    }

    private boolean isCompilerBuiltinMacro(String macro, Set<String> compilerBuiltinMacros) {
        String name = safe(macro).split("=", 2)[0].trim();
        return compilerBuiltinMacros.contains(name);
    }

    private String macroSource(String macro, Set<String> compilerBuiltinMacros) {
        String name = safe(macro).split("=", 2)[0].trim();
        if (!compilerBuiltinMacros.contains(name)) {
            return "";
        }
        if (COMMON_COMPILER_BUILTIN_MACROS.contains(name)) {
            return "static_builtin_catalog";
        }
        return "collected_compiler_builtin";
    }

    private Map<String, List<CMakeCompilerFlagProbe>> cmakeCompilerFlagProbes(String text) {
        Map<String, List<CMakeCompilerFlagProbe>> probes = new LinkedHashMap<>();
        Matcher matcher = CMAKE_COMPILER_FLAG_PROBE_PATTERN.matcher(text);
        while (matcher.find()) {
            String variable = macroName(matcher.group(1));
            Map<String, String> props = properties(matcher.group(2));
            String flag = props.getOrDefault("flag", "");
            if (variable.isBlank() || flag.isBlank()) {
                continue;
            }
            probes.computeIfAbsent(variable, ignored -> new ArrayList<>())
                    .add(new CMakeCompilerFlagProbe(
                            props.getOrDefault("language", ""),
                            flag,
                            props.getOrDefault("file", ""),
                            props.getOrDefault("function", "")
                    ));
        }
        return probes;
    }

    private MacroClassification classifyMacro(
            String define,
            Set<String> compilerBuiltinMacros,
            Map<String, List<CMakeCompilerFlagProbe>> cmakeCompilerFlagProbes
    ) {
        String name = macroName(define);
        List<CMakeCompilerFlagProbe> probes = cmakeCompilerFlagProbes.getOrDefault(name, List.of());
        if (!probes.isEmpty()) {
            Set<String> flags = new LinkedHashSet<>();
            List<Map<String, String>> candidates = new ArrayList<>();
            for (CMakeCompilerFlagProbe probe : probes) {
                flags.add(probe.flag());
                candidates.add(Map.of(
                        "compilerFlag", probe.flag(),
                        "probeFile", probe.file(),
                        "probeLanguage", probe.language(),
                        "probeFunction", probe.function()
                ));
            }
            if (flags.size() == 1) {
                CMakeCompilerFlagProbe probe = probes.getFirst();
                return new MacroClassification(
                        DependencyTargetMatchStatus.TARGET_INSTALLED,
                        DependencyRiskLevel.LOW,
                        DependencyConfidence.HIGH,
                        "compiler_flag_probe",
                        "CMake 检测调用确认该宏对应编译器参数 " + probe.flag() + "，通常应归属到当前编译器能力",
                        Map.of(
                                "macroKind", "compiler_flag_probe",
                                "macroSource", "",
                                "compilerFlag", probe.flag(),
                                "probeSource", "cmake_check_compiler_flag",
                                "probeFile", probe.file(),
                                "probeLanguage", probe.language(),
                                "probeFunction", probe.function(),
                                "confidenceSource", "cmake_compiler_flag_probe"
                        )
                );
            }
            return new MacroClassification(
                    DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED,
                    DependencyRiskLevel.COMMENT,
                    DependencyConfidence.OBSERVED,
                    "compiler_flag_probe_conflict",
                    "CMake 检测调用中同一宏变量对应多个编译器参数，需人工确认真实含义",
                    Map.of(
                            "macroKind", "compiler_flag_probe_conflict",
                            "macroSource", "",
                            "probeSource", "cmake_check_compiler_flag",
                            "conflictCandidates", candidates,
                            "confidenceSource", "cmake_compiler_flag_probe_conflict"
                    )
            );
        }
        if (isCompilerBuiltinMacro(define, compilerBuiltinMacros)) {
            return new MacroClassification(
                    DependencyTargetMatchStatus.TARGET_INSTALLED,
                    DependencyRiskLevel.LOW,
                    DependencyConfidence.OBSERVED,
                    "compiler_builtin",
                    "宏定义匹配编译器内置宏，通常不需要作为迁移依赖处理",
                    Map.of(
                            "macroKind", "compiler_builtin",
                            "macroSource", macroSource(define, compilerBuiltinMacros),
                            "compilerFlag", "",
                            "confidenceSource", "compiler_builtin_macro"
                    )
            );
        }
        return new MacroClassification(
                DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED,
                DependencyRiskLevel.COMMENT,
                DependencyConfidence.OBSERVED,
                "project_or_build_custom",
                "观测到自定义宏定义，通常不是外部依赖，但会影响构建条件和兼容路径",
                Map.of(
                        "macroKind", "project_or_build_custom",
                        "macroSource", "",
                        "compilerFlag", "",
                        "confidenceSource", "no_dynamic_probe_or_builtin_match"
                )
        );
    }

    private String macroName(String macro) {
        return safe(macro).split("=", 2)[0].trim();
    }

    private boolean isTrivialPath(String path) {
        String value = safe(path).trim();
        return value.isBlank() || ".".equals(value) || "./".equals(value);
    }

    private String fileName(String relativePath) {
        if (relativePath == null || relativePath.isBlank()) {
            return "unknown";
        }
        int slash = Math.max(relativePath.lastIndexOf('/'), relativePath.lastIndexOf('\\'));
        return slash >= 0 ? relativePath.substring(slash + 1) : relativePath;
    }

    private String firstNonBlank(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                return value;
            }
        }
        return "";
    }

    private String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private Map<String, String> properties(String text) {
        Map<String, String> value = new LinkedHashMap<>();
        if (text == null || text.isBlank()) {
            return value;
        }
        for (String part : text.split("\\t")) {
            int idx = part.indexOf('=');
            if (idx > 0) {
                value.put(part.substring(0, idx), part.substring(idx + 1));
            }
        }
        return value;
    }

    private List<String> csv(String text) {
        if (text == null || text.isBlank()) {
            return List.of();
        }
        return java.util.Arrays.stream(text.split(","))
                .map(String::trim)
                .filter(value -> !value.isBlank())
                .distinct()
                .toList();
    }

    private String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    private String libraryStem(String name) {
        String value = normalize(fileName(name));
        while (value.matches(".*\\.so(\\.\\d+)+$")) {
            value = value.replaceFirst("\\.so(\\.\\d+)+$", ".so");
        }
        return value;
    }

    private String libraryVersionEvidence(String name) {
        String value = normalize(fileName(name));
        Matcher matcher = Pattern.compile("\\.so\\.(\\d+(?:\\.\\d+)*)").matcher(value);
        if (matcher.find()) {
            return matcher.group(1);
        }
        return "";
    }

    private String majorVersion(String version) {
        String value = safe(version).trim();
        if (value.isBlank()) {
            return "";
        }
        Matcher epochMatcher = Pattern.compile("^(?:\\d+:)?(\\d+)").matcher(value);
        if (epochMatcher.find()) {
            return epochMatcher.group(1);
        }
        Matcher digitMatcher = Pattern.compile("(\\d+)").matcher(value);
        return digitMatcher.find() ? digitMatcher.group(1) : "";
    }

    private int compareMajorVersion(String sourceVersion, String targetVersion) {
        String sourceMajor = majorVersion(sourceVersion);
        String targetMajor = majorVersion(targetVersion);
        if (sourceMajor.isBlank() || targetMajor.isBlank()) {
            return Integer.MIN_VALUE;
        }
        try {
            return Integer.compare(Integer.parseInt(targetMajor), Integer.parseInt(sourceMajor));
        } catch (NumberFormatException ex) {
            return targetMajor.compareTo(sourceMajor);
        }
    }

    private SourcePackage parseSourcePackage(String ownerText) {
        String raw = safe(ownerText).trim();
        if (raw.isBlank() || raw.contains("is not owned by")) {
            return SourcePackage.empty();
        }
        String value = raw;
        int colon = value.indexOf(':');
        if (colon > 0 && !value.substring(0, colon).contains("-")) {
            value = value.substring(colon + 1).trim();
        }
        value = value.replaceFirst("\\.(x86_64|riscv64|aarch64|noarch|i[3-6]86)$", "");
        Matcher rpm = Pattern.compile("^(.+)-([^-]+)-([^-]+)$").matcher(value);
        if (rpm.matches()) {
            return new SourcePackage(rpm.group(1), rpm.group(2) + "-" + rpm.group(3), "package-database");
        }
        return new SourcePackage(value, "", "package-database");
    }

    private List<String> toolAliases(String name) {
        return switch (normalize(name)) {
            case "cc" -> List.of("gcc", "clang");
            case "c++" -> List.of("g++", "clang++");
            case "ar", "ld", "as", "ranlib", "strip", "objcopy", "objdump" -> List.of("binutils");
            case "ninja" -> List.of("ninja-build", "python3-ninja");
            case "rpmbuild" -> List.of("rpm-build", "rpm");
            case "configure" -> List.of("autoconf");
            default -> List.of();
        };
    }

    private String sourceProviderPackage(Map<String, Object> sourceProvider) {
        return stringValue(sourceProvider.get("sourceProviderPackage"));
    }

    private List<String> equivalentCompilerTools(String name, String sourceProviderPackage) {
        String normalizedName = normalize(name);
        String normalizedProvider = normalize(sourceProviderPackage);
        if (Set.of("c++", "g++", "clang++").contains(normalizedName)) {
            if (normalizedProvider.contains("clang")) {
                return List.of("c++", "clang++");
            }
            if (normalizedProvider.contains("gcc") || normalizedProvider.contains("g++")) {
                return List.of("c++", "g++");
            }
            return List.of("c++", "g++", "clang++");
        }
        if (Set.of("cc", "gcc", "clang").contains(normalizedName)) {
            if (normalizedProvider.contains("clang")) {
                return List.of("cc", "clang");
            }
            if (normalizedProvider.contains("gcc")) {
                return List.of("cc", "gcc");
            }
            return List.of("cc", "gcc", "clang");
        }
        return List.of();
    }

    private String libraryPackageStem(String libraryName) {
        String value = normalize(libraryName);
        if (value.endsWith(".so")) {
            return value.substring(0, value.length() - 3);
        }
        return value;
    }

    private List<String> libraryProviderAliases(String name) {
        return switch (libraryPackageStem(libraryStem(name))) {
            case "libgcc", "libgcc_s" -> List.of("libgcc", "gcc");
            case "libstdc++" -> List.of("libstdc++", "gcc-c++", "gcc");
            case "libc" -> List.of("glibc");
            default -> List.of();
        };
    }

    private record CMakeCompilerFlagProbe(
            String language,
            String flag,
            String file,
            String function
    ) {
    }

    private record MacroClassification(
            DependencyTargetMatchStatus status,
            DependencyRiskLevel risk,
            DependencyConfidence confidence,
            String macroKind,
            String recommendation,
            Map<String, Object> evidence
    ) {
        String recommendation(String source) {
            if ("project_or_build_custom".equals(macroKind)) {
                return source + " 中出现自定义宏定义，通常不是外部依赖，但会影响构建条件和兼容路径";
            }
            return recommendation;
        }
    }

    private record SourcePackage(
            String name,
            String version,
            String source
    ) {
        static SourcePackage empty() {
            return new SourcePackage("", "", "");
        }

        boolean present() {
            return !name.isBlank();
        }
    }

    private final class BuildProducedElfIndex {
        private final Set<String> paths = new LinkedHashSet<>();
        private final Set<String> libraryKeys = new LinkedHashSet<>();

        BuildProducedElfIndex(String text, String compileDatabaseJson) {
            CompileObjectIndex compileObjectIndex = new CompileObjectIndex(compileDatabaseJson);
            Matcher produced = BUILD_PRODUCED_ELF_PATTERN.matcher(text);
            while (produced.find()) {
                String path = produced.group(1);
                paths.add(normalize(path));
                libraryKeys.addAll(libraryKeys(path));
            }
            Matcher soname = ELF_SONAME_PATTERN.matcher(text);
            while (soname.find()) {
                if (isProducedPath(soname.group(1))) {
                    libraryKeys.addAll(libraryKeys(soname.group(2)));
                }
            }
            Matcher linkedLibrary = LINKING_SHARED_LIBRARY_PATTERN.matcher(text);
            while (linkedLibrary.find()) {
                libraryKeys.addAll(libraryKeys(linkedLibrary.group(1)));
            }
            for (String line : text.split("\\R")) {
                if (compileObjectIndex.referencesObject(line)) {
                    for (String output : compileObjectIndex.linkOutputs(line)) {
                        paths.add(normalize(output));
                        libraryKeys.addAll(libraryKeys(output));
                    }
                }
            }
        }

        boolean isProducedPath(String path) {
            return paths.contains(normalize(path));
        }

        boolean isProducedLibrary(String libraryName) {
            Set<String> candidates = libraryKeys(libraryName);
            for (String candidate : candidates) {
                if (libraryKeys.contains(candidate)) {
                    return true;
                }
            }
            return false;
        }

        private Set<String> libraryKeys(String value) {
            String name = normalize(fileName(value));
            if (!name.contains(".so")) {
                return Set.of();
            }
            Set<String> keys = new LinkedHashSet<>();
            keys.add(name);
            keys.add(libraryStem(name));
            Matcher versioned = Pattern.compile("^(.*?\\.so)\\.([0-9][0-9.]*)$").matcher(name);
            if (versioned.matches()) {
                String current = versioned.group(1);
                keys.add(current);
                for (String part : versioned.group(2).split("\\.")) {
                    if (!part.isBlank()) {
                        current = current + "." + part;
                        keys.add(current);
                    }
                }
            }
            keys.remove("");
            return keys;
        }
    }

    private final class CompileObjectIndex {
        private final Set<String> objects = new LinkedHashSet<>();
        private final Set<String> objectNames = new LinkedHashSet<>();

        CompileObjectIndex(String compileDatabaseJson) {
            if (compileDatabaseJson == null || compileDatabaseJson.isBlank()) {
                return;
            }
            try {
                JsonNode root = OBJECT_MAPPER.readTree(compileDatabaseJson);
                if (!root.isArray()) {
                    return;
                }
                int count = 0;
                for (JsonNode entry : root) {
                    if (count++ >= MAX_COMPILE_DATABASE_ENTRIES) {
                        break;
                    }
                    String command = compileCommand(entry);
                    if (command.isBlank()) {
                        continue;
                    }
                    String output = outputObject(command);
                    if (output.isBlank() || !isObjectOutput(output)) {
                        continue;
                    }
                    objects.add(normalizePath(output));
                    objectNames.add(normalize(fileName(output)));
                }
            } catch (Exception ignored) {
                objects.clear();
                objectNames.clear();
            }
        }

        boolean referencesObject(String line) {
            if (objects.isEmpty() || line == null || line.isBlank()) {
                return false;
            }
            String normalizedLine = normalizePath(line);
            for (String object : objects) {
                if (normalizedLine.contains(object)) {
                    return true;
                }
            }
            for (String objectName : objectNames) {
                if (!objectName.isBlank() && normalizedLine.contains(objectName)) {
                    return true;
                }
            }
            return false;
        }

        List<String> linkOutputs(String line) {
            List<String> outputs = new ArrayList<>();
            List<String> parts = splitCommand(line);
            for (int i = 0; i < parts.size(); i++) {
                String part = parts.get(i);
                String output = "";
                if ("-o".equals(part) && i + 1 < parts.size()) {
                    output = parts.get(i + 1);
                } else if (part.startsWith("-o") && part.length() > 2) {
                    output = part.substring(2);
                }
                if (!output.isBlank() && isElfLikeOutput(output)) {
                    outputs.add(output);
                }
            }
            return outputs;
        }

        private String compileCommand(JsonNode entry) {
            JsonNode arguments = entry.get("arguments");
            if (arguments != null && arguments.isArray()) {
                List<String> parts = new ArrayList<>();
                int count = 0;
                for (JsonNode argument : arguments) {
                    if (count++ >= 512) {
                        break;
                    }
                    parts.add(argument.asText(""));
                }
                return String.join(" ", parts);
            }
            String command = entry.path("command").asText("");
            if (command.length() > MAX_COMMAND_LENGTH) {
                return command.substring(0, MAX_COMMAND_LENGTH);
            }
            return command;
        }

        private String outputObject(String command) {
            List<String> parts = splitCommand(command);
            for (int i = 0; i < parts.size(); i++) {
                String part = parts.get(i);
                if ("-o".equals(part) && i + 1 < parts.size()) {
                    return parts.get(i + 1);
                }
                if (part.startsWith("-o") && part.length() > 2) {
                    return part.substring(2);
                }
            }
            return "";
        }

        private boolean isObjectOutput(String value) {
            String normalized = normalize(value);
            return normalized.endsWith(".o") || normalized.endsWith(".obj");
        }

        private boolean isElfLikeOutput(String value) {
            String name = normalize(fileName(value));
            return name.contains(".so") || !name.contains(".");
        }

        private String normalizePath(String value) {
            return normalize(value).replace('\\', '/');
        }

        private List<String> splitCommand(String command) {
            if (command == null || command.isBlank()) {
                return List.of();
            }
            List<String> parts = new ArrayList<>();
            Matcher matcher = Pattern.compile("\"((?:\\\\.|[^\"])*)\"|'([^']*)'|(\\S+)").matcher(command);
            while (matcher.find() && parts.size() < 1024) {
                String value = firstNonBlank(matcher.group(1), matcher.group(2), matcher.group(3));
                if (!value.isBlank()) {
                    parts.add(value);
                }
            }
            return parts;
        }
    }

    private final class SourceOwnerIndex {
        private final Map<String, SourcePackage> byPath = new LinkedHashMap<>();
        private final Map<String, ResolvedNeededLibrary> resolvedByPathAndSoname = new LinkedHashMap<>();
        private final Map<String, ResolvedNeededLibrary> resolvedBySoname = new LinkedHashMap<>();

        SourceOwnerIndex(String text) {
            Matcher owner = OWNER_PACKAGE_PATTERN.matcher(text);
            while (owner.find()) {
                SourcePackage sourcePackage = parseSourcePackage(owner.group(2));
                if (sourcePackage.present()) {
                    byPath.put(normalize(owner.group(1)), sourcePackage);
                }
            }
            Matcher resolved = RESOLVED_NEEDED_LIBRARY_PATTERN.matcher(text);
            while (resolved.find()) {
                String elfPath = resolved.group(1);
                Map<String, String> props = properties(resolved.group(2));
                ResolvedNeededLibrary library = ResolvedNeededLibrary.from(elfPath, props);
                if (!library.soname().isBlank()) {
                    resolvedByPathAndSoname.put(resolvedKey(elfPath, library.soname()), library);
                    resolvedBySoname.putIfAbsent(normalize(library.soname()), library);
                }
            }
        }

        SourcePackage owner(String path) {
            return byPath.getOrDefault(normalize(path), SourcePackage.empty());
        }

        ResolvedNeededLibrary resolvedNeeded(String elfPath, String soname) {
            ResolvedNeededLibrary exact = resolvedByPathAndSoname.get(resolvedKey(elfPath, soname));
            if (exact != null) {
                return exact;
            }
            return resolvedBySoname.getOrDefault(normalize(soname), ResolvedNeededLibrary.empty(soname));
        }

        private String resolvedKey(String elfPath, String soname) {
            return normalize(elfPath) + "|" + normalize(soname);
        }
    }

    private record ResolvedNeededLibrary(
            String elfPath,
            String soname,
            String path,
            SourcePackage owner,
            String resolver,
            String candidates,
            String warning
    ) {
        static ResolvedNeededLibrary empty(String soname) {
            return new ResolvedNeededLibrary("", safeStatic(soname), "", SourcePackage.empty(), "", "", "");
        }

        static ResolvedNeededLibrary from(String elfPath, Map<String, String> props) {
            String ownerText = props.getOrDefault("ownerPackage", "");
            return new ResolvedNeededLibrary(
                    safeStatic(elfPath),
                    safeStatic(props.get("soname")),
                    safeStatic(props.get("path")),
                    parseSourcePackageStatic(ownerText),
                    safeStatic(props.get("resolver")),
                    safeStatic(props.get("candidates")),
                    safeStatic(props.get("warning"))
            );
        }

        SourcePackage sourcePackage(SourcePackage fallback) {
            return owner.present() ? owner : fallback;
        }

        String sourcePath(String fallback) {
            return path.isBlank() ? fallback : path;
        }

        Map<String, Object> evidence() {
            Map<String, Object> value = new LinkedHashMap<>();
            put(value, "resolvedSourceLibraryPath", path);
            put(value, "resolvedSourceLibrarySoname", soname);
            put(value, "sourceLibraryResolver", resolver);
            put(value, "sourceLibraryCandidates", candidates);
            put(value, "sourceLibraryResolutionWarning", warning);
            if (owner.present()) {
                put(value, "resolvedSourceOwnerPackage", owner.name());
                put(value, "resolvedSourceOwnerVersion", owner.version());
                put(value, "resolvedSourceOwnerSource", owner.source());
            }
            return value;
        }

        private static void put(Map<String, Object> target, String key, String value) {
            if (value != null && !value.isBlank()) {
                target.put(key, sanitizeStatic(value));
            }
        }
    }

    private record ProviderMatch(
            String libraryName,
            String sourceLibraryPath,
            String sourceSoname,
            String sourceOwnerPackage,
            String sourceOwnerVersion,
            String sourceOwnerSource,
            String sourceVersionEvidence,
            String targetProviderPackage,
            String targetProviderVersion,
            String targetProviderSource,
            DependencyTargetMatchStatus versionRelation,
            DependencyRiskLevel riskLevel,
            DependencyConfidence confidence,
            String riskMappingRule,
            Map<String, Object> matchEvidence,
            List<String> evidencePaths
    ) {
    }

    private record ProviderFields(
            String sourceProviderPackage,
            String sourceProviderVersion,
            String sourceDetectedVersion,
            String targetProviderPackage,
            String targetProviderVersion,
            String targetDetectedVersion,
            String providerVersionStatus,
            String versionEvidenceConfidence
    ) {
        static ProviderFields from(String dependencyVersion,
                                   DependencyTargetMatchStatus status,
                                   Map<String, Object> evidence) {
            Map<?, ?> evidenceMap = evidence == null ? Map.of() : evidence;
            Map<?, ?> target = evidenceMap.get("targetMatchEvidence") instanceof Map<?, ?> map ? map : Map.of();
            Map<?, ?> metadata = target.get("metadata") instanceof Map<?, ?> map ? map : Map.of();
            String sourceProviderPackage = firstNonBlank(
                    value(evidenceMap.get("sourceProviderPackage")),
                    value(evidenceMap.get("sourceOwnerPackage"))
            );
            String sourceProviderVersion = firstNonBlank(
                    value(evidenceMap.get("sourceProviderVersion")),
                    value(evidenceMap.get("sourceOwnerVersion"))
            );
            String sourceDetectedVersion = firstNonBlank(
                    value(evidenceMap.get("sourceDetectedVersion")),
                    value(evidenceMap.get("sourceVersionEvidence")),
                    sourceProviderVersion
            );
            String targetProviderPackage = firstNonBlank(
                    value(evidenceMap.get("targetProviderPackage")),
                    value(target.get("providerPackage")),
                    value(metadata.get("ownerPackage")),
                    value(metadata.get("normalizedPackage")),
                    value(metadata.get("packageName")),
                    value(target.get("name"))
            );
            String targetProviderVersion = firstNonBlank(
                    value(evidenceMap.get("targetProviderVersion")),
                    value(metadata.get("ownerVersion")),
                    value(metadata.get("packageVersion")),
                    value(metadata.get("version")),
                    value(target.get("version"))
            );
            String targetDetectedVersion = firstNonBlank(
                    value(evidenceMap.get("targetDetectedVersion")),
                    value(metadata.get("versionText")),
                    targetProviderVersion
            );
            String providerVersionStatus = firstNonBlank(
                    value(evidenceMap.get("providerVersionStatus")),
                    value(evidenceMap.get("versionRelation")),
                    isProviderStatus(status) ? status.name() : "",
                    inferredProviderVersionStatus(
                            sourceProviderPackage,
                            firstNonBlank(sourceProviderVersion, sourceDetectedVersion, dependencyVersion),
                            targetProviderPackage,
                            firstNonBlank(targetProviderVersion, targetDetectedVersion)
                    )
            );
            String versionEvidenceConfidence = evidenceConfidence(
                    sourceProviderPackage,
                    sourceProviderVersion,
                    sourceDetectedVersion,
                    targetProviderPackage,
                    targetProviderVersion,
                    targetDetectedVersion,
                    dependencyVersion
            );
            return new ProviderFields(
                    sourceProviderPackage,
                    sourceProviderVersion,
                    sourceDetectedVersion,
                    targetProviderPackage,
                    targetProviderVersion,
                    targetDetectedVersion,
                    providerVersionStatus.isBlank() ? null : providerVersionStatus,
                    versionEvidenceConfidence
            );
        }

        private static boolean isProviderStatus(DependencyTargetMatchStatus status) {
            return switch (status) {
                case SAME_MAJOR, TARGET_NEWER, TARGET_OLDER, TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED,
                        NO_TARGET_VERSION_FOUND -> true;
                case TARGET_INSTALLED, REPO_AVAILABLE, PROVIDES_MATCH, VERSION_MISMATCH, SOURCE_BUILD_REQUIRED,
                        MISSING, MANUAL_CONFIRM_REQUIRED -> false;
            };
        }

        private static String evidenceConfidence(String sourceProviderPackage,
                                                 String sourceProviderVersion,
                                                 String sourceDetectedVersion,
                                                 String targetProviderPackage,
                                                 String targetProviderVersion,
                                                 String targetDetectedVersion,
                                                 String dependencyVersion) {
            if ((!sourceProviderPackage.isBlank() && !sourceProviderVersion.isBlank())
                    || (!targetProviderPackage.isBlank() && !targetProviderVersion.isBlank())) {
                return "PACKAGE_OWNER";
            }
            if (!sourceDetectedVersion.isBlank() || !targetDetectedVersion.isBlank()) {
                return "ELF_METADATA";
            }
            if (dependencyVersion != null && !dependencyVersion.isBlank()) {
                return "COMMAND_VERSION";
            }
            return null;
        }

        private static String inferredProviderVersionStatus(String sourceProviderPackage,
                                                            String sourceVersion,
                                                            String targetProviderPackage,
                                                            String targetVersion) {
            if (targetProviderPackage.isBlank() || targetVersion.isBlank()) {
                return "";
            }
            if (sourceProviderPackage.isBlank()) {
                return "";
            }
            int comparison = compareMajorVersion(sourceVersion, targetVersion);
            if (comparison == 0) {
                return DependencyTargetMatchStatus.SAME_MAJOR.name();
            }
            if (comparison > 0) {
                return DependencyTargetMatchStatus.TARGET_NEWER.name();
            }
            if (comparison < 0 && comparison != Integer.MIN_VALUE) {
                return DependencyTargetMatchStatus.TARGET_OLDER.name();
            }
            return DependencyTargetMatchStatus.NO_TARGET_VERSION_FOUND.name();
        }

        private static String majorVersion(String version) {
            String value = value(version);
            if (value.isBlank()) {
                return "";
            }
            Matcher epochMatcher = Pattern.compile("^(?:\\d+:)?(\\d+)").matcher(value);
            if (epochMatcher.find()) {
                return epochMatcher.group(1);
            }
            Matcher digitMatcher = Pattern.compile("(\\d+)").matcher(value);
            return digitMatcher.find() ? digitMatcher.group(1) : "";
        }

        private static int compareMajorVersion(String sourceVersion, String targetVersion) {
            String sourceMajor = majorVersion(sourceVersion);
            String targetMajor = majorVersion(targetVersion);
            if (sourceMajor.isBlank() || targetMajor.isBlank()) {
                return Integer.MIN_VALUE;
            }
            try {
                return Integer.compare(Integer.parseInt(targetMajor), Integer.parseInt(sourceMajor));
            } catch (NumberFormatException ex) {
                return targetMajor.compareTo(sourceMajor);
            }
        }

        private static String value(Object value) {
            if (value == null) {
                return "";
            }
            String text = String.valueOf(value).trim();
            return "null".equalsIgnoreCase(text) ? "" : text;
        }

        private static String firstNonBlank(String... values) {
            for (String value : values) {
                if (value != null && !value.isBlank()) {
                    return value;
                }
            }
            return "";
        }
    }

    private final class SourceCapabilityIndex {
        private final Map<String, DependencyAnalysisRepository.TargetComponentView> tools = new LinkedHashMap<>();
        private final Map<String, DependencyAnalysisRepository.TargetComponentView> packages = new LinkedHashMap<>();
        private final Map<String, DependencyAnalysisRepository.TargetComponentView> libraries = new LinkedHashMap<>();

        SourceCapabilityIndex(Collection<DependencyAnalysisRepository.TargetComponentView> components) {
            if (components == null) {
                return;
            }
            for (DependencyAnalysisRepository.TargetComponentView component : components) {
                String source = normalize(component.source());
                String type = normalize(component.componentType());
                String name = normalize(component.name());
                String path = normalize(component.path());
                if ("tool_version".equals(source) || "tool".equals(type)) {
                    tools.putIfAbsent(name, component);
                    tools.putIfAbsent(fileName(path), component);
                } else if ("installed_package".equals(source) || "package".equals(type)) {
                    packages.putIfAbsent(name, component);
                } else if ("installed_library".equals(source) || "native_file".equals(source) || "library".equals(type)) {
                    libraries.putIfAbsent(libraryStem(firstNonBlank(component.name(), component.path())), component);
                    libraries.putIfAbsent(path, component);
                    String ownerPackage = stringValue(component.metadata() == null ? "" : component.metadata().get("ownerPackage"));
                    if (!ownerPackage.isBlank()) {
                        packages.putIfAbsent(normalize(ownerPackage), component);
                    }
                }
            }
        }

        Map<String, Object> toolEvidence(String name) {
            return toolEvidence(name, "");
        }

        Map<String, Object> toolEvidence(String name, String path) {
            DependencyAnalysisRepository.TargetComponentView component = tools.get(normalize(name));
            if (component == null && path != null && !path.isBlank()) {
                component = tools.get(fileName(path));
            }
            if (component == null) {
                for (String alias : toolAliases(name)) {
                    component = tools.get(normalize(alias));
                    if (component == null) {
                        component = packages.get(normalize(alias));
                    }
                    if (component != null) {
                        break;
                    }
                }
            }
            return sourceProviderEvidence(component, "source_tool");
        }

        Map<String, Object> libraryEvidence(String name) {
            DependencyAnalysisRepository.TargetComponentView component = libraries.get(libraryStem(name));
            if (component == null) {
                component = packages.get(libraryPackageStem(libraryStem(name)));
            }
            if (component == null) {
                for (String alias : libraryProviderAliases(name)) {
                    component = libraries.get(libraryStem(alias));
                    if (component == null) {
                        component = packages.get(normalize(alias));
                    }
                    if (component != null) {
                        break;
                    }
                }
            }
            return sourceProviderEvidence(component, "source_library");
        }

        private Map<String, Object> sourceProviderEvidence(DependencyAnalysisRepository.TargetComponentView component,
                                                           String source) {
            if (component == null) {
                return Map.of();
            }
            Map<String, Object> value = new LinkedHashMap<>();
            Map<String, Object> metadata = component.metadata() == null ? Map.of() : component.metadata();
            putIfPresent(value, "sourceProviderPackage", firstNonBlank(
                    stringValue(metadata.get("ownerPackage")),
                    stringValue(metadata.get("normalizedPackage")),
                    stringValue(metadata.get("packageName")),
                    component.name()
            ));
            putIfPresent(value, "sourceProviderVersion", firstNonBlank(
                    stringValue(metadata.get("ownerVersion")),
                    stringValue(metadata.get("packageVersion")),
                    component.version()
            ));
            putIfPresent(value, "sourceDetectedVersion", firstNonBlank(
                    stringValue(metadata.get("versionText")),
                    component.version()
            ));
            putIfPresent(value, "sourceProviderSource", source);
            putIfPresent(value, "sourceProviderScanner", stringValue(metadata.get("providerScanner")));
            return value;
        }

        private void putIfPresent(Map<String, Object> target, String key, String value) {
            if (value != null && !value.isBlank()) {
                target.put(key, sanitize(value));
            }
        }
    }

    private final class TargetCapabilityIndex {
        private final boolean available;
        private final Map<String, DependencyAnalysisRepository.TargetComponentView> installedTools = new LinkedHashMap<>();
        private final Map<String, DependencyAnalysisRepository.TargetComponentView> installedPackages = new LinkedHashMap<>();
        private final Map<String, DependencyAnalysisRepository.TargetComponentView> repositoryPackages = new LinkedHashMap<>();
        private final Map<String, DependencyAnalysisRepository.TargetComponentView> installedLibraries = new LinkedHashMap<>();
        private final Map<String, DependencyAnalysisRepository.TargetComponentView> repositoryProvides = new LinkedHashMap<>();
        private final List<DependencyAnalysisRepository.TargetComponentView> allComponents = new ArrayList<>();

        TargetCapabilityIndex(Collection<DependencyAnalysisRepository.TargetComponentView> components) {
            this.available = components != null && !components.isEmpty();
            if (components != null) {
                allComponents.addAll(components);
                for (DependencyAnalysisRepository.TargetComponentView component : components) {
                    String name = normalize(component.name());
                    String path = normalize(component.path());
                    String source = normalize(component.source());
                    String type = normalize(component.componentType());
                    if ("tool_version".equals(source) || "tool".equals(type)) {
                        installedTools.putIfAbsent(name, component);
                    } else if ("installed_package".equals(source)) {
                        installedPackages.putIfAbsent(name, component);
                    } else if ("repository_package".equals(source)) {
                        repositoryPackages.putIfAbsent(name, component);
                    } else if ("installed_library".equals(source) || "native_file".equals(source)) {
                        installedLibraries.putIfAbsent(libraryStem(firstNonBlank(component.name(), component.path())), component);
                        installedLibraries.putIfAbsent(path, component);
                    } else if ("repository_provide".equals(source)) {
                        indexRepositoryProvide(component);
                        repositoryProvides.putIfAbsent(path, component);
                    }
                }
            }
        }

        private void indexRepositoryProvide(DependencyAnalysisRepository.TargetComponentView component) {
            putRepositoryProvideKey(firstNonBlank(component.path(), component.name()), component);
            putRepositoryProvideKey(component.name(), component);
            if (component.metadata() == null || component.metadata().isEmpty()) {
                return;
            }
            putRepositoryProvideKey(stringValue(component.metadata().get("queryValue")), component);
            putRepositoryProvideKey(stringValue(component.metadata().get("queryPattern")), component);
            putRepositoryProvideKey(stringValue(component.metadata().get("path")), component);
            putRepositoryProvideKey(stringValue(component.metadata().get("normalizedName")), component);
        }

        private void putRepositoryProvideKey(String value, DependencyAnalysisRepository.TargetComponentView component) {
            String normalized = normalize(value);
            if (normalized.isBlank()) {
                return;
            }
            repositoryProvides.putIfAbsent(libraryStem(normalized), component);
            repositoryProvides.putIfAbsent(normalized, component);
            repositoryProvides.putIfAbsent(fileName(normalized), component);
            String withoutWildcard = normalized.replaceFirst("^\\*/", "");
            if (!withoutWildcard.equals(normalized)) {
                repositoryProvides.putIfAbsent(libraryStem(withoutWildcard), component);
                repositoryProvides.putIfAbsent(withoutWildcard, component);
            }
        }

        MatchDecision matchTool(String name) {
            return matchTool(name, "");
        }

        MatchDecision matchTool(String name, String sourceProviderPackage) {
            MatchDecision direct = matchExactToolOrPackage(name);
            if (direct.status() != DependencyTargetMatchStatus.MISSING
                    && direct.status() != DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED) {
                return direct;
            }
            List<String> equivalentTools = equivalentCompilerTools(name, sourceProviderPackage);
            for (String equivalentTool : equivalentTools) {
                if (normalize(equivalentTool).equals(normalize(name))) {
                    continue;
                }
                MatchDecision equivalentMatch = matchExactToolOrPackage(equivalentTool);
                if (equivalentMatch.status() != DependencyTargetMatchStatus.MISSING
                        && equivalentMatch.status() != DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED) {
                    return equivalentMatch.withAlias(name, equivalentTool);
                }
            }
            if (!sourceProviderPackage.isBlank()) {
                MatchDecision providerMatch = matchExactPackage(sourceProviderPackage);
                if (providerMatch.status() != DependencyTargetMatchStatus.MISSING
                        && providerMatch.status() != DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED) {
                    return providerMatch.withSourceProviderPackage(name, sourceProviderPackage);
                }
            }
            if (equivalentTools.isEmpty()) {
                for (String alias : toolAliases(name)) {
                    MatchDecision aliasMatch = TOOLCHAIN_COMPONENTS.contains(normalize(name))
                            ? matchExactPackage(alias)
                            : matchExactToolOrPackage(alias);
                    if (aliasMatch.status() != DependencyTargetMatchStatus.MISSING
                            && aliasMatch.status() != DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED) {
                        return aliasMatch.withAlias(name, alias);
                    }
                }
            }
            return direct;
        }

        MatchDecision matchPackage(String name) {
            return matchName(name, installedPackages, repositoryPackages, false);
        }

        ProviderMatch matchProvider(String libraryName, SourcePackage sourcePackage, String sourcePath) {
            String normalizedLibrary = libraryStem(libraryName);
            String sourceVersionEvidence = libraryVersionEvidence(firstNonBlank(libraryName, sourcePath));
            MatchDecision target = sourcePackage.present()
                    ? matchLibraryThenSourcePackageFallback(sourcePackage.name(), libraryName)
                    : matchLibrary(libraryName);
            TargetProvider targetProvider = TargetProvider.from(target, libraryName);
            DependencyTargetMatchStatus relation = versionRelation(sourcePackage, sourceVersionEvidence, targetProvider, target.status());
            DependencyRiskLevel risk = riskForProviderRelation(relation);
            Map<String, Object> matchEvidence = new LinkedHashMap<>(target.evidence());
            matchEvidence.put("normalizedLibrary", normalizedLibrary);
            matchEvidence.put("sourcePackagePresent", sourcePackage.present());
            matchEvidence.put("versionComparator", "major-version");
            return new ProviderMatch(
                    fileName(libraryName),
                    sourcePath,
                    libraryStem(libraryName),
                    sourcePackage.name(),
                    sourcePackage.version(),
                    sourcePackage.source(),
                    sourceVersionEvidence,
                    targetProvider.packageName(),
                    targetProvider.version(),
                    targetProvider.source(),
                    relation,
                    risk,
                    target.status() == DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED
                            ? DependencyConfidence.LOW
                            : DependencyConfidence.HIGH,
                    relation.name(),
                    matchEvidence,
                    List.of(sanitize(sourcePath))
            );
        }

        private MatchDecision matchLibraryThenSourcePackageFallback(String packageName, String libraryName) {
            MatchDecision libraryMatch = matchLibrary(libraryName);
            if (libraryMatch.status() != DependencyTargetMatchStatus.MISSING
                    && libraryMatch.status() != DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED
                    && hasProviderVersion(libraryMatch)) {
                return libraryMatch;
            }
            MatchDecision packageMatch = matchPackage(packageName);
            if (packageMatch.status() != DependencyTargetMatchStatus.MISSING
                    && packageMatch.status() != DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED) {
                return packageMatch.withSourceOwnerPackageFallback(packageName, libraryName);
            }
            MatchDecision normalizedPackageMatch = matchPackage(normalizedPackageName(packageName));
            if (!normalize(normalizedPackageName(packageName)).equals(normalize(packageName))
                    && normalizedPackageMatch.status() != DependencyTargetMatchStatus.MISSING
                    && normalizedPackageMatch.status() != DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED) {
                return normalizedPackageMatch.withSourceOwnerPackageFallback(packageName, libraryName);
            }
            return packageMatch.status() == DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED ? packageMatch : libraryMatch;
        }

        private boolean hasProviderVersion(MatchDecision match) {
            if (match.version() != null && !match.version().isBlank()) {
                return true;
            }
            Map<String, Object> evidence = match.evidence() == null ? Map.of() : match.evidence();
            Map<?, ?> metadata = evidence.get("metadata") instanceof Map<?, ?> map ? map : Map.of();
            return !firstNonBlank(
                    stringValue(evidence.get("providerPackage")),
                    stringValue(evidence.get("targetProviderPackage")),
                    stringValue(metadata.get("ownerPackage")),
                    stringValue(metadata.get("packageName")),
                    stringValue(metadata.get("targetPackageCandidate"))
            ).isBlank() && !firstNonBlank(
                    stringValue(metadata.get("ownerVersion")),
                    stringValue(metadata.get("packageVersion")),
                    stringValue(metadata.get("version"))
            ).isBlank();
        }

        private DependencyTargetMatchStatus versionRelation(SourcePackage sourcePackage, String sourceVersionEvidence,
                                                           TargetProvider targetProvider, DependencyTargetMatchStatus targetStatus) {
            if (sourcePackage.present()) {
                if (targetProvider.version().isBlank()) {
                    return DependencyTargetMatchStatus.NO_TARGET_VERSION_FOUND;
                }
                int comparison = compareMajorVersion(sourcePackage.version(), targetProvider.version());
                if (comparison == 0) {
                    return DependencyTargetMatchStatus.SAME_MAJOR;
                }
                if (comparison > 0) {
                    return DependencyTargetMatchStatus.TARGET_NEWER;
                }
                if (comparison < 0 && comparison != Integer.MIN_VALUE) {
                    return DependencyTargetMatchStatus.TARGET_OLDER;
                }
                return DependencyTargetMatchStatus.NO_TARGET_VERSION_FOUND;
            }
            if (!sourceVersionEvidence.isBlank() && !targetProvider.version().isBlank()) {
                return DependencyTargetMatchStatus.TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED;
            }
            if (targetStatus == DependencyTargetMatchStatus.TARGET_INSTALLED
                    || targetStatus == DependencyTargetMatchStatus.REPO_AVAILABLE
                    || targetStatus == DependencyTargetMatchStatus.PROVIDES_MATCH
                    || targetStatus == DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED) {
                return targetStatus;
            }
            return DependencyTargetMatchStatus.NO_TARGET_VERSION_FOUND;
        }

        private DependencyRiskLevel riskForProviderRelation(DependencyTargetMatchStatus relation) {
            return switch (relation) {
                case SAME_MAJOR -> DependencyRiskLevel.INFO;
                case TARGET_NEWER -> DependencyRiskLevel.LOW;
                case TARGET_OLDER -> DependencyRiskLevel.HIGH;
                case TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED -> DependencyRiskLevel.MEDIUM;
                case NO_TARGET_VERSION_FOUND -> DependencyRiskLevel.CRITICAL;
                case TARGET_INSTALLED, REPO_AVAILABLE, PROVIDES_MATCH -> DependencyRiskLevel.MEDIUM;
                case VERSION_MISMATCH, SOURCE_BUILD_REQUIRED, MISSING -> DependencyRiskLevel.HIGH;
                case MANUAL_CONFIRM_REQUIRED -> DependencyRiskLevel.INFO;
            };
        }

        MatchDecision matchLibrary(String name) {
            String key = libraryStem(name);
            DependencyAnalysisRepository.TargetComponentView installed = installedLibraries.get(key);
            if (installed != null) {
                return MatchDecision.installed(installed);
            }
            DependencyAnalysisRepository.TargetComponentView provided = repositoryProvides.get(key);
            if (provided != null) {
                return MatchDecision.provides(provided);
            }
            String packageStem = libraryPackageStem(key);
            if (!packageStem.equals(key)) {
                MatchDecision packageMatch = matchExactPackage(packageStem);
                if (packageMatch.status() != DependencyTargetMatchStatus.MISSING
                        && packageMatch.status() != DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED) {
                    return packageMatch.withAlias(name, packageStem);
                }
                if (!"libc".equals(packageStem)) {
                    MatchDecision packageMetadataMatch = scanMetadata(packageStem, "library-package");
                    if (packageMetadataMatch.status() != DependencyTargetMatchStatus.MISSING
                            && packageMetadataMatch.status() != DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED) {
                        return packageMetadataMatch.withAlias(name, packageStem);
                    }
                }
            }
            return scanMetadata(name, "library");
        }

        MatchDecision matchHeader(String name) {
            return scanMetadata(name, "header");
        }

        MatchDecision matchPkgConfig(String name) {
            return scanMetadata(name, "pkg-config");
        }

        private MatchDecision matchName(String name,
                                        Map<String, DependencyAnalysisRepository.TargetComponentView> installed,
                                        Map<String, DependencyAnalysisRepository.TargetComponentView> repository,
                                        boolean tool) {
            String key = normalize(name);
            DependencyAnalysisRepository.TargetComponentView installedMatch = installed.get(key);
            if (installedMatch != null) {
                return MatchDecision.installed(installedMatch);
            }
            DependencyAnalysisRepository.TargetComponentView repoMatch = repository.get(key);
            if (repoMatch != null) {
                return MatchDecision.repo(repoMatch);
            }
            MatchDecision metadata = scanMetadata(name, tool ? "tool" : "package");
            if (metadata.status() != DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED) {
                return metadata;
            }
            return available ? MatchDecision.missing() : MatchDecision.manual();
        }

        private MatchDecision matchExactToolOrPackage(String name) {
            String key = normalize(name);
            DependencyAnalysisRepository.TargetComponentView installedTool = installedTools.get(key);
            if (installedTool != null) {
                return MatchDecision.installed(installedTool);
            }
            return matchExactPackage(name);
        }

        private MatchDecision matchExactPackage(String name) {
            String key = normalize(name);
            DependencyAnalysisRepository.TargetComponentView installedPackage = installedPackages.get(key);
            if (installedPackage != null) {
                return MatchDecision.installed(installedPackage);
            }
            DependencyAnalysisRepository.TargetComponentView repositoryPackage = repositoryPackages.get(key);
            if (repositoryPackage != null) {
                return MatchDecision.repo(repositoryPackage);
            }
            return available ? MatchDecision.missing() : MatchDecision.manual();
        }

        private MatchDecision scanMetadata(String needle, String kind) {
            String normalizedNeedle = normalize(needle);
            if (normalizedNeedle.isBlank()) {
                return available ? MatchDecision.missing() : MatchDecision.manual();
            }
            if (normalizedNeedle.length() < 3) {
                return available ? MatchDecision.missing() : MatchDecision.manual();
            }
            for (DependencyAnalysisRepository.TargetComponentView component : allComponents) {
                String haystack = normalize(String.join(" ",
                        safe(component.name()),
                        safe(component.version()),
                        safe(component.componentType()),
                        safe(component.path()),
                        safe(component.source()),
                        component.metadata() == null ? "" : component.metadata().toString()
                ));
                if (haystack.contains(normalizedNeedle) || haystack.contains(libraryStem(normalizedNeedle))) {
                    if ("installed_package".equals(normalize(component.source()))
                            || "installed_library".equals(normalize(component.source()))
                            || "tool_version".equals(normalize(component.source()))) {
                        return MatchDecision.installed(component);
                    }
                    if ("repository_package".equals(normalize(component.source()))) {
                        return MatchDecision.repo(component);
                    }
                    return MatchDecision.provides(component, kind);
                }
            }
            return available ? MatchDecision.missing() : MatchDecision.manual();
        }

        private String libraryPackageStem(String libraryName) {
            String value = normalize(libraryName);
            if (value.endsWith(".so")) {
                return value.substring(0, value.length() - 3);
            }
            return value;
        }

        private String normalizedPackageName(String packageName) {
            return normalize(packageName)
                    .replaceAll("\\.(x86_64|riscv64|aarch64|noarch|i[3-6]86)$", "")
                    .replaceAll("[-_](x86_64|riscv64|aarch64|amd64|x64)$", "")
                    .replaceAll("[-_.]{2,}", "-")
                    .replaceAll("^-|-$", "");
        }
    }

    private record MatchDecision(
            DependencyTargetMatchStatus status,
            String version,
            Map<String, Object> evidence
    ) {
        static MatchDecision installed(DependencyAnalysisRepository.TargetComponentView component) {
            return of(DependencyTargetMatchStatus.TARGET_INSTALLED, component, "installed");
        }

        static MatchDecision repo(DependencyAnalysisRepository.TargetComponentView component) {
            return of(DependencyTargetMatchStatus.REPO_AVAILABLE, component, "repository");
        }

        static MatchDecision provides(DependencyAnalysisRepository.TargetComponentView component) {
            return provides(component, "provides");
        }

        static MatchDecision provides(DependencyAnalysisRepository.TargetComponentView component, String kind) {
            return of(DependencyTargetMatchStatus.PROVIDES_MATCH, component, kind);
        }

        static MatchDecision missing() {
            return new MatchDecision(DependencyTargetMatchStatus.MISSING, null, Map.of("targetSnapshotAvailable", true));
        }

        static MatchDecision manual() {
            return new MatchDecision(DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED, null, Map.of("targetSnapshotAvailable", false));
        }

        MatchDecision withAlias(String requestedName, String matchedAlias) {
            Map<String, Object> aliasedEvidence = new LinkedHashMap<>(evidence);
            aliasedEvidence.put("requestedName", requestedName);
            aliasedEvidence.put("matchedAlias", matchedAlias);
            return new MatchDecision(status, version, aliasedEvidence);
        }

        MatchDecision withSourceProviderPackage(String requestedName, String sourceProviderPackage) {
            Map<String, Object> providerEvidence = new LinkedHashMap<>(evidence);
            providerEvidence.put("matchedBy", "source-provider-package");
            providerEvidence.put("requestedName", requestedName);
            providerEvidence.put("sourceProviderPackage", sourceProviderPackage);
            return new MatchDecision(status, version, providerEvidence);
        }

        MatchDecision withSourceOwnerPackageFallback(String sourceOwnerPackage, String requestedLibrary) {
            Map<String, Object> fallbackEvidence = new LinkedHashMap<>(evidence);
            fallbackEvidence.put("matchedBy", "source-owner-package-fallback");
            fallbackEvidence.put("sourceOwnerPackage", sourceOwnerPackage);
            fallbackEvidence.put("requestedLibrary", requestedLibrary);
            fallbackEvidence.put("samePackageEcosystemAssumed", true);
            fallbackEvidence.put("targetProviderPackage", firstNonBlank(
                    stringValue(fallbackEvidence.get("providerPackage")),
                    stringValue(fallbackEvidence.get("name"))
            ));
            fallbackEvidence.put("targetProviderVersion", firstNonBlank(
                    version,
                    stringValue(fallbackEvidence.get("version"))
            ));
            return new MatchDecision(status, version, fallbackEvidence);
        }

        private static MatchDecision of(DependencyTargetMatchStatus status,
                                        DependencyAnalysisRepository.TargetComponentView component,
                                        String matchedBy) {
            Map<String, Object> evidence = new LinkedHashMap<>();
            evidence.put("matchedBy", matchedBy);
            evidence.put("name", component.name());
            evidence.put("version", component.version());
            evidence.put("componentType", component.componentType());
            evidence.put("path", component.path());
            evidence.put("source", component.source());
            if (component.metadata() != null && !component.metadata().isEmpty()) {
                evidence.put("metadata", component.metadata());
                String providerPackage = firstNonBlank(
                        stringValue(component.metadata().get("ownerPackage")),
                        stringValue(component.metadata().get("normalizedPackage")),
                        stringValue(component.metadata().get("packageName")),
                        stringValue(component.metadata().get("targetPackageCandidate"))
                );
                if (!providerPackage.isBlank()) {
                    evidence.put("providerPackage", providerPackage);
                }
            }
            return new MatchDecision(status, component.version(), evidence);
        }

        private static String stringValue(Object value) {
            return value == null ? "" : String.valueOf(value);
        }

        private static String firstNonBlank(String... values) {
            for (String value : values) {
                if (value != null && !value.isBlank()) {
                    return value;
                }
            }
            return "";
        }
    }

    private record TargetProvider(
            String packageName,
            String version,
            String source
    ) {
        static TargetProvider from(MatchDecision match, String fallbackLibraryName) {
            Map<String, Object> evidence = match.evidence() == null ? Map.of() : match.evidence();
            Map<?, ?> metadata = evidence.get("metadata") instanceof Map<?, ?> map ? map : Map.of();
            String packageName = firstNonBlank(
                    stringValue(evidence.get("providerPackage")),
                    stringValue(evidence.get("name")),
                    stringValue(metadata.get("ownerPackage")),
                    stringValue(metadata.get("normalizedPackage")),
                    stringValue(metadata.get("packageName")),
                    stringValue(metadata.get("targetPackageCandidate")),
                    fallbackLibraryName
            );
            String version = firstNonBlank(
                    match.version(),
                    stringValue(metadata.get("ownerVersion")),
                    stringValue(metadata.get("packageVersion")),
                    stringValue(metadata.get("version"))
            );
            return new TargetProvider(packageName, version, stringValue(evidence.get("source")));
        }

        private static String stringValue(Object value) {
            return value == null ? "" : String.valueOf(value);
        }

        private static String firstNonBlank(String... values) {
            for (String value : values) {
                if (value != null && !value.isBlank()) {
                    return value;
                }
            }
            return "";
        }
    }
}
