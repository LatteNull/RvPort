package cn.rvport.backend.dependency;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

class DependencyFactExtractorRuleTests {

    private final DependencyFactExtractor extractor = new DependencyFactExtractor();

    @Test
    void mapsEveryTargetStatusToItsRiskAndPriority() {
        Map<DependencyTargetMatchStatus, DependencyRiskLevel> risks = Map.ofEntries(
                Map.entry(DependencyTargetMatchStatus.SAME_MAJOR, DependencyRiskLevel.INFO),
                Map.entry(DependencyTargetMatchStatus.TARGET_NEWER, DependencyRiskLevel.LOW),
                Map.entry(DependencyTargetMatchStatus.TARGET_OLDER, DependencyRiskLevel.HIGH),
                Map.entry(DependencyTargetMatchStatus.TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED, DependencyRiskLevel.MEDIUM),
                Map.entry(DependencyTargetMatchStatus.NO_TARGET_VERSION_FOUND, DependencyRiskLevel.CRITICAL),
                Map.entry(DependencyTargetMatchStatus.TARGET_INSTALLED, DependencyRiskLevel.LOW),
                Map.entry(DependencyTargetMatchStatus.REPO_AVAILABLE, DependencyRiskLevel.MEDIUM),
                Map.entry(DependencyTargetMatchStatus.PROVIDES_MATCH, DependencyRiskLevel.MEDIUM),
                Map.entry(DependencyTargetMatchStatus.VERSION_MISMATCH, DependencyRiskLevel.HIGH),
                Map.entry(DependencyTargetMatchStatus.SOURCE_BUILD_REQUIRED, DependencyRiskLevel.HIGH),
                Map.entry(DependencyTargetMatchStatus.MISSING, DependencyRiskLevel.HIGH),
                Map.entry(DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED, DependencyRiskLevel.LOW));
        Map<DependencyTargetMatchStatus, Integer> ranks = Map.ofEntries(
                Map.entry(DependencyTargetMatchStatus.SAME_MAJOR, 12),
                Map.entry(DependencyTargetMatchStatus.TARGET_NEWER, 11),
                Map.entry(DependencyTargetMatchStatus.TARGET_OLDER, 10),
                Map.entry(DependencyTargetMatchStatus.TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED, 9),
                Map.entry(DependencyTargetMatchStatus.NO_TARGET_VERSION_FOUND, 8),
                Map.entry(DependencyTargetMatchStatus.TARGET_INSTALLED, 7),
                Map.entry(DependencyTargetMatchStatus.PROVIDES_MATCH, 6),
                Map.entry(DependencyTargetMatchStatus.REPO_AVAILABLE, 5),
                Map.entry(DependencyTargetMatchStatus.VERSION_MISMATCH, 4),
                Map.entry(DependencyTargetMatchStatus.SOURCE_BUILD_REQUIRED, 3),
                Map.entry(DependencyTargetMatchStatus.MISSING, 2),
                Map.entry(DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED, 1));

        risks.forEach((status, expected) -> {
            DependencyRiskLevel actual = ReflectionTestUtils.invokeMethod(extractor, "riskFor", status, DependencyRiskLevel.LOW);
            assertThat(actual).isEqualTo(expected);
            Integer rank = ReflectionTestUtils.invokeMethod(extractor, "statusRank", status);
            assertThat(rank).isEqualTo(ranks.get(status));
        });
    }

