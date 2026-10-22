package cn.rvport.backend.dependency;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.buildvalidation.BuildValidationRunView;
import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class DependencyFactExtractorTests {

    private final DependencyFactExtractor extractor = new DependencyFactExtractor();

    @Test
    void includesRepositoryBundledElfAsDependencyCandidate() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION repositoryBundledElf third_party/libfoo.so\tELF 64-bit LSB shared object, x86-64
                RVPORT_OBSERVATION buildProducedElf build/app\tELF 64-bit LSB executable, x86-64
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log);

        assertThat(items)
                .filteredOn(item -> item.dependencyName().equals("libfoo.so"))
                .singleElement()
                .satisfies(item -> {
                    assertThat(item.dependencyType()).isEqualTo(DependencyType.RUNTIME_LIBRARY);
                    assertThat(item.dependencyName()).isEqualTo("libfoo.so");
                    assertThat(item.locationLabel()).isEqualTo("lib:libfoo.so");
                    assertThat(item.evidence()).containsEntry("buildProducedArtifact", false);
                    assertThat(item.evidence()).containsEntry("versionRelation", "MANUAL_CONFIRM_REQUIRED");
                });
        assertThat(items).noneSatisfy(item -> assertThat(item.locationLabel()).isEqualTo("elf:build/app"));
    }

    @Test
    void excludesBuildProducedLibrarySonameAndInternalNeededEntries() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION buildProducedElf build/libcjson.so.1.7.19\tELF 64-bit LSB shared object, x86-64
                RVPORT_OBSERVATION elfSoname build/libcjson.so.1.7.19\tlibcjson.so.1
                RVPORT_OBSERVATION buildProducedElf build/tests/json_patch_tests\tELF 64-bit LSB executable, x86-64
                RVPORT_OBSERVATION elfNeeded build/tests/json_patch_tests\tlibcjson.so.1
                RVPORT_OBSERVATION resolvedNeededLibrary build/tests/json_patch_tests\tsoname=libcjson.so.1\tresolver=unresolved\twarning=library_not_found
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, targetComponents());

        assertThat(items)
                .noneSatisfy(item -> assertThat(item.dependencyName()).contains("libcjson"));
    }

    @Test
    void excludesRepositoryBundledEntryWhenSamePathIsBuildProduced() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION repositoryBundledElf build/libcjson.so.1.7.19\tELF 64-bit LSB shared object, x86-64
                RVPORT_OBSERVATION buildProducedElf build/libcjson.so.1.7.19\tELF 64-bit LSB shared object, x86-64
                RVPORT_OBSERVATION elfSoname build/libcjson.so.1.7.19\tlibcjson.so.1
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, targetComponents());

        assertThat(items)
                .noneSatisfy(item -> assertThat(item.dependencyName()).contains("libcjson"));
    }

    @Test
    void excludesLibraryProducedByCmakeLinkingOutputWhenBuildProducedMarkerIsMissing() {
        DependencyAnalysisView run = run();
        String log = """
                [  3%] Linking C shared library libcjson.so
                RVPORT_OBSERVATION repositoryBundledElf build/libcjson.so.1.7.19\tELF 64-bit LSB shared object, x86-64
                RVPORT_OBSERVATION elfSoname build/libcjson.so.1.7.19\tlibcjson.so.1
                RVPORT_OBSERVATION elfNeeded build/tests/json_patch_tests\tlibcjson.so.1
                RVPORT_OBSERVATION resolvedNeededLibrary build/tests/json_patch_tests\tsoname=libcjson.so.1\tresolver=unresolved\twarning=library_not_found
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, targetComponents());

        assertThat(items)
                .noneSatisfy(item -> assertThat(item.dependencyName()).contains("libcjson"));
    }

    @Test
    void excludesBuildProducedLibraryWhenCompileDatabaseObjectParticipatesInLinkCommand() {
        DependencyAnalysisView run = run();
        String compileDatabase = """
                [
                  {
                    "directory": "/workspace/source",
                    "file": "/workspace/source/src/foo.c",
                    "command": "gcc -Iinclude -c /workspace/source/src/foo.c -o CMakeFiles/foo.dir/src/foo.c.o"
                  }
                ]
                """;
        String log = """
                gcc CMakeFiles/foo.dir/src/foo.c.o -shared -o build/libfoo.so.1.2.3
                RVPORT_OBSERVATION repositoryBundledElf build/libfoo.so.1.2.3\tELF 64-bit LSB shared object, x86-64
                RVPORT_OBSERVATION elfSoname build/libfoo.so.1.2.3\tlibfoo.so.1
                RVPORT_OBSERVATION buildProducedElf build/tests/foo_test\tELF 64-bit LSB executable, x86-64
                RVPORT_OBSERVATION elfNeeded build/tests/foo_test\tlibfoo.so.1
                RVPORT_OBSERVATION resolvedNeededLibrary build/tests/foo_test\tsoname=libfoo.so.1\tresolver=unresolved\twarning=library_not_found
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, List.of(), targetComponents(), compileDatabase);

        assertThat(items)
                .noneSatisfy(item -> assertThat(item.dependencyName()).contains("libfoo"));
    }

    @Test
    void keepsRepositoryBundledLibraryWhenCompileDatabaseHasOnlyNearbyObjectEvidence() {
        DependencyAnalysisView run = run();
        String compileDatabase = """
                [
                  {
                    "directory": "/workspace/source",
                    "file": "/workspace/source/src/foo.c",
                    "arguments": ["gcc", "-c", "src/foo.c", "-o", "build/CMakeFiles/foo.c.o"]
                  }
                ]
                """;
        String log = """
                RVPORT_OBSERVATION repositoryBundledElf build/prebuilt/libbar.so\tELF 64-bit LSB shared object, x86-64
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, List.of(), targetComponents(), compileDatabase);

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("libbar.so");
                    assertThat(item.evidence()).containsEntry("buildProducedArtifact", false);
                });
    }

    @Test
    void keepsExistingBehaviorWhenCompileDatabaseIsInvalid() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION elfSoname build/libinvalid.so.1.0\tlibinvalid.so.1
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, List.of(), targetComponents(), "{not-json");

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("libinvalid.so.1");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.NO_TARGET_VERSION_FOUND);
                });
    }

    @Test
    void keepsExternalLibraryNeededByCompileDatabaseProducedArtifact() {
        DependencyAnalysisView run = run();
        String compileDatabase = """
                [
                  {
                    "directory": "/workspace/source",
                    "file": "/workspace/source/src/foo.c",
                    "command": "gcc -c src/foo.c -o CMakeFiles/foo.dir/src/foo.c.o"
                  }
                ]
                """;
        String log = """
                gcc CMakeFiles/foo.dir/src/foo.c.o -shared -o build/libfoo.so.1
                RVPORT_OBSERVATION elfSoname build/libfoo.so.1\tlibfoo.so.1
                RVPORT_OBSERVATION elfNeeded build/libfoo.so.1\tlibc.so.6
                RVPORT_OBSERVATION resolvedNeededLibrary build/libfoo.so.1\tsoname=libc.so.6\tpath=/lib64/libc.so.6\townerPackage=glibc-2.38-18.x86_64\tresolver=ldconfig
                """;
        List<DependencyAnalysisRepository.TargetComponentView> target = List.of(packageComponent("glibc", "2.38-20"));

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, List.of(), target, compileDatabase);

        assertThat(items)
                .noneSatisfy(item -> assertThat(item.dependencyName()).contains("libfoo"))
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("glibc");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.SAME_MAJOR);
                    assertThat(item.riskLevel()).isEqualTo(DependencyRiskLevel.INFO);
                });
    }

    @Test
    void keepsExistingBehaviorWhenBuildProducedElfMarkerIsMissing() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION elfSoname build/libcjson.so.1.7.19\tlibcjson.so.1
                RVPORT_OBSERVATION elfNeeded build/tests/json_patch_tests\tlibcjson.so.1
                RVPORT_OBSERVATION resolvedNeededLibrary build/tests/json_patch_tests\tsoname=libcjson.so.1\tresolver=unresolved\twarning=library_not_found
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, targetComponents());

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("libcjson.so.1");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.NO_TARGET_VERSION_FOUND);
                });
    }

    @Test
    void keepsExternalNeededLibraryWhenProducedArtifactAlsoDependsOnProducedLibrary() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION buildProducedElf build/libcjson.so.1.7.19\tELF 64-bit LSB shared object, x86-64
                RVPORT_OBSERVATION elfSoname build/libcjson.so.1.7.19\tlibcjson.so.1
                RVPORT_OBSERVATION buildProducedElf build/tests/json_patch_tests\tELF 64-bit LSB executable, x86-64
                RVPORT_OBSERVATION elfNeeded build/tests/json_patch_tests\tlibcjson.so.1
                RVPORT_OBSERVATION elfNeeded build/tests/json_patch_tests\tlibc.so.6
                RVPORT_OBSERVATION resolvedNeededLibrary build/tests/json_patch_tests\tsoname=libcjson.so.1\tresolver=unresolved\twarning=library_not_found
                RVPORT_OBSERVATION resolvedNeededLibrary build/tests/json_patch_tests\tsoname=libc.so.6\tpath=/lib64/libc.so.6\townerPackage=glibc-2.38-18.x86_64\tresolver=ldconfig
                """;
        List<DependencyAnalysisRepository.TargetComponentView> target = List.of(packageComponent("glibc", "2.38-20"));

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, target);

        assertThat(items)
                .noneSatisfy(item -> assertThat(item.dependencyName()).contains("libcjson"))
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("glibc");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.SAME_MAJOR);
                    assertThat(item.riskLevel()).isEqualTo(DependencyRiskLevel.INFO);
                });
    }

    @Test
    void keepsSameNamedBundledLibrariesWhenPathsDiffer() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION repositoryBundledElf vendor/a/libfoo.so\tELF 64-bit LSB shared object, x86-64
                RVPORT_OBSERVATION repositoryBundledElf vendor/b/libfoo.so\tELF 64-bit LSB shared object, x86-64
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log);

        DependencyAnalysisResultItem item = items.stream()
                .filter(result -> result.dependencyName().equals("libfoo.so"))
                .findFirst()
                .orElseThrow();
        assertThat(items)
                .filteredOn(result -> result.dependencyName().equals("libfoo.so"))
                .hasSize(1);
        assertThat(item.evidence().get("evidencePaths"))
                .isInstanceOfSatisfying(List.class, paths ->
                        assertThat(paths).containsExactlyInAnyOrder("vendor/a/libfoo.so", "vendor/b/libfoo.so"));
    }

    @Test
    void matchesTargetInstalledToolRepositoryPackageAndProvides() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION buildSystemHint CMAKE\tCMakeLists.txt
                gcc main.c -lssl
                fatal error: zlib.h: No such file or directory
                RVPORT_OBSERVATION repositoryBundledElf third_party/libfoo.so\tELF 64-bit LSB shared object, x86-64
                RVPORT_OBSERVATION elfNeeded third_party/libfoo.so\tlibbar.so.1
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, targetComponents());

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("gcc");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.TARGET_INSTALLED);
                    assertThat(item.riskLevel()).isEqualTo(DependencyRiskLevel.LOW);
                })
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("libssl.so");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.PROVIDES_MATCH);
                })
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("zlib.h");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.REPO_AVAILABLE);
                })
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("libbar.so.1");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.NO_TARGET_VERSION_FOUND);
                    assertThat(item.riskLevel()).isEqualTo(DependencyRiskLevel.CRITICAL);
                });
    }

    @Test
    void exposesSourceAndTargetProviderFieldsFromEnvironmentSnapshots() {
        DependencyAnalysisView run = run();
        String log = """
                gcc main.c -lssl
                """;
        List<DependencyAnalysisRepository.TargetComponentView> sourceComponents = List.of(
                new DependencyAnalysisRepository.TargetComponentView("gcc", "12.3.1", "TOOL", "/usr/bin/gcc", "TOOL_VERSION",
                        Map.of("ownerPackage", "gcc", "ownerVersion", "12.3.1-1")),
                new DependencyAnalysisRepository.TargetComponentView("libssl.so.3", null, "LIBRARY", "/usr/lib64/libssl.so.3", "INSTALLED_FILE",
                        Map.of("ownerPackage", "openssl-libs", "ownerVersion", "3.0.9-1"))
        );

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, sourceComponents, targetComponents());

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("gcc");
                    assertThat(item.sourceProviderPackage()).isEqualTo("gcc");
                    assertThat(item.sourceProviderVersion()).isEqualTo("12.3.1-1");
                    assertThat(item.sourceDetectedVersion()).isEqualTo("12.3.1");
                    assertThat(item.targetProviderPackage()).isEqualTo("gcc");
                    assertThat(item.targetProviderVersion()).isEqualTo("14.2");
                    assertThat(item.targetDetectedVersion()).isEqualTo("14.2");
                    assertThat(item.providerVersionStatus()).isEqualTo(DependencyTargetMatchStatus.TARGET_NEWER.name());
                    assertThat(item.versionEvidenceConfidence()).isEqualTo("PACKAGE_OWNER");
                })
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("openssl-libs");
                    assertThat(item.sourceProviderPackage()).isEqualTo("openssl-libs");
                    assertThat(item.sourceProviderVersion()).isEqualTo("3.0.9-1");
                    assertThat(item.targetProviderPackage()).isEqualTo("openssl-libs");
                    assertThat(item.targetProviderVersion()).isEqualTo("3.0.9");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.SAME_MAJOR);
                    assertThat(item.versionEvidenceConfidence()).isEqualTo("PACKAGE_OWNER");
                });
    }

    @Test
    void fallsBackToManualConfirmWhenTargetSnapshotIsUnavailable() {
        DependencyAnalysisView run = run();
        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), "gcc main.c -lssl", List.of());

        assertThat(items)
                .filteredOn(item -> item.dependencyName().equals("libssl.so"))
                .allSatisfy(item -> assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED));
    }

    @Test
    void expandsCompileDatabaseSummaryIntoConcreteFacts() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION compileDatabase compile_commands.json\tcommands=2\tcompilers=gcc,ar\tincludes=include,/usr/include/foo\tdefines=HAVE_FOO,VERSION\tlibPaths=/usr/lib64\tlinkLibs=ssl,z\tstandards=c11
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, targetComponents());

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyType()).isEqualTo(DependencyType.BUILD_TOOL);
                    assertThat(item.dependencyName()).isEqualTo("gcc");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.TARGET_INSTALLED);
                    assertThat(item.evidence()).containsEntry("source", "compile_database_compiler");
                })
                .anySatisfy(item -> {
                    assertThat(item.dependencyType()).isEqualTo(DependencyType.LINK_LIBRARY);
                    assertThat(item.dependencyName()).isEqualTo("libssl.so");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.PROVIDES_MATCH);
                })
                .anySatisfy(item -> {
                    assertThat(item.locationLabel()).isEqualTo("include:include");
                    assertThat(item.evidence()).containsEntry("source", "compile_database_include_path");
                });
        assertThat(items)
                .noneSatisfy(item -> assertThat(item.locationLabel()).startsWith("define:"))
                .noneSatisfy(item -> assertThat(item.locationLabel()).startsWith("standard:"))
                .noneSatisfy(item -> assertThat(item.dependencyName()).isIn("compile-db", "build-ninja"));
    }

    @Test
    void expandsStraceExecveSummaryIntoToolsAndLinkLibraries() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION execveSummary .rvport-execve.log\texecve=10\ttools=gcc:4,ld:1
                RVPORT_OBSERVATION execveTool gcc\tcount=4\tpath=/usr/bin/gcc\tincludes=include\tdefines=HAVE_FOO\tlibPaths=/usr/lib64\tlinkLibs=ssl\tstandards=c11
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, targetComponents());

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("gcc");
                    assertThat(item.locationLabel()).isEqualTo("execve:gcc");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.TARGET_INSTALLED);
                    assertThat(item.evidence()).containsEntry("source", "strace_execve_tool");
                })
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("libssl.so");
                    assertThat(item.evidence()).containsEntry("source", "strace_execve_link_library");
                });
    }

    @Test
    void matchesCommonBuildToolAliasesAgainstTargetPackages() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION compileDatabase compile_commands.json\tcommands=2\tcompilers=cc,ar,ld\tincludes=\tdefines=\tlibPaths=\tlinkLibs=\tstandards=
                RVPORT_OBSERVATION buildNinja build.ninja\trules=1\tbuilds=1\tcommands=ninja -f build.ninja
                RVPORT_OBSERVATION execveTool ninja\tcount=1\tpath=/usr/bin/ninja\tincludes=\tdefines=\tlibPaths=\tlinkLibs=\tstandards=
                """;
        List<DependencyAnalysisRepository.TargetComponentView> components = new ArrayList<>(targetComponents());
        components.add(new DependencyAnalysisRepository.TargetComponentView("binutils", "2.42", "PACKAGE", null, "INSTALLED_PACKAGE", Map.of()));
        components.add(new DependencyAnalysisRepository.TargetComponentView("ninja-build", "1.11", "PACKAGE", null, "REPOSITORY_PACKAGE", Map.of()));

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, components);

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("cc");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.TARGET_INSTALLED);
                    assertThat(((Map<?, ?>) item.evidence().get("targetMatchEvidence")).get("matchedAlias")).isEqualTo("gcc");
                })
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("ar");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.TARGET_INSTALLED);
                    assertThat(((Map<?, ?>) item.evidence().get("targetMatchEvidence")).get("matchedAlias")).isEqualTo("binutils");
                })
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("ninja");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.REPO_AVAILABLE);
                    assertThat(((Map<?, ?>) item.evidence().get("targetMatchEvidence")).get("name")).isEqualTo("ninja-build");
                });
    }

    @Test
    void matchesSharedLibraryNameAgainstDevelopmentPackageStem() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION execveTool ld\tcount=1\tpath=/usr/bin/ld\tincludes=\tdefines=\tlibPaths=\tlinkLibs=gcc\tstandards=
                """;
        List<DependencyAnalysisRepository.TargetComponentView> components = new ArrayList<>(targetComponents());
        components.add(new DependencyAnalysisRepository.TargetComponentView("libgcc-13-dev", "13.2", "PACKAGE", null, "REPOSITORY_PACKAGE", Map.of()));

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, components);

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("libgcc.so");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.REPO_AVAILABLE);
                    assertThat(((Map<?, ?>) item.evidence().get("matchEvidence")).get("matchedAlias")).isEqualTo("libgcc");
                });
    }

    @Test
    void resolvesSourceProvidersFromInstalledPackageAliases() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION execveSummary .rvport-execve.log\texecve=4\ttools=ar:1,ninja:1
                RVPORT_OBSERVATION execveTool ar\tcount=1\tpath=/usr/bin/ar\tincludes=\tdefines=\tlibPaths=\tlinkLibs=gcc\tstandards=
                RVPORT_OBSERVATION execveTool ninja\tcount=1\tpath=/usr/bin/ninja\tincludes=\tdefines=\tlibPaths=\tlinkLibs=\tstandards=
                """;
        List<DependencyAnalysisRepository.TargetComponentView> sourceComponents = List.of(
                new DependencyAnalysisRepository.TargetComponentView("binutils", "2.41-5", "PACKAGE", null, "INSTALLED_PACKAGE", Map.of()),
                new DependencyAnalysisRepository.TargetComponentView("python3-ninja", "1.11.1", "PACKAGE", null, "INSTALLED_PACKAGE", Map.of()),
                new DependencyAnalysisRepository.TargetComponentView("libgcc", "12.3.1", "PACKAGE", null, "INSTALLED_PACKAGE", Map.of())
        );
        List<DependencyAnalysisRepository.TargetComponentView> targetComponents = List.of(
                new DependencyAnalysisRepository.TargetComponentView("binutils", "2.41-6", "PACKAGE", null, "INSTALLED_PACKAGE", Map.of()),
                new DependencyAnalysisRepository.TargetComponentView("python3-ninja", "1.11.1", "PACKAGE", null, "INSTALLED_PACKAGE", Map.of()),
                new DependencyAnalysisRepository.TargetComponentView("libgcc", "12.3.1", "PACKAGE", null, "INSTALLED_PACKAGE", Map.of())
        );

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, sourceComponents, targetComponents);

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("ar");
                    assertThat(item.sourceProviderPackage()).isEqualTo("binutils");
                    assertThat(item.sourceProviderVersion()).isEqualTo("2.41-5");
                    assertThat(item.targetProviderPackage()).isEqualTo("binutils");
                    assertThat(item.providerVersionStatus()).isEqualTo(DependencyTargetMatchStatus.SAME_MAJOR.name());
                })
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("ninja");
                    assertThat(item.sourceProviderPackage()).isEqualTo("python3-ninja");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.TARGET_INSTALLED);
                    assertThat(item.providerVersionStatus()).isEqualTo(DependencyTargetMatchStatus.SAME_MAJOR.name());
                })
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("libgcc");
                    assertThat(item.sourceProviderPackage()).isEqualTo("libgcc");
                    assertThat(item.sourceProviderVersion()).isEqualTo("12.3.1");
                    assertThat(item.targetProviderPackage()).isEqualTo("libgcc");
                    assertThat(item.providerVersionStatus()).isEqualTo(DependencyTargetMatchStatus.SAME_MAJOR.name());
                });
    }

    @Test
    void matchesObservedCxxThroughItsSourceProviderInsteadOfBareGcc() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION compileDatabase compile_commands.json\tcommands=14\tcompilers=c++\tincludes=\tdefines=\tlibPaths=\tlinkLibs=\tstandards=c++17
                RVPORT_OBSERVATION execveSummary .rvport-execve.log\texecve=22\ttools=c++:22
                RVPORT_OBSERVATION execveTool c++\tcount=22\tpath=/usr/bin/c++\tincludes=\tdefines=\tlibPaths=\tlinkLibs=\tstandards=c++17
                """;
        List<DependencyAnalysisRepository.TargetComponentView> sourceComponents = List.of(
                new DependencyAnalysisRepository.TargetComponentView(
                        "c++", "12.3.1", "TOOL", "/usr/bin/c++", "TOOL_VERSION",
                        Map.of("ownerPackage", "gcc-c++", "ownerVersion", "12.3.1-105.oe2403sp3")),
                new DependencyAnalysisRepository.TargetComponentView(
                        "gcc-c++", "12.3.1-105.oe2403sp3", "PACKAGE", null, "INSTALLED_PACKAGE", Map.of())
        );
        List<DependencyAnalysisRepository.TargetComponentView> targetComponents = List.of(
                new DependencyAnalysisRepository.TargetComponentView(
                        "gcc", "12.3.1-30.oe2403", "TOOL", "/usr/bin/gcc", "TOOL_VERSION",
                        Map.of("ownerPackage", "gcc", "ownerVersion", "12.3.1-30.oe2403")),
                new DependencyAnalysisRepository.TargetComponentView(
                        "gcc-c++", "12.3.1-30.oe2403", "PACKAGE", null, "REPOSITORY_PACKAGE", Map.of())
        );

        List<DependencyAnalysisResultItem> items = extractor.extract(
                run, buildRun(run), log, sourceComponents, targetComponents);

        assertThat(items)
                .filteredOn(item -> item.dependencyType() == DependencyType.BUILD_TOOL)
                .filteredOn(item -> item.dependencyName().equals("c++"))
                .singleElement()
                .satisfies(item -> {
                    assertThat(item.sourceProviderPackage()).isEqualTo("gcc-c++");
                    assertThat(item.sourceProviderVersion()).isEqualTo("12.3.1-105.oe2403sp3");
                    assertThat(item.targetProviderPackage()).isEqualTo("gcc-c++");
                    assertThat(item.targetProviderVersion()).isEqualTo("12.3.1-30.oe2403");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.REPO_AVAILABLE);
                    assertThat(item.riskLevel()).isEqualTo(DependencyRiskLevel.MEDIUM);
                    Map<?, ?> targetMatchEvidence = (Map<?, ?>) item.evidence().get("targetMatchEvidence");
                    assertThat(targetMatchEvidence.get("matchedBy")).isEqualTo("source-provider-package");
                    assertThat(targetMatchEvidence.get("matchedAlias")).isNotEqualTo("gcc");
                });
    }

    @Test
    void treatsInstalledGccCxxProviderAsSatisfied() {
        DependencyAnalysisResultItem item = extractCxx(
                sourceCxx("gcc-c++", "12.3.1-105"),
                List.of(new DependencyAnalysisRepository.TargetComponentView(
                        "gcc-c++", "12.3.1-30", "PACKAGE", null, "INSTALLED_PACKAGE", Map.of())));

        assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.TARGET_INSTALLED);
        assertThat(item.riskLevel()).isEqualTo(DependencyRiskLevel.LOW);
        assertThat(item.targetProviderPackage()).isEqualTo("gcc-c++");
    }

    @Test
    void doesNotTreatBareGccAsCxxWhenProviderPackageIsUnavailable() {
        DependencyAnalysisResultItem item = extractCxx(
                sourceCxx("gcc-c++", "12.3.1-105"),
                List.of(new DependencyAnalysisRepository.TargetComponentView(
                        "gcc", "12.3.1-30", "TOOL", "/usr/bin/gcc", "TOOL_VERSION", Map.of())));

        assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.MISSING);
        assertThat(item.riskLevel()).isEqualTo(DependencyRiskLevel.HIGH);
        assertThat(item.targetProviderPackage()).isBlank();
    }

    @Test
    void keepsGccAndClangCxxProvidersIsolated() {
        DependencyAnalysisResultItem item = extractCxx(
                sourceCxx("clang", "18.1.0"),
                List.of(
                        new DependencyAnalysisRepository.TargetComponentView(
                                "g++", "13.2", "TOOL", "/usr/bin/g++", "TOOL_VERSION",
                                Map.of("ownerPackage", "gcc-c++", "ownerVersion", "13.2")),
                        new DependencyAnalysisRepository.TargetComponentView(
                                "gcc-c++", "13.2", "PACKAGE", null, "REPOSITORY_PACKAGE", Map.of())));

        assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.MISSING);
        assertThat(item.targetProviderPackage()).isBlank();
    }

    @Test
    void acceptsActualCxxDriverWhenSourceProviderMetadataIsMissing() {
        DependencyAnalysisResultItem item = extractCxx(
                List.of(new DependencyAnalysisRepository.TargetComponentView(
                        "c++", "12.3.1", "TOOL", "/usr/bin/c++", "TOOL_VERSION", Map.of())),
                List.of(new DependencyAnalysisRepository.TargetComponentView(
                        "g++", "13.2", "TOOL", "/usr/bin/g++", "TOOL_VERSION",
                        Map.of("ownerPackage", "gcc-c++", "ownerVersion", "13.2"))));

        assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.TARGET_INSTALLED);
        assertThat(item.targetProviderPackage()).isEqualTo("gcc-c++");
        assertThat(((Map<?, ?>) item.evidence().get("targetMatchEvidence")).get("matchedAlias"))
                .isEqualTo("g++");
    }

    @Test
    void hidesInternalObservationToolsAndDeduplicatesRepeatedToolSources() {
        DependencyAnalysisView run = run();
        String log = """
                bear -- strace -f make
                RVPORT_OBSERVATION execveSummary .rvport-execve.log\texecve=10\ttools=bear:1,gcc:4,make:2
                RVPORT_OBSERVATION execveTool bear\tcount=1\tpath=/usr/bin/bear\tincludes=\tdefines=\tlibPaths=\tlinkLibs=\tstandards=
                RVPORT_OBSERVATION execveTool gcc\tcount=4\tpath=/usr/bin/gcc\tincludes=\tdefines=\tlibPaths=\tlinkLibs=\tstandards=
                RVPORT_OBSERVATION buildSystemHint MAKE\tMakefile
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, targetComponents());

        assertThat(items)
                .noneSatisfy(item -> assertThat(item.dependencyName()).isIn("bear", "strace"))
                .filteredOn(item -> item.dependencyName().equals("gcc"))
                .hasSize(1);
        assertThat(items)
                .filteredOn(item -> item.dependencyName().equals("make"))
                .hasSize(1);
    }

    @Test
    void treatsLibrarySearchPathAsEvidenceOnlyAndDoesNotEmitMacros() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION cmakeCompilerFlagProbe FLAG_SUPPORTED_Wall\tlanguage=C\tflag=-Wall\tfile=CMakeLists.txt\tfunction=check_c_compiler_flag
                RVPORT_OBSERVATION compileDatabase compile_commands.json\tcommands=1\tcompilers=gcc\tincludes=.\tdefines=__GNUC__,FLAG_SUPPORTED_Wall,PROJECT_FEATURE\tlibPaths=/usr/lib64,/opt/vendor/lib\tlinkLibs=ssl\tstandards=
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, targetComponents());

        assertThat(items)
                .noneSatisfy(item -> assertThat(item.locationLabel()).startsWith("libpath:"))
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("libssl.so");
                    assertThat(item.evidence()).containsEntry("librarySearchPaths", List.of("/usr/lib64", "/opt/vendor/lib"));
                })
                .noneSatisfy(item -> assertThat(item.locationLabel()).isEqualTo("include:."))
                .noneSatisfy(item -> assertThat(item.locationLabel()).startsWith("define:"));
    }

    @Test
    void doesNotClassifyFlagSupportedPrefixWithoutCmakeProbeMapping() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION compileDatabase compile_commands.json\tcommands=1\tcompilers=gcc\tincludes=\tdefines=FLAG_SUPPORTED_Wall\tlibPaths=\tlinkLibs=\tstandards=
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, targetComponents());

        assertThat(items)
                .noneSatisfy(item -> assertThat(item.dependencyName()).isEqualTo("FLAG_SUPPORTED_Wall"))
                .noneSatisfy(item -> assertThat(item.locationLabel()).startsWith("define:"));
    }

    @Test
    void classifiesCmakeCompilerFlagProbeMappingFromExecveDefine() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION cmakeCompilerFlagProbe FLAG_SUPPORTED_fvisibilityhidden\tlanguage=C\tflag=-fvisibility=hidden\tfile=cmake/Flags.cmake\tfunction=check_c_compiler_flag
                RVPORT_OBSERVATION execveTool cc\tcount=4\tpath=/usr/bin/cc\tincludes=\tdefines=FLAG_SUPPORTED_fvisibilityhidden\tlibPaths=\tlinkLibs=\tstandards=
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, targetComponents());

        assertThat(items)
                .noneSatisfy(item -> assertThat(item.dependencyName()).isEqualTo("FLAG_SUPPORTED_fvisibilityhidden"))
                .noneSatisfy(item -> assertThat(item.locationLabel()).startsWith("define:"));
    }

    @Test
    void downgradesConflictingCmakeCompilerFlagProbeMappings() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION cmakeCompilerFlagProbe FLAG_SUPPORTED_STACK\tlanguage=C\tflag=-fstack-protector\tfile=CMakeLists.txt\tfunction=check_c_compiler_flag
                RVPORT_OBSERVATION cmakeCompilerFlagProbe FLAG_SUPPORTED_STACK\tlanguage=C\tflag=-fstack-protector-strong\tfile=cmake/Flags.cmake\tfunction=check_c_compiler_flag
                RVPORT_OBSERVATION compileDatabase compile_commands.json\tcommands=1\tcompilers=gcc\tincludes=\tdefines=FLAG_SUPPORTED_STACK\tlibPaths=\tlinkLibs=\tstandards=
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, targetComponents());

        assertThat(items)
                .noneSatisfy(item -> assertThat(item.dependencyName()).isEqualTo("FLAG_SUPPORTED_STACK"))
                .noneSatisfy(item -> assertThat(item.locationLabel()).startsWith("define:"));
    }

    @Test
    void classifiesCollectedCompilerBuiltinMacrosFromBuildObservation() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION compilerBuiltinMacros gcc\tlanguage=c\tpath=/usr/bin/gcc\tcount=3\tchunk=1\tmacros=__GNUC__,__SIZE_TYPE__,__USER_LABEL_PREFIX__
                RVPORT_OBSERVATION compileDatabase compile_commands.json\tcommands=1\tcompilers=gcc\tincludes=\tdefines=__SIZE_TYPE__,PROJECT_FEATURE\tlibPaths=\tlinkLibs=\tstandards=
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, targetComponents());

        assertThat(items)
                .noneSatisfy(item -> assertThat(item.dependencyName()).isIn("__SIZE_TYPE__", "PROJECT_FEATURE"))
                .noneSatisfy(item -> assertThat(item.locationLabel()).startsWith("define:"));
    }

    @Test
    void omitsEmptyCompileDatabaseAndBuildNinjaObservationItems() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION compileDatabase compile_commands.json\tcommands=0\tcompilers=\tincludes=\tdefines=\tlibPaths=\tlinkLibs=\tstandards=
                RVPORT_OBSERVATION buildNinja build.ninja\trules=1\tbuilds=1\tcommands=
                gcc -I. main.c
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, targetComponents());

        assertThat(items)
                .noneSatisfy(item -> assertThat(item.dependencyName()).isIn("compile-db", "build-ninja", "."));
    }

    @Test
    void ignoresBuildSystemHintOnlyToolsAndMatchesObservedBuildTools() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION buildSystemHint AUTOTOOLS\tconfigure
                RVPORT_OBSERVATION buildSystemHint MESON\tmeson.build
                RVPORT_TRACE ts=2026-08-21T00:00:00Z pwd=/repo line=1 cmd=find . -maxdepth 5 -path './.git' -prune -o -type f \\( -name 'CMakeLists.txt' -o -name 'Makefile' -o -name '*.spec' -o -name 'configure' -o -name 'meson.build' -o -name 'build.ninja' \\) -print
                RVPORT_OBSERVATION execveTool rpmbuild\tcount=1\tpath=/usr/bin/rpmbuild\tincludes=\tdefines=\tlibPaths=\tlinkLibs=\tstandards=
                """;
        List<DependencyAnalysisRepository.TargetComponentView> components = new ArrayList<>(targetComponents());
        components.add(new DependencyAnalysisRepository.TargetComponentView("pyconfigure", "1", "PACKAGE", null, "REPOSITORY_PACKAGE", Map.of()));
        components.add(new DependencyAnalysisRepository.TargetComponentView("librpmbuild9t64", "9", "PACKAGE", null, "REPOSITORY_PACKAGE", Map.of()));
        components.add(new DependencyAnalysisRepository.TargetComponentView("autoconf", "2.71", "PACKAGE", null, "REPOSITORY_PACKAGE", Map.of()));
        components.add(new DependencyAnalysisRepository.TargetComponentView("meson", "1.3.1", "PACKAGE", null, "REPOSITORY_PACKAGE", Map.of()));
        components.add(new DependencyAnalysisRepository.TargetComponentView("rpm", "4.19", "PACKAGE", null, "REPOSITORY_PACKAGE", Map.of()));

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, components);

        assertThat(items)
                .noneSatisfy(item -> assertThat(item.dependencyName()).isIn("configure", "meson"))
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("rpmbuild");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.REPO_AVAILABLE);
                    assertThat(((Map<?, ?>) item.evidence().get("targetMatchEvidence")).get("matchedAlias")).isEqualTo("rpm");
                })
                .noneSatisfy(item -> {
                    Map<?, ?> evidence = (Map<?, ?>) item.evidence().get("targetMatchEvidence");
                    assertThat(evidence == null ? null : evidence.get("name")).isIn("pyconfigure", "librpmbuild9t64");
                });
    }

    @Test
    void mapsOwnedElfProviderVersionsToRiskLevels() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION repositoryBundledElf lib/libsame.so.1\tELF 64-bit LSB shared object, x86-64
                RVPORT_OBSERVATION ownerPackage lib/libsame.so.1\tlibsame-1.2.3-1.x86_64
                RVPORT_OBSERVATION repositoryBundledElf lib/libnewer.so.2\tELF 64-bit LSB shared object, x86-64
                RVPORT_OBSERVATION ownerPackage lib/libnewer.so.2\tlibnewer-2.0.0-1.x86_64
                RVPORT_OBSERVATION repositoryBundledElf lib/libolder.so.3\tELF 64-bit LSB shared object, x86-64
                RVPORT_OBSERVATION ownerPackage lib/libolder.so.3\tlibolder-3.5.0-1.x86_64
                """;
        List<DependencyAnalysisRepository.TargetComponentView> components = new ArrayList<>();
        components.add(packageComponent("libsame", "1.9.0-1"));
        components.add(packageComponent("libnewer", "4.0.0-1"));
        components.add(packageComponent("libolder", "2.9.0-1"));

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, components);

        assertProvider(items, "libsame", DependencyTargetMatchStatus.SAME_MAJOR, DependencyRiskLevel.INFO, "1.2.3-1", "1.9.0-1");
        assertProvider(items, "libnewer", DependencyTargetMatchStatus.TARGET_NEWER, DependencyRiskLevel.LOW, "2.0.0-1", "4.0.0-1");
        assertProvider(items, "libolder", DependencyTargetMatchStatus.TARGET_OLDER, DependencyRiskLevel.HIGH, "3.5.0-1", "2.9.0-1");
    }

    @Test
    void mapsUnownedElfWithVersionAndTargetProviderToMediumRisk() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION repositoryBundledElf vendor/libcustom.so.5.4.1\tELF 64-bit LSB shared object, x86-64
                """;
        List<DependencyAnalysisRepository.TargetComponentView> components = List.of(
                new DependencyAnalysisRepository.TargetComponentView("libcustom.so.5", "5.8.0", "LIBRARY", "/usr/lib64/libcustom.so.5", "REPOSITORY_PROVIDE",
                        Map.of("packageName", "custom-libs", "packageVersion", "5.8.0"))
        );

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, components);

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("libcustom.so.5.4.1");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED);
                    assertThat(item.riskLevel()).isEqualTo(DependencyRiskLevel.MEDIUM);
                    assertThat(item.evidence()).containsEntry("sourceVersionEvidence", "5.4.1");
                    assertThat(item.evidence()).containsEntry("targetProviderPackage", "custom-libs");
                });
    }

    @Test
    void mapsUnownedElfWithoutTargetVersionToCriticalRisk() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION repositoryBundledElf vendor/libunknown.so\tELF 64-bit LSB shared object, x86-64
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, targetComponents());

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("libunknown.so");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.NO_TARGET_VERSION_FOUND);
                    assertThat(item.riskLevel()).isEqualTo(DependencyRiskLevel.CRITICAL);
                });
    }

    @Test
    void usesResolvedNeededLibraryOwnerForLibcProviderEvidence() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION repositoryBundledElf bin/app\tELF 64-bit LSB executable, x86-64
                RVPORT_OBSERVATION elfNeeded bin/app\tlibc.so.6
                RVPORT_OBSERVATION resolvedNeededLibrary bin/app\tsoname=libc.so.6\tpath=/lib64/libc.so.6\townerPackage=glibc-2.38-18.x86_64\tresolver=ldconfig
                """;
        List<DependencyAnalysisRepository.TargetComponentView> target = List.of(packageComponent("glibc", "2.38-20"));

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, target);

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("glibc");
                    assertThat(item.sourceProviderPackage()).isEqualTo("glibc");
                    assertThat(item.sourceProviderVersion()).isEqualTo("2.38-18");
                    assertThat(item.targetProviderPackage()).isEqualTo("glibc");
                    assertThat(item.targetProviderVersion()).isEqualTo("2.38-20");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.SAME_MAJOR);
                    assertThat(item.riskLevel()).isEqualTo(DependencyRiskLevel.INFO);
                    assertThat(item.evidence()).containsEntry("resolvedSourceLibraryPath", "/lib64/libc.so.6");
                    assertThat(item.evidence()).containsEntry("sourceLibraryResolver", "ldconfig");
                });
    }

    @Test
    void matchesLinkLibrariesThroughSourceProviderPackagesWhenTargetLibrarySnapshotIsMissing() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION compileDatabase compile_commands.json\tcommands=1\tcompilers=gcc\tincludes=\tdefines=\tlibPaths=/usr/lib64\tlinkLibs=c,gcc_s\tstandards=
                """;
        List<DependencyAnalysisRepository.TargetComponentView> sourceComponents = List.of(
                new DependencyAnalysisRepository.TargetComponentView("libc.so.6", null, "LIBRARY", "/lib64/libc.so.6", "INSTALLED_LIBRARY",
                        Map.of("ownerPackage", "glibc", "ownerVersion", "2.38-84.oe2403sp3", "providerScanner", "rpm")),
                new DependencyAnalysisRepository.TargetComponentView("libgcc_s.so.1", null, "LIBRARY", "/usr/lib64/libgcc_s.so.1", "INSTALLED_LIBRARY",
                        Map.of("ownerPackage", "libgcc", "ownerVersion", "12.3.1-105.oe2403sp3", "providerScanner", "rpm"))
        );
        List<DependencyAnalysisRepository.TargetComponentView> targetComponents = List.of(
                packageComponent("glibc", "2.38-59.oe2403sp2"),
                packageComponent("libgcc", "12.3.1-93.oe2403sp2")
        );

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, sourceComponents, targetComponents);

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("glibc");
                    assertThat(item.sourceProviderPackage()).isEqualTo("glibc");
                    assertThat(item.sourceProviderVersion()).isEqualTo("2.38-84.oe2403sp3");
                    assertThat(item.targetProviderPackage()).isEqualTo("glibc");
                    assertThat(item.targetProviderVersion()).isEqualTo("2.38-59.oe2403sp2");
                    assertThat(item.providerVersionStatus()).isEqualTo(DependencyTargetMatchStatus.SAME_MAJOR.name());
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.SAME_MAJOR);
                    assertThat(item.riskLevel()).isEqualTo(DependencyRiskLevel.INFO);
                    assertThat(item.evidence()).containsEntry("librarySearchPaths", List.of("/usr/lib64"));
                })
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("libgcc");
                    assertThat(item.sourceProviderPackage()).isEqualTo("libgcc");
                    assertThat(item.targetProviderPackage()).isEqualTo("libgcc");
                    assertThat(item.providerVersionStatus()).isEqualTo(DependencyTargetMatchStatus.SAME_MAJOR.name());
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.SAME_MAJOR);
                });
        assertThat(items)
                .filteredOn(item -> item.dependencyType() == DependencyType.LINK_LIBRARY)
                .noneSatisfy(item -> assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.MISSING));
    }

    @Test
    void fallsBackToSourcePackageWhenTargetInstalledLibraryHasNoProviderVersion() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION compileDatabase compile_commands.json\tcommands=1\tcompilers=gcc\tincludes=\tdefines=\tlibPaths=/usr/lib64\tlinkLibs=c,gcc_s\tstandards=
                """;
        List<DependencyAnalysisRepository.TargetComponentView> sourceComponents = List.of(
                new DependencyAnalysisRepository.TargetComponentView("libc.so.6", null, "LIBRARY", "/lib64/libc.so.6", "INSTALLED_LIBRARY",
                        Map.of("ownerPackage", "glibc", "ownerVersion", "2.38-84.oe2403sp3", "providerScanner", "rpm")),
                new DependencyAnalysisRepository.TargetComponentView("libgcc_s.so.1", null, "LIBRARY", "/lib64/libgcc_s.so.1", "INSTALLED_LIBRARY",
                        Map.of("ownerPackage", "libgcc", "ownerVersion", "12.3.1-105.oe2403sp3", "providerScanner", "rpm"))
        );
        List<DependencyAnalysisRepository.TargetComponentView> targetComponents = List.of(
                new DependencyAnalysisRepository.TargetComponentView("libc.so.6", null, "LIBRARY", "/lib64/libc.so.6", "INSTALLED_LIBRARY", Map.of()),
                new DependencyAnalysisRepository.TargetComponentView("libgcc_s.so.1", null, "LIBRARY", "/lib64/libgcc_s.so.1", "INSTALLED_LIBRARY", Map.of()),
                packageComponent("glibc", "2.38-59.oe2403sp2"),
                packageComponent("libgcc", "12.3.1-93.oe2403sp2")
        );

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, sourceComponents, targetComponents);

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("glibc");
                    assertThat(item.targetProviderPackage()).isEqualTo("glibc");
                    assertThat(item.targetProviderVersion()).isEqualTo("2.38-59.oe2403sp2");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.SAME_MAJOR);
                    assertThat(item.riskLevel()).isEqualTo(DependencyRiskLevel.INFO);
                })
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("libgcc");
                    assertThat(item.targetProviderPackage()).isEqualTo("libgcc");
                    assertThat(item.targetProviderVersion()).isEqualTo("12.3.1-93.oe2403sp2");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.SAME_MAJOR);
                    assertThat(item.riskLevel()).isEqualTo(DependencyRiskLevel.INFO);
                });
    }

    @Test
    void matchesRepositoryProvidesByQueriedLibraryNameWhenPackageNameDiffers() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION compileDatabase compile_commands.json\tcommands=1\tcompilers=gcc\tincludes=\tdefines=\tlibPaths=/usr/lib64\tlinkLibs=c,gcc_s\tstandards=
                """;
        List<DependencyAnalysisRepository.TargetComponentView> sourceComponents = List.of(
                new DependencyAnalysisRepository.TargetComponentView("libc.so.6", null, "LIBRARY", "/lib64/libc.so.6", "INSTALLED_LIBRARY",
                        Map.of("ownerPackage", "glibc", "ownerVersion", "2.38-84.oe2403sp3", "providerScanner", "rpm")),
                new DependencyAnalysisRepository.TargetComponentView("libgcc_s.so.1", null, "LIBRARY", "/lib64/libgcc_s.so.1", "INSTALLED_LIBRARY",
                        Map.of("ownerPackage", "libgcc", "ownerVersion", "12.3.1-105.oe2403sp3", "providerScanner", "rpm"))
        );
        List<DependencyAnalysisRepository.TargetComponentView> targetComponents = List.of(
                new DependencyAnalysisRepository.TargetComponentView("glibc", "2.38-59.oe2403sp2", "LIBRARY", "%{location}", "REPOSITORY_PROVIDE",
                        Map.of("packageName", "glibc", "packageVersion", "2.38-59.oe2403sp2", "packageArch", "riscv64",
                                "queryPattern", "*/libc.so.6", "queryValue", "libc.so.6", "provideKind", "PATH")),
                new DependencyAnalysisRepository.TargetComponentView("libgcc", "12.3.1-93.oe2403sp2", "LIBRARY", "%{location}", "REPOSITORY_PROVIDE",
                        Map.of("packageName", "libgcc", "packageVersion", "12.3.1-93.oe2403sp2", "packageArch", "riscv64",
                                "queryPattern", "*/libgcc_s.so.1", "queryValue", "libgcc_s.so.1", "provideKind", "PATH"))
        );

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, sourceComponents, targetComponents);

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("glibc");
                    assertThat(item.sourceProviderPackage()).isEqualTo("glibc");
                    assertThat(item.targetProviderPackage()).isEqualTo("glibc");
                    assertThat(item.targetProviderVersion()).isEqualTo("2.38-59.oe2403sp2");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.SAME_MAJOR);
                    assertThat(item.riskLevel()).isEqualTo(DependencyRiskLevel.INFO);
                    assertThat(((Map<?, ?>) item.evidence().get("matchEvidence")).get("matchedBy")).isEqualTo("provides");
                })
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("libgcc");
                    assertThat(item.sourceProviderPackage()).isEqualTo("libgcc");
                    assertThat(item.targetProviderPackage()).isEqualTo("libgcc");
                    assertThat(item.targetProviderVersion()).isEqualTo("12.3.1-93.oe2403sp2");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.SAME_MAJOR);
                    assertThat(item.riskLevel()).isEqualTo(DependencyRiskLevel.INFO);
                });
    }

    @Test
    void keepsCriticalRiskWhenLinkLibraryHasNoSourceProviderAndNoTargetProvider() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION execveTool ld\tcount=1\tpath=/usr/bin/ld\tincludes=\tdefines=\tlibPaths=\tlinkLibs=missing\tstandards=
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, List.of(), targetComponents());

        assertThat(items)
                .filteredOn(item -> item.dependencyType() == DependencyType.LINK_LIBRARY)
                .filteredOn(item -> item.dependencyName().equals("libmissing.so"))
                .singleElement()
                .satisfies(item -> {
                    assertThat(item.dependencyName()).isEqualTo("libmissing.so");
                    assertThat(item.sourceProviderPackage()).isEmpty();
                    assertThat(item.targetProviderVersion()).isEmpty();
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.NO_TARGET_VERSION_FOUND);
                    assertThat(item.riskLevel()).isEqualTo(DependencyRiskLevel.CRITICAL);
                    assertThat(item.versionEvidenceConfidence()).isNull();
                });
    }

    @Test
    void fallsBackToSamePackageWhenTargetLibraryProvidesIsMissing() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION repositoryBundledElf bin/app\tELF 64-bit LSB executable, x86-64
                RVPORT_OBSERVATION elfNeeded bin/app\tlibdemo.so.1
                RVPORT_OBSERVATION resolvedNeededLibrary bin/app\tsoname=libdemo.so.1\tpath=/usr/lib64/libdemo.so.1\townerPackage=demo-libs-3.2.1-1.x86_64\tresolver=ldconfig
                """;
        List<DependencyAnalysisRepository.TargetComponentView> target = List.of(packageComponent("demo-libs", "4.0.0-1"));

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, target);

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("demo-libs");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.TARGET_NEWER);
                    assertThat(item.riskLevel()).isEqualTo(DependencyRiskLevel.LOW);
                    assertThat(item.evidence()).containsEntry("targetProviderPackage", "demo-libs");
                    @SuppressWarnings("unchecked")
                    Map<String, Object> matchEvidence = (Map<String, Object>) item.evidence().get("matchEvidence");
                    assertThat(matchEvidence).containsEntry("matchedBy", "source-owner-package-fallback");
                    assertThat(matchEvidence).containsEntry("samePackageEcosystemAssumed", true);
                    assertThat(matchEvidence).containsEntry("requestedLibrary", "libdemo.so.1");
                });
    }

    @Test
    void recordsResolutionWarningWhenNeededLibraryCannotBeResolved() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION repositoryBundledElf bin/app\tELF 64-bit LSB executable, x86-64
                RVPORT_OBSERVATION elfNeeded bin/app\tlibmissing.so.9
                RVPORT_OBSERVATION resolvedNeededLibrary bin/app\tsoname=libmissing.so.9\tresolver=unresolved\twarning=library_not_found
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, targetComponents());

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("libmissing.so.9");
                    assertThat(item.evidence()).containsEntry("sourceLibraryResolver", "unresolved");
                    assertThat(item.evidence()).containsEntry("sourceLibraryResolutionWarning", "library_not_found");
                });
    }

    @Test
    void recordsMultipleResolvedLibraryCandidates() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION repositoryBundledElf bin/app\tELF 64-bit LSB executable, x86-64
                RVPORT_OBSERVATION elfNeeded bin/app\tlibdemo.so.1
                RVPORT_OBSERVATION resolvedNeededLibrary bin/app\tsoname=libdemo.so.1\tpath=/usr/lib64/libdemo.so.1\townerPackage=demo-libs-3.2.1-1.x86_64\tresolver=ldconfig\tcandidates=/usr/lib64/libdemo.so.1,/usr/local/lib64/libdemo.so.1\twarning=multiple_candidates
                """;

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, List.of(packageComponent("demo-libs", "3.2.1-2")));

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("demo-libs");
                    assertThat(item.evidence()).containsEntry("sourceLibraryCandidates", "/usr/lib64/libdemo.so.1,/usr/local/lib64/libdemo.so.1");
                    assertThat(item.evidence()).containsEntry("sourceLibraryResolutionWarning", "multiple_candidates");
                });
    }

    @Test
    void doesNotInferCrossDistroLibcAliasForSourceOwnerFallback() {
        DependencyAnalysisView run = run();
        String log = """
                RVPORT_OBSERVATION repositoryBundledElf bin/app\tELF 64-bit LSB executable, x86-64
                RVPORT_OBSERVATION elfNeeded bin/app\tlibc.so.6
                RVPORT_OBSERVATION resolvedNeededLibrary bin/app\tsoname=libc.so.6\tpath=/lib64/libc.so.6\townerPackage=glibc-2.38-18.x86_64\tresolver=ldconfig
                """;
        List<DependencyAnalysisRepository.TargetComponentView> target = List.of(packageComponent("libc6", "2.38-1"));

        List<DependencyAnalysisResultItem> items = extractor.extract(run, buildRun(run), log, target);

        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo("glibc");
                    assertThat(item.targetProviderPackage()).isNotEqualTo("libc6");
                    assertThat(item.targetMatchStatus()).isEqualTo(DependencyTargetMatchStatus.NO_TARGET_VERSION_FOUND);
                });
    }

    private void assertProvider(List<DependencyAnalysisResultItem> items, String name,
                                DependencyTargetMatchStatus status, DependencyRiskLevel risk,
                                String sourceVersion, String targetVersion) {
        assertThat(items)
                .anySatisfy(item -> {
                    assertThat(item.dependencyName()).isEqualTo(name);
                    assertThat(item.targetMatchStatus()).isEqualTo(status);
                    assertThat(item.riskLevel()).isEqualTo(risk);
                    assertThat(item.sourceProviderPackage()).isEqualTo(name);
                    assertThat(item.sourceProviderVersion()).isEqualTo(sourceVersion);
                    assertThat(item.targetProviderPackage()).isEqualTo(name);
                    assertThat(item.targetProviderVersion()).isEqualTo(targetVersion);
                    assertThat(item.providerVersionStatus()).isEqualTo(status.name());
                    assertThat(item.versionEvidenceConfidence()).isEqualTo("PACKAGE_OWNER");
                    assertThat(item.evidence()).containsEntry("sourceOwnerVersion", sourceVersion);
                    assertThat(item.evidence()).containsEntry("targetProviderVersion", targetVersion);
                    assertThat(item.evidence()).containsEntry("versionRelation", status.name());
                });
    }

    private DependencyAnalysisView run() {
        UUID projectId = UUID.randomUUID();
        return new DependencyAnalysisView(UUID.randomUUID(), projectId, UUID.randomUUID(), UUID.randomUUID(),
                UUID.randomUUID(), UUID.randomUUID(), 1L, TaskStatus.RUNNING, Map.of(), List.of(),
                OffsetDateTime.now(), null, OffsetDateTime.now());
    }

    private DependencyAnalysisResultItem extractCxx(
            List<DependencyAnalysisRepository.TargetComponentView> sourceComponents,
            List<DependencyAnalysisRepository.TargetComponentView> targetComponents
    ) {
        DependencyAnalysisView run = run();
        List<DependencyAnalysisResultItem> items = extractor.extract(
                run,
                buildRun(run),
                "RVPORT_OBSERVATION execveTool c++\tcount=1\tpath=/usr/bin/c++\tincludes=\tdefines=\tlibPaths=\tlinkLibs=\tstandards=c++17",
                sourceComponents,
                targetComponents
        );
        return items.stream()
                .filter(item -> item.dependencyType() == DependencyType.BUILD_TOOL)
                .filter(item -> item.dependencyName().equals("c++"))
                .findFirst()
                .orElseThrow();
    }

    private List<DependencyAnalysisRepository.TargetComponentView> sourceCxx(String providerPackage, String providerVersion) {
        return List.of(new DependencyAnalysisRepository.TargetComponentView(
                "c++", "12.3.1", "TOOL", "/usr/bin/c++", "TOOL_VERSION",
                Map.of("ownerPackage", providerPackage, "ownerVersion", providerVersion)));
    }

    private BuildValidationRunView buildRun(DependencyAnalysisView run) {
        return new BuildValidationRunView(run.sourceBuildRunId(), run.projectId(), UUID.randomUUID(), run.sourceRevisionId(),
                UUID.randomUUID(), UUID.randomUUID(), null, "hash", "make", "/workspace/source",
                120, 0, TaskStatus.SUCCEEDED, null, null, null, null, OffsetDateTime.now(),
                OffsetDateTime.now(), OffsetDateTime.now(), Map.of());
    }

    private List<DependencyAnalysisRepository.TargetComponentView> targetComponents() {
        List<DependencyAnalysisRepository.TargetComponentView> components = new ArrayList<>();
        components.add(new DependencyAnalysisRepository.TargetComponentView("gcc", "14.2", "TOOL", "/usr/bin/gcc", "TOOL_VERSION", Map.of()));
        components.add(new DependencyAnalysisRepository.TargetComponentView("zlib-devel", "1.3", "PACKAGE", null, "REPOSITORY_PACKAGE",
                Map.of("providesCapabilities", "zlib.h pkgconfig(zlib)")));
        components.add(new DependencyAnalysisRepository.TargetComponentView("libssl.so.3", "3.0.9", "LIBRARY", "/usr/lib64/libssl.so.3", "REPOSITORY_PROVIDE",
                Map.of("packageName", "openssl-libs", "queryValue", "libssl.so", "packageVersion", "3.0.9")));
        components.add(new DependencyAnalysisRepository.TargetComponentView("libz.so.1", "1.3", "LIBRARY", "/usr/lib64/libz.so.1", "REPOSITORY_PROVIDE",
                Map.of("packageName", "zlib", "queryValue", "libz.so", "packageVersion", "1.3")));
        return components;
    }

    private DependencyAnalysisRepository.TargetComponentView packageComponent(String name, String version) {
        return new DependencyAnalysisRepository.TargetComponentView(name, version, "PACKAGE", null, "REPOSITORY_PACKAGE", Map.of());
    }
}
