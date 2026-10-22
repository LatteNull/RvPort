package cn.rvport.backend.dependency;

import static org.assertj.core.api.Assertions.assertThat;

import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class DependencyFactExtractorIndexTests {

    private final DependencyFactExtractor extractor = new DependencyFactExtractor();

    @Test
    void compileObjectIndexParsesCommandAndArgumentsOutputForms() throws Exception {
        Object index = inner("CompileObjectIndex", """
                [
                  {"arguments":["cc","-c","a.c","-o","obj/a.o"]},
                  {"command":"c++ -c b.cc -oobj/b.obj"},
                  {"command":"cc -c ignored.c -o ignored.txt"},
                  {"command":""}
                ]
                """);

        assertThat((Boolean) call(index, "referencesObject", "c++ obj/a.o obj/b.obj -o app")).isTrue();
        assertThat((Boolean) call(index, "referencesObject", "ld /tmp/a.o -o app")).isTrue();
        assertThat((Boolean) call(index, "referencesObject", "cc unrelated.c")).isFalse();
        assertThat((Boolean) call(index, "referencesObject", (Object) null)).isFalse();
        assertThat((Boolean) call(index, "referencesObject", " ")).isFalse();

        assertThat(this.<String>callList(index, "linkOutputs", "c++ a.o -o libdemo.so -odemo -o ignored.a"))
                .containsExactly("libdemo.so", "demo");
        assertThat(this.<String>callList(index, "linkOutputs", (Object) null)).isEmpty();
        assertThat(this.<String>callList(index, "linkOutputs", " ")).isEmpty();
    }

    @Test
    void compileObjectIndexSafelyIgnoresAbsentMalformedAndNonArrayDatabases() throws Exception {
        for (Object input : new Object[]{null, " ", "{}", "not-json"}) {
            Object index = inner("CompileObjectIndex", input);
            assertThat((Boolean) call(index, "referencesObject", "a.o")).isFalse();
            assertThat(this.<String>callList(index, "linkOutputs", "cc a.o -o result")).containsExactly("result");
        }
    }

    @Test
    void sourceCapabilityIndexUsesNamesPathsAliasesAndOwnerMetadata() throws Exception {
        List<DependencyAnalysisRepository.TargetComponentView> components = List.of(
                component("gcc", "12.2", "tool", "/usr/bin/cc", "tool_version", null),
                component("gcc", "12.2", "package", null, "installed_package", null),
                component("binutils", "2.40", "package", null, "installed_package", null),
                component("libdemo.so.1", "1.2", "library", "/usr/lib/libdemo.so.1", "installed_library",
                        Map.of("ownerPackage", "demo-libs", "ownerVersion", "1.2", "providerScanner", "rpm")),
                component("libnative.so", "2", "file", "/opt/libnative.so", "native_file", null));
        Object index = inner("SourceCapabilityIndex", components);

        assertThat(this.<String, Object>callMap(index, "toolEvidence", "gcc")).containsEntry("sourceProviderPackage", "gcc");
        assertThat(this.<String, Object>callMap(index, "toolEvidence", "missing", "/usr/bin/cc"))
                .containsEntry("sourceProviderPackage", "gcc");
        assertThat(this.<String, Object>callMap(index, "toolEvidence", "ar"))
                .containsEntry("sourceProviderPackage", "binutils");
        assertThat(this.<String, Object>callMap(index, "toolEvidence", "unknown")).isEmpty();
        assertThat(this.<String, Object>callMap(index, "libraryEvidence", "libdemo.so.1"))
                .containsEntry("sourceProviderPackage", "demo-libs")
                .containsEntry("sourceProviderVersion", "1.2")
                .containsEntry("sourceProviderScanner", "rpm");
        assertThat(this.<String, Object>callMap(index, "libraryEvidence", "libnative.so")).isNotEmpty();
        assertThat(this.<String, Object>callMap(index, "libraryEvidence", "libgcc_s.so.1"))
                .containsEntry("sourceProviderPackage", "gcc");

        assertThat(this.<String, Object>callMap(inner("SourceCapabilityIndex", (Object) null), "toolEvidence", "gcc"))
                .isEmpty();

        Object typeOnly = inner("SourceCapabilityIndex", List.of(
                component("clang", "18", "tool", "/usr/bin/clang", "unknown", null),
                component("pkg-only", "1", "package", null, "unknown", null),
                component("lib-only.so", "1", "library", "/usr/lib/lib-only.so", "unknown", null)));
        assertThat(this.<String, Object>callMap(typeOnly, "toolEvidence", "clang", null)).isNotEmpty();
        assertThat(this.<String, Object>callMap(typeOnly, "libraryEvidence", "lib-only.so")).isNotEmpty();
        assertThat(this.<String, Object>callMap(typeOnly, "libraryEvidence", "libpkg-only.so")).isNotNull();
    }

    @Test
    void targetCapabilityIndexMatchesDirectAliasProvideMetadataAndAvailabilityStates() throws Exception {
        List<DependencyAnalysisRepository.TargetComponentView> components = List.of(
                component("gcc", "13.1", "tool", "/usr/bin/gcc", "tool_version", null),
                component("clang", "18", "tool", "/usr/bin/clang", "unknown", null),
                component("binutils", "2.41", "package", null, "installed_package", null),
                component("cmake", "3.27", "package", null, "repository_package", null),
                component("libdemo.so.1", "1.2", "library", "/usr/lib/libdemo.so.1", "installed_library", null),
                component("libnative.so", "2", "library", "/opt/libnative.so", "native_file", null),
                component("demo-devel", "1.3", "package", "*/libprovided.so.1", "repository_provide",
                        Map.of("queryValue", "libprovided.so.1", "normalizedName", "libprovided.so")),
                component("header-provider", "2", "other", "/usr/include/special/header.h", "scan",
                        Map.of("packageName", "header-provider", "packageVersion", "2")),
                component("repo-hit", "4", "other", null, "repository_package", Map.of("version", "4")));
        Object index = inner("TargetCapabilityIndex", components);

        assertStatus(call(index, "matchTool", "gcc"), "TARGET_INSTALLED");
        assertStatus(call(index, "matchTool", "ar"), "TARGET_INSTALLED");
        assertStatus(call(index, "matchTool", "cmake"), "REPO_AVAILABLE");
        assertStatus(call(index, "matchTool", "unknown"), "MISSING");
        assertStatus(call(index, "matchLibrary", "libdemo.so.1"), "TARGET_INSTALLED");
        assertStatus(call(index, "matchLibrary", "libprovided.so.1"), "PROVIDES_MATCH");
        assertStatus(call(index, "matchHeader", "special/header.h"), "PROVIDES_MATCH");
        assertStatus(call(index, "matchPkgConfig", "repo-hit"), "REPO_AVAILABLE");
        assertStatus(call(index, "matchHeader", ""), "MISSING");
        assertStatus(call(index, "matchHeader", "ab"), "MISSING");

        Object unavailable = inner("TargetCapabilityIndex", (Object) null);
        assertStatus(call(unavailable, "matchTool", "gcc"), "MANUAL_CONFIRM_REQUIRED");
        assertStatus(call(unavailable, "matchTool", "c++", "gcc-c++"), "MANUAL_CONFIRM_REQUIRED");
        assertStatus(call(unavailable, "matchLibrary", "libmissing.so"), "MANUAL_CONFIRM_REQUIRED");
        assertStatus(call(unavailable, "matchHeader", ""), "MANUAL_CONFIRM_REQUIRED");
        assertStatus(call(unavailable, "matchHeader", "ab"), "MANUAL_CONFIRM_REQUIRED");
    }

    @Test
    void providerFieldsDerivesVersionsFromExplicitNestedAndFallbackEvidence() throws Exception {
        Object explicit = providerFields("1", DependencyTargetMatchStatus.MISSING, Map.of(
                "sourceProviderPackage", "src", "sourceProviderVersion", "1.2",
                "targetProviderPackage", "dst", "targetProviderVersion", "2.0",
                "providerVersionStatus", "TARGET_NEWER"));
        assertThat(explicit.toString()).contains("providerVersionStatus=TARGET_NEWER", "versionEvidenceConfidence=PACKAGE_OWNER");

        Object nested = providerFields(null, DependencyTargetMatchStatus.PROVIDES_MATCH, Map.of(
                "sourceOwnerPackage", "src", "sourceVersionEvidence", "3.1",
                "targetMatchEvidence", Map.of("name", "fallback", "metadata", Map.of(
                        "normalizedPackage", "dst", "ownerVersion", "2.8", "versionText", "2.8-rpm"))));
        assertThat(nested.toString()).contains("sourceProviderPackage=src", "targetProviderPackage=dst",
                "providerVersionStatus=TARGET_OLDER", "versionEvidenceConfidence=PACKAGE_OWNER");

        Object elf = providerFields(null, DependencyTargetMatchStatus.MISSING,
                Map.of("sourceDetectedVersion", "3.1"));
        assertThat(elf.toString()).contains("versionEvidenceConfidence=ELF_METADATA");

        Object command = providerFields("9.1", DependencyTargetMatchStatus.MISSING, null);
        assertThat(command.toString()).contains("providerVersionStatus=null", "versionEvidenceConfidence=COMMAND_VERSION");
        Object empty = providerFields(null, DependencyTargetMatchStatus.MISSING, Map.of());
        assertThat(empty.toString()).contains("providerVersionStatus=null", "versionEvidenceConfidence=null");

        for (DependencyTargetMatchStatus status : DependencyTargetMatchStatus.values()) {
            assertThat(providerFields(null, status, Map.of())).isNotNull();
        }

        assertThat(innerStatic("ProviderFields", "inferredProviderVersionStatus",
                new Class<?>[]{String.class, String.class, String.class, String.class},
                "src", "1.2", "dst", "1.9")).isEqualTo("SAME_MAJOR");
        assertThat(innerStatic("ProviderFields", "inferredProviderVersionStatus",
                new Class<?>[]{String.class, String.class, String.class, String.class},
                "src", "1.2", "dst", "2.0")).isEqualTo("TARGET_NEWER");
        assertThat(innerStatic("ProviderFields", "inferredProviderVersionStatus",
                new Class<?>[]{String.class, String.class, String.class, String.class},
                "src", "2.2", "dst", "1.0")).isEqualTo("TARGET_OLDER");
        assertThat(innerStatic("ProviderFields", "inferredProviderVersionStatus",
                new Class<?>[]{String.class, String.class, String.class, String.class},
                "src", "unknown", "dst", "unknown")).isEqualTo("NO_TARGET_VERSION_FOUND");
        assertThat(innerStatic("ProviderFields", "inferredProviderVersionStatus",
                new Class<?>[]{String.class, String.class, String.class, String.class},
                "src", "1", "", "1")).isEqualTo("");
        assertThat(innerStatic("ProviderFields", "inferredProviderVersionStatus",
                new Class<?>[]{String.class, String.class, String.class, String.class},
                "", "1", "dst", "1")).isEqualTo("");
    }

    @Test
    void targetProviderVersionRelationCoversOwnedUnownedAndFallbackStatuses() throws Exception {
        Object index = inner("TargetCapabilityIndex", List.of());
        Object ownedSame = record("SourcePackage", new Class<?>[]{String.class, String.class, String.class},
                "src", "1.2", "rpm");
        Object ownedNewer = record("SourcePackage", new Class<?>[]{String.class, String.class, String.class},
                "src", "1.2", "rpm");
        Object ownedOlder = record("SourcePackage", new Class<?>[]{String.class, String.class, String.class},
                "src", "2.2", "rpm");
        Object ownedUnknown = record("SourcePackage", new Class<?>[]{String.class, String.class, String.class},
                "src", "unknown", "rpm");
        Object unowned = record("SourcePackage", new Class<?>[]{String.class, String.class, String.class},
                "", "", "");

        assertRelation(index, ownedSame, "", provider("dst", "1.9"), DependencyTargetMatchStatus.REPO_AVAILABLE,
                DependencyTargetMatchStatus.SAME_MAJOR);
        assertRelation(index, ownedNewer, "", provider("dst", "2.0"), DependencyTargetMatchStatus.REPO_AVAILABLE,
                DependencyTargetMatchStatus.TARGET_NEWER);
        assertRelation(index, ownedOlder, "", provider("dst", "1.0"), DependencyTargetMatchStatus.REPO_AVAILABLE,
                DependencyTargetMatchStatus.TARGET_OLDER);
        assertRelation(index, ownedUnknown, "", provider("dst", "unknown"), DependencyTargetMatchStatus.REPO_AVAILABLE,
                DependencyTargetMatchStatus.NO_TARGET_VERSION_FOUND);
        assertRelation(index, ownedSame, "", provider("dst", ""), DependencyTargetMatchStatus.REPO_AVAILABLE,
                DependencyTargetMatchStatus.NO_TARGET_VERSION_FOUND);
        assertRelation(index, unowned, "3.1", provider("dst", "3.2"), DependencyTargetMatchStatus.PROVIDES_MATCH,
                DependencyTargetMatchStatus.TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED);
        for (DependencyTargetMatchStatus status : List.of(
                DependencyTargetMatchStatus.TARGET_INSTALLED,
                DependencyTargetMatchStatus.REPO_AVAILABLE,
                DependencyTargetMatchStatus.PROVIDES_MATCH,
                DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED,
                DependencyTargetMatchStatus.MISSING)) {
            DependencyTargetMatchStatus expected = status == DependencyTargetMatchStatus.MISSING
                    ? DependencyTargetMatchStatus.NO_TARGET_VERSION_FOUND : status;
            assertRelation(index, unowned, "", provider("", ""), status, expected);
        }

        for (DependencyTargetMatchStatus status : DependencyTargetMatchStatus.values()) {
            Object risk = call(index, "riskForProviderRelation", status);
            assertThat(risk).isNotNull();
        }
    }

    @Test
    void macroClassificationUsesCustomRecommendationOnlyForCustomKind() throws Exception {
        Object custom = record("MacroClassification", new Class<?>[]{DependencyTargetMatchStatus.class,
                        DependencyRiskLevel.class, DependencyConfidence.class, String.class, String.class, Map.class},
                DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED, DependencyRiskLevel.INFO,
                DependencyConfidence.LOW, "project_or_build_custom", "original", Map.of());
        Object builtin = record("MacroClassification", new Class<?>[]{DependencyTargetMatchStatus.class,
                        DependencyRiskLevel.class, DependencyConfidence.class, String.class, String.class, Map.class},
                DependencyTargetMatchStatus.TARGET_INSTALLED, DependencyRiskLevel.INFO,
                DependencyConfidence.HIGH, "compiler_builtin", "original", Map.of());

        assertThat((String) call(custom, "recommendation", "CMakeLists.txt")).contains("自定义宏定义");
        assertThat((String) call(builtin, "recommendation", "CMakeLists.txt")).isEqualTo("original");
    }

    private DependencyAnalysisRepository.TargetComponentView component(
            String name, String version, String type, String path, String source, Map<String, Object> metadata
    ) {
        return new DependencyAnalysisRepository.TargetComponentView(name, version, type, path, source, metadata);
    }

    private Object providerFields(String version, DependencyTargetMatchStatus status, Map<String, Object> evidence)
            throws Exception {
        Class<?> type = Class.forName("cn.rvport.backend.dependency.DependencyFactExtractor$ProviderFields");
        Method method = type.getDeclaredMethod("from", String.class, DependencyTargetMatchStatus.class, Map.class);
        method.setAccessible(true);
        return method.invoke(null, version, status, evidence);
    }

    private Object provider(String packageName, String version) throws Exception {
        return record("TargetProvider", new Class<?>[]{String.class, String.class, String.class},
                packageName, version, "repository");
    }

    private void assertRelation(Object index, Object sourcePackage, String sourceVersion, Object targetProvider,
                                DependencyTargetMatchStatus targetStatus, DependencyTargetMatchStatus expected)
            throws Exception {
        Object actual = call(index, "versionRelation", sourcePackage, sourceVersion, targetProvider, targetStatus);
        assertThat(actual).isEqualTo(expected);
    }

    private Object record(String simpleName, Class<?>[] parameterTypes, Object... arguments) throws Exception {
        Class<?> type = Class.forName("cn.rvport.backend.dependency.DependencyFactExtractor$" + simpleName);
        Constructor<?> constructor = type.getDeclaredConstructor(parameterTypes);
        constructor.setAccessible(true);
        return constructor.newInstance(arguments);
    }

    private Object inner(String simpleName, Object argument) throws Exception {
        Class<?> type = Class.forName("cn.rvport.backend.dependency.DependencyFactExtractor$" + simpleName);
        Constructor<?> constructor = type.getDeclaredConstructors()[0];
        constructor.setAccessible(true);
        return constructor.newInstance(extractor, argument);
    }

    private Object innerStatic(String simpleName, String methodName, Class<?>[] parameterTypes, Object... arguments)
            throws Exception {
        Class<?> type = Class.forName("cn.rvport.backend.dependency.DependencyFactExtractor$" + simpleName);
        Method method = type.getDeclaredMethod(methodName, parameterTypes);
        method.setAccessible(true);
        return method.invoke(null, arguments);
    }

    @SuppressWarnings("unchecked")
    private <T> T call(Object target, String name, Object... arguments) throws Exception {
        Method selected = null;
        for (Method method : target.getClass().getDeclaredMethods()) {
            if (method.getName().equals(name) && method.getParameterCount() == arguments.length) {
                selected = method;
                break;
            }
        }
        if (selected == null) {
            throw new NoSuchMethodException(name);
        }
        selected.setAccessible(true);
        return (T) selected.invoke(target, arguments);
    }

    @SuppressWarnings("unchecked")
    private <T> List<T> callList(Object target, String name, Object... arguments) throws Exception {
        return (List<T>) call(target, name, arguments);
    }

    @SuppressWarnings("unchecked")
    private <K, V> Map<K, V> callMap(Object target, String name, Object... arguments) throws Exception {
        return (Map<K, V>) call(target, name, arguments);
    }

    private void assertStatus(Object decision, String expected) {
        assertThat(decision.toString()).contains("status=" + expected);
    }
}