    @Test
    void ranksEveryEvidenceSourceAndConfidenceLevel() {
        Map<String, Integer> sourceRanks = Map.ofEntries(
                Map.entry("strace_execve_tool", 80),
                Map.entry("strace_execve_link_library", 80),
                Map.entry("compile_database_compiler", 70),
                Map.entry("compile_database_link_library", 70),
                Map.entry("elf_needed", 60),
                Map.entry("elf_soname", 60),
                Map.entry("runtime_loader_error", 60),
                Map.entry("missing_header", 50),
                Map.entry("pkg_config", 50),
                Map.entry("build_system_hint", 40),
                Map.entry("build_ninja", 40),
                Map.entry("tool_pattern", 10),
                Map.entry("unknown", 20));
        sourceRanks.forEach((source, expected) -> {
            Integer actual = ReflectionTestUtils.invokeMethod(extractor, "sourceRank", item(source, DependencyConfidence.LOW));
            assertThat(actual).isEqualTo(expected);
        });
        assertThat((Integer) ReflectionTestUtils.invokeMethod(extractor, "sourceRank", item(null, DependencyConfidence.LOW)))
                .isEqualTo(20);

        assertThat((Integer) ReflectionTestUtils.invokeMethod(extractor, "confidenceRank", DependencyConfidence.HIGH)).isEqualTo(4);
        assertThat((Integer) ReflectionTestUtils.invokeMethod(extractor, "confidenceRank", DependencyConfidence.MEDIUM)).isEqualTo(3);
        assertThat((Integer) ReflectionTestUtils.invokeMethod(extractor, "confidenceRank", DependencyConfidence.OBSERVED)).isEqualTo(2);
        assertThat((Integer) ReflectionTestUtils.invokeMethod(extractor, "confidenceRank", DependencyConfidence.LOW)).isEqualTo(1);
    }

    @Test
    void parsesVersionsPathsPropertiesCsvAndAliasesAtBoundaries() {
        assertThat((String) ReflectionTestUtils.invokeMethod(extractor, "majorVersion", "1:12.3-4")).isEqualTo("12");
        assertThat((String) ReflectionTestUtils.invokeMethod(extractor, "majorVersion", "release-99")).isEqualTo("99");
        assertThat((String) ReflectionTestUtils.invokeMethod(extractor, "majorVersion", "none")).isEmpty();
        assertThat((String) ReflectionTestUtils.invokeMethod(extractor, "majorVersion", " ")).isEmpty();
        assertThat((Integer) ReflectionTestUtils.invokeMethod(extractor, "compareMajorVersion", "12.1", "13.0")).isPositive();
        assertThat((Integer) ReflectionTestUtils.invokeMethod(extractor, "compareMajorVersion", "12", "11")).isNegative();
        assertThat((Integer) ReflectionTestUtils.invokeMethod(extractor, "compareMajorVersion", "none", "11"))
                .isEqualTo(Integer.MIN_VALUE);
        assertThat((Integer) ReflectionTestUtils.invokeMethod(extractor, "compareMajorVersion", "11", "none"))
                .isEqualTo(Integer.MIN_VALUE);

        assertThat((Boolean) ReflectionTestUtils.invokeMethod(extractor, "isTrivialPath", (Object) null)).isTrue();
        assertThat((Boolean) ReflectionTestUtils.invokeMethod(extractor, "isTrivialPath", "./")).isTrue();
        assertThat((Boolean) ReflectionTestUtils.invokeMethod(extractor, "isTrivialPath", "/usr/include")).isFalse();
        assertThat((String) ReflectionTestUtils.invokeMethod(extractor, "fileName", (Object) null)).isEqualTo("unknown");
        assertThat((String) ReflectionTestUtils.invokeMethod(extractor, "fileName", " ")).isEqualTo("unknown");
        assertThat((String) ReflectionTestUtils.invokeMethod(extractor, "fileName", "C:\\lib\\foo.so")).isEqualTo("foo.so");
        assertThat((String) ReflectionTestUtils.invokeMethod(extractor, "fileName", "/usr/lib/foo.so")).isEqualTo("foo.so");
        assertThat((String) ReflectionTestUtils.invokeMethod(extractor, "fileName", "foo.so")).isEqualTo("foo.so");

        assertThat(this.<String, String>invokeMap("properties", (Object) null)).isEmpty();
        assertThat(this.<String, String>invokeMap("properties", "a=1\tbroken\tb=2=3"))
                .containsEntry("a", "1").containsEntry("b", "2=3");
        assertThat(this.<String>invokeList("csv", " a, ,b,a "))
                .containsExactly("a", "b");
        assertThat(this.<String>invokeList("csv", " ")).isEmpty();
        assertThat(this.<String>invokeList("csv", (Object) null)).isEmpty();

        assertThat(this.<String>invokeList("toolAliases", "cc")).containsExactly("gcc", "clang");
        assertThat(this.<String>invokeList("toolAliases", "c++"))
                .containsExactly("g++", "clang++")
                .doesNotContain("gcc");
        assertThat(this.<String>invokeList("toolAliases", "ar")).containsExactly("binutils");
        assertThat(this.<String>invokeList("toolAliases", "ninja")).contains("ninja-build");
        assertThat(this.<String>invokeList("toolAliases", "rpmbuild")).contains("rpm-build");
        assertThat(this.<String>invokeList("toolAliases", "configure")).containsExactly("autoconf");
        assertThat(this.<String>invokeList("toolAliases", "custom")).isEmpty();
        assertThat(this.<String>invokeListTwo("equivalentCompilerTools", "c++", "gcc-c++"))
                .containsExactly("c++", "g++");
        assertThat(this.<String>invokeListTwo("equivalentCompilerTools", "g++", "g++"))
                .containsExactly("c++", "g++");
        assertThat(this.<String>invokeListTwo("equivalentCompilerTools", "clang++", "clang"))
                .containsExactly("c++", "clang++");
        assertThat(this.<String>invokeListTwo("equivalentCompilerTools", "c++", ""))
                .containsExactly("c++", "g++", "clang++");
        assertThat(this.<String>invokeListTwo("equivalentCompilerTools", "cc", "gcc"))
                .containsExactly("cc", "gcc");
        assertThat(this.<String>invokeListTwo("equivalentCompilerTools", "clang", "clang"))
                .containsExactly("cc", "clang");
        assertThat(this.<String>invokeListTwo("equivalentCompilerTools", "cc", ""))
                .containsExactly("cc", "gcc", "clang");
        assertThat(this.<String>invokeListTwo("equivalentCompilerTools", "make", "gcc")).isEmpty();
        assertThat((String) ReflectionTestUtils.invokeMethod(extractor, "sourceProviderPackage", Map.of()))
                .isEmpty();
        assertThat(this.<String>invokeList("libraryProviderAliases", "libgcc_s.so.1")).contains("libgcc", "gcc");
        assertThat(this.<String>invokeList("libraryProviderAliases", "libstdc++.so.6")).contains("gcc-c++");
        assertThat(this.<String>invokeList("libraryProviderAliases", "libc.so.6")).containsExactly("glibc");
        assertThat(this.<String>invokeList("libraryProviderAliases", "libcustom.so")).isEmpty();

        assertThat((Boolean) ReflectionTestUtils.invokeMethod(extractor, "isBuildSystemDiscoveryLine", "CMakeLists.txt")).isFalse();
        assertThat((Boolean) ReflectionTestUtils.invokeMethod(extractor, "isBuildSystemDiscoveryLine", "CMakeLists.txt Makefile")).isFalse();
        assertThat((Boolean) ReflectionTestUtils.invokeMethod(extractor, "isBuildSystemDiscoveryLine", "CMakeLists.txt Makefile meson.build")).isFalse();
        assertThat((Boolean) ReflectionTestUtils.invokeMethod(extractor, "isBuildSystemDiscoveryLine",
                "CMakeLists.txt Makefile meson.build build.ninja")).isTrue();
        assertThat((Boolean) ReflectionTestUtils.invokeMethod(extractor, "isToolFileNameReference", ".gcc", 1, 4)).isTrue();
        assertThat((Boolean) ReflectionTestUtils.invokeMethod(extractor, "isToolFileNameReference", "gcc.txt", 0, 3)).isTrue();
        assertThat((Boolean) ReflectionTestUtils.invokeMethod(extractor, "isToolFileNameReference", "gcc", 0, 3)).isFalse();
    }

    @Test
    void parsesRpmOwnerTextAndRejectsUnownedValues() {
        Object rpm = ReflectionTestUtils.invokeMethod(extractor, "parseSourcePackage", "file: glibc-2.38-4.x86_64");
        Object simple = ReflectionTestUtils.invokeMethod(extractor, "parseSourcePackage", "custom-package");
        Object empty = ReflectionTestUtils.invokeMethod(extractor, "parseSourcePackage", "file is not owned by any package");

        assertThat(rpm.toString()).contains("name=glibc", "version=2.38-4");
        assertThat(simple.toString()).contains("name=custom-package", "version=");
        assertThat(empty.toString()).contains("name=", "version=");
    }

    @Test
    void suppliesRecommendationForEveryMatchStatus() throws Exception {
        Class<?> decisionType = Class.forName("cn.rvport.backend.dependency.DependencyFactExtractor$MatchDecision");
        Constructor<?> constructor = decisionType.getDeclaredConstructor(
                DependencyTargetMatchStatus.class, String.class, Map.class);
        constructor.setAccessible(true);

        for (DependencyTargetMatchStatus status : DependencyTargetMatchStatus.values()) {
            Object decision = constructor.newInstance(status, "1.0", Map.of());
            String recommendation = ReflectionTestUtils.invokeMethod(extractor, "recommendation", "base", decision);
            assertThat(recommendation).startsWith("base；").hasSizeGreaterThan(8);
        }
    }

    @Test
    void replacementPrecedenceUsesStatusThenEvidenceThenConfidence() {
        assertThat(shouldReplace(
                item("tool_pattern", DependencyConfidence.HIGH, DependencyTargetMatchStatus.MISSING),
                item("tool_pattern", DependencyConfidence.LOW, DependencyTargetMatchStatus.SAME_MAJOR))).isTrue();
        assertThat(shouldReplace(
                item("tool_pattern", DependencyConfidence.LOW, DependencyTargetMatchStatus.SAME_MAJOR),
                item("tool_pattern", DependencyConfidence.HIGH, DependencyTargetMatchStatus.MISSING))).isFalse();
        assertThat(shouldReplace(
                item("tool_pattern", DependencyConfidence.HIGH, DependencyTargetMatchStatus.REPO_AVAILABLE),
                item("strace_execve_tool", DependencyConfidence.LOW, DependencyTargetMatchStatus.REPO_AVAILABLE))).isTrue();
        assertThat(shouldReplace(
                item("strace_execve_tool", DependencyConfidence.LOW, DependencyTargetMatchStatus.REPO_AVAILABLE),
                item("tool_pattern", DependencyConfidence.HIGH, DependencyTargetMatchStatus.REPO_AVAILABLE))).isFalse();
        assertThat(shouldReplace(
                item("tool_pattern", DependencyConfidence.LOW, DependencyTargetMatchStatus.REPO_AVAILABLE),
                item("tool_pattern", DependencyConfidence.HIGH, DependencyTargetMatchStatus.REPO_AVAILABLE))).isTrue();
        assertThat(shouldReplace(
                item("tool_pattern", DependencyConfidence.HIGH, DependencyTargetMatchStatus.REPO_AVAILABLE),
                item("tool_pattern", DependencyConfidence.LOW, DependencyTargetMatchStatus.REPO_AVAILABLE))).isFalse();
    }

    @Test
    void dedupeKeysDistinguishBundledPathsAndCollapseProviderEvidence() {
        DependencyAnalysisResultItem bundled = item("repository_bundled_elf", DependencyConfidence.HIGH);
        DependencyAnalysisResultItem ordinary = item("tool_pattern", DependencyConfidence.HIGH);
        Map<String, Object> providerEvidence = Map.of(
                "source", "repository_bundled_elf", "versionRelation", "SAME_MAJOR",
                "sourceOwnerPackage", "demo", "sourceOwnerVersion", "1.2",
                "sourceLibraryName", "libdemo.so.1", "sourceVersionEvidence", "1",
                "targetProviderPackage", "demo", "targetProviderVersion", "1.3");
        DependencyAnalysisResultItem provider = copyWithEvidence(bundled, providerEvidence);

        assertThat((String) ReflectionTestUtils.invokeMethod(extractor, "dedupeKey", bundled))
                .contains("tool:tool");
        assertThat((String) ReflectionTestUtils.invokeMethod(extractor, "dedupeKey", ordinary))
                .isEqualTo("BUILD_TOOL|tool");
        assertThat((String) ReflectionTestUtils.invokeMethod(extractor, "dedupeKey", provider))
                .contains("demo", "libdemo.so.1", "same_major");
    }

    @Test
    void helperCollectionsAndEvidenceHandleNullAndPopulatedInputs() {
        assertThat(this.<String>invokeList("stringList", List.of("a", "b"))).containsExactly("a", "b");
        assertThat(this.<String>invokeList("stringList", "not-a-list")).isEmpty();
        assertThat(this.<Object>invokeList("objectList", List.of(1, 2))).containsExactly(1, 2);
        assertThat(this.<Object>invokeList("objectList", 1)).isEmpty();

        assertThat(this.<String, Object>invokeMapTwo("mergeExtra", null, null)).isEmpty();
        assertThat(this.<String, Object>invokeMapTwo("mergeExtra", Map.of("left", 1), null))
                .containsEntry("left", 1);
        assertThat(this.<String, Object>invokeMapTwo("mergeExtra", null, Map.of("right", 2)))
                .containsEntry("right", 2);
        assertThat(this.<String, Object>invokeMapTwo("mergeExtra", Map.of("same", 1), Map.of("same", 2)))
                .containsEntry("same", 2);

        assertThat((String) ReflectionTestUtils.invokeMethod(extractor, "sanitize", (Object) null)).isEmpty();
        assertThat((String) ReflectionTestUtils.invokeMethod(extractor, "sanitize", "token=plain visible"))
                .isEqualTo("token=*** visible");
    }

    @Test
    void sourceProviderAndCmakeProbeHelpersHandleMissingAndCollectedData() {
        assertThat(ReflectionTestUtils.invokeMethod(extractor, "sourcePackage", (Object) null).toString())
                .contains("name=");
        assertThat(ReflectionTestUtils.invokeMethod(extractor, "sourcePackage", Map.of()).toString())
                .contains("name=");
        assertThat(ReflectionTestUtils.invokeMethod(extractor, "sourcePackage", Map.of("sourceProviderPackage", " ")).toString())
                .contains("name=");
        assertThat(ReflectionTestUtils.invokeMethod(extractor, "sourcePackage", Map.of(
                "sourceProviderPackage", "glibc", "sourceProviderVersion", "2.38", "sourceProviderSource", "rpm")).toString())
                .contains("name=glibc", "version=2.38", "source=rpm");

        Set<String> macros = Set.of("__GNUC__", "COLLECTED");
        assertThat((String) ReflectionTestUtils.invokeMethod(extractor, "macroSource", "UNKNOWN", macros)).isEmpty();
        assertThat((String) ReflectionTestUtils.invokeMethod(extractor, "macroSource", "__GNUC__=12", macros))
                .isEqualTo("static_builtin_catalog");
        assertThat((String) ReflectionTestUtils.invokeMethod(extractor, "macroSource", "COLLECTED=1", macros))
                .isEqualTo("collected_compiler_builtin");

        String probes = """
                RVPORT_OBSERVATION cmakeCompilerFlagProbe FLAG_OK\tlanguage=C\tflag=-Wall\tfile=sub/CMakeLists.txt\tfunction=check_c_compiler_flag
                RVPORT_OBSERVATION cmakeCompilerFlagProbe \tlanguage=C\tflag=-O2
                RVPORT_OBSERVATION cmakeCompilerFlagProbe FLAG_NO_VALUE\tlanguage=C\tflag=
                """;
        Map<String, Object> parsed = invokeMap("cmakeCompilerFlagProbes", probes);
        assertThat(parsed).containsKey("FLAG_OK").doesNotContainKeys("", "FLAG_NO_VALUE");
    }

    @Test
    void staticPackageParserAndSanitizerCoverRpmFormats() throws Exception {
        assertThat(invokeStatic("sanitizeStatic", new Class<?>[]{String.class}, new Object[]{null})).isEqualTo("");
        assertThat(invokeStatic("sanitizeStatic", new Class<?>[]{String.class}, new Object[]{"private_key=value"}))
                .isEqualTo("private_key=***");
        assertThat(invokeStatic("parseSourcePackageStatic", new Class<?>[]{String.class}, new Object[]{null}).toString())
                .contains("name=");
        assertThat(invokeStatic("parseSourcePackageStatic", new Class<?>[]{String.class}, new Object[]{"file is not owned by any package"}).toString())
                .contains("name=");
        assertThat(invokeStatic("parseSourcePackageStatic", new Class<?>[]{String.class}, new Object[]{"file: glibc-2.38-4.riscv64"}).toString())
                .contains("name=glibc", "version=2.38-4");
        assertThat(invokeStatic("parseSourcePackageStatic", new Class<?>[]{String.class}, new Object[]{"vendor-tool"}).toString())
                .contains("name=vendor-tool", "version=");
        assertThat((Integer) ReflectionTestUtils.invokeMethod(extractor, "compareMajorVersion",
                "999999999999999999", "888888888888888888")).isNegative();
    }

    @Test
    void extractionFallsBackToManualBuildScriptFindingWhenNoEvidenceExists() {
        DependencyAnalysisView run = new DependencyAnalysisView(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
                UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), 1L,
                cn.rvport.backend.task.TaskStatus.RUNNING, Map.of(), List.of(), java.time.OffsetDateTime.now(), null,
                java.time.OffsetDateTime.now());
        cn.rvport.backend.buildvalidation.BuildValidationRunView build =
                new cn.rvport.backend.buildvalidation.BuildValidationRunView(run.sourceBuildRunId(), run.projectId(),
                        UUID.randomUUID(), run.sourceRevisionId(), UUID.randomUUID(), UUID.randomUUID(), null, "hash",
                        "", "/workspace", 60, 0, cn.rvport.backend.task.TaskStatus.SUCCEEDED, null, null, null, null,
                        java.time.OffsetDateTime.now(), java.time.OffsetDateTime.now(), java.time.OffsetDateTime.now(), Map.of());

        assertThat(extractor.extract(run, build, "", List.of(), List.of(), null))
                .singleElement().satisfies(item -> {
                    assertThat(item.dependencyName()).isEqualTo("build-script");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED);
                });
    }

    private DependencyAnalysisResultItem item(String source, DependencyConfidence confidence) {
        return item(source, confidence, DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED);
    }

    private DependencyAnalysisResultItem item(
            String source,
            DependencyConfidence confidence,
            DependencyTargetMatchStatus status
    ) {
        Map<String, Object> evidence = source == null ? null : Map.of("source", source);
        return new DependencyAnalysisResultItem(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
                DependencyType.BUILD_TOOL, "tool", null, null, null, null, null, null, null, null, null,
                status, DependencyRiskLevel.LOW, "tool:tool", "review",
                confidence, evidence);
    }

    private boolean shouldReplace(DependencyAnalysisResultItem existing, DependencyAnalysisResultItem candidate) {
        return Boolean.TRUE.equals(ReflectionTestUtils.invokeMethod(extractor, "shouldReplace", existing, candidate));
    }

    private DependencyAnalysisResultItem copyWithEvidence(
            DependencyAnalysisResultItem item,
            Map<String, Object> evidence
    ) {
        return new DependencyAnalysisResultItem(item.projectId(), item.sourceRevisionId(), item.taskId(),
                item.dependencyAnalysisRunId(), item.dependencyType(), item.dependencyName(), item.dependencyVersion(),
                item.sourceProviderPackage(), item.sourceProviderVersion(), item.sourceDetectedVersion(),
                item.targetProviderPackage(), item.targetProviderVersion(), item.targetDetectedVersion(),
                item.providerVersionStatus(), item.versionEvidenceConfidence(), item.targetMatchStatus(), item.riskLevel(),
                item.locationLabel(), item.recommendation(), item.confidence(), evidence);
    }

    @SuppressWarnings("unchecked")
    private <T> List<T> invokeList(String method, Object argument) {
        return (List<T>) ReflectionTestUtils.invokeMethod(extractor, method, argument);
    }

    @SuppressWarnings("unchecked")
    private <T> List<T> invokeListTwo(String method, Object first, Object second) {
        return (List<T>) ReflectionTestUtils.invokeMethod(extractor, method, first, second);
    }

    @SuppressWarnings("unchecked")
    private <K, V> Map<K, V> invokeMap(String method, Object argument) {
        return (Map<K, V>) ReflectionTestUtils.invokeMethod(extractor, method, argument);
    }

    @SuppressWarnings("unchecked")
    private <K, V> Map<K, V> invokeMapTwo(String method, Object first, Object second) {
        return (Map<K, V>) ReflectionTestUtils.invokeMethod(extractor, method, first, second);
    }

    private Object invokeStatic(String name, Class<?>[] parameterTypes, Object[] arguments) throws Exception {
        Method method = DependencyFactExtractor.class.getDeclaredMethod(name, parameterTypes);
        method.setAccessible(true);
        return method.invoke(null, arguments);
    }
}
