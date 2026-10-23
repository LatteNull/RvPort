package cn.rvport.backend.report.runtime;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.migration.MigrationInputRefView;
import cn.rvport.backend.migration.MigrationInputSourceType;
import cn.rvport.backend.migration.MigrationInputStatus;
import cn.rvport.backend.report.ReportInputProjection;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class ReportOrganizationProjectorTests {

    private final ReportOrganizationProjector projector = new ReportOrganizationProjector();

    @TempDir
    Path root;

    @Test
    void resolvesExplicitAndSharedBuildTargetsWithoutChangingFileIdentity() {
        MigrationInputRefView ref = ref(MigrationInputSourceType.KB_FINDING);
        Map<String, Object> single = snapshot(Map.of("filePath", "src/main.c", "lineStart", 7, "category", "INTRINSIC",
                "buildTarget", "app"));
        Map<String, Object> shared = snapshot(Map.of("filePath", "src/main.c", "lineStart", 7, "category", "INTRINSIC",
                "buildTargets", List.of("lib", "app")));

        ReportInputProjection direct = projector.project(ref, single, root);
        ReportInputProjection multiple = projector.project(ref, shared, root);

        assertThat(direct.moduleName()).isEqualTo("app");
        assertThat(direct.moduleBasis()).isEqualTo("EXPLICIT_BUILD_TARGET");
        assertThat(multiple.moduleName()).contains("共享代码").contains("app").contains("lib");
        assertThat(multiple.relatedModuleKeys()).hasSize(2);
        assertThat(multiple.fileKey()).isEqualTo(direct.fileKey());
    }

    @Test
    void fallsBackThroughDescriptorDirectoryAndProjectRoot() throws Exception {
        Files.createDirectories(root.resolve("module/src"));
        Files.writeString(root.resolve("module/CMakeLists.txt"), "add_library(module main.c)");
        ReportInputProjection descriptor = projector.project(ref(MigrationInputSourceType.KB_FINDING),
                snapshot(Map.of("filePath", "module/src/main.c", "lineStart", 2)), root);
        ReportInputProjection directory = projector.project(ref(MigrationInputSourceType.KB_FINDING),
                snapshot(Map.of("filePath", "other/main.c", "lineStart", 2)), root);
        ReportInputProjection projectRoot = projector.project(ref(MigrationInputSourceType.KB_FINDING),
                snapshot(Map.of("filePath", "main.c", "lineStart", 2)), root);

        assertThat(descriptor.moduleBasis()).isEqualTo("NEAREST_BUILD_DESCRIPTOR");
        assertThat(descriptor.moduleName()).isEqualTo("module");
        assertThat(directory.moduleBasis()).isEqualTo("DIRECTORY");
        assertThat(projectRoot.moduleBasis()).isEqualTo("PROJECT_ROOT");
    }

    @Test
    void marksUnsafeAndMissingLocationsAsUnlocatedAndLeavesDependenciesGlobal() {
        ReportInputProjection unsafe = projector.project(ref(MigrationInputSourceType.KB_FINDING),
                snapshot(Map.of("filePath", "../../secret.c", "lineStart", -1)), root);
        ReportInputProjection dependency = projector.project(ref(MigrationInputSourceType.DEPENDENCY_RESULT),
                snapshot(Map.of("dependencyName", "zlib")), root);

        assertThat(unsafe.moduleKey()).isEqualTo("unlocated");
        assertThat(unsafe.locationAvailable()).isFalse();
        assertThat(dependency.moduleKey()).isNull();
        assertThat(dependency.sourceType()).isEqualTo("DEPENDENCY_RESULT");
    }

    @Test
    void treatsBothSpecializedFindingTypesAsCodeFindings() {
        Map<String, Object> detail = snapshot(Map.of("filePath", "src/atomic.cpp", "lineStart", 12,
                "lineEnd", 14, "category", "MEMORY_ORDER"));

        ReportInputProjection floating = projector.project(ref(MigrationInputSourceType.FLOATING_POINT_FINDING), detail, root);
        ReportInputProjection memory = projector.project(ref(MigrationInputSourceType.MEMORY_ORDER_FINDING), detail, root);

        assertThat(floating.relativePath()).isEqualTo("src/atomic.cpp");
        assertThat(memory.moduleBasis()).isEqualTo("DIRECTORY");
        assertThat(memory.findingType()).isEqualTo("MEMORY_ORDER");
        assertThat(memory.locationAvailable()).isTrue();
    }

    @Test
    void resolvesArtifactEvidenceAbsoluteAndPrefixedPaths() throws Exception {
        Files.createDirectories(root.resolve("src"));
        Path absolute = root.resolve("src/main.c").toAbsolutePath();
        Map<String, Object> artifactDetail = new java.util.LinkedHashMap<>();
        artifactDetail.put("filePath", absolute.toString());
        artifactDetail.put("lineStart", "7");
        artifactDetail.put("lineEnd", "bad");
        artifactDetail.put("colStart", 2L);
        artifactDetail.put("endColumn", "4");
        artifactDetail.put("linkArtifact", "build\\libsample.so");
        artifactDetail.put("symbol", " ");

        ReportInputProjection artifact = projector.project(ref(MigrationInputSourceType.KB_FINDING), snapshot(artifactDetail), root);
        ReportInputProjection prefixed = projector.project(ref(MigrationInputSourceType.KB_FINDING),
                snapshot(Map.of("filePath", "<source-root>/src/main.c", "evidence",
                        Map.of("buildTargets", List.of("zeta", "alpha", "alpha")))), root);

        assertThat(artifact.moduleBasis()).isEqualTo("BUILD_ARTIFACT");
        assertThat(artifact.moduleName()).isEqualTo("libsample.so");
        assertThat(artifact.lineStart()).isEqualTo(7);
        assertThat(artifact.lineEnd()).isEqualTo(7);
        assertThat(artifact.columnStart()).isEqualTo(2);
        assertThat(artifact.columnEnd()).isEqualTo(4);
        assertThat(prefixed.relativePath()).isEqualTo("src/main.c");
        assertThat(prefixed.relatedModuleKeys()).hasSize(2);
    }

    @Test
    void recognizesSpecAndRootDescriptorsAndRejectsMalformedAbsolutePaths() throws Exception {
        Files.createDirectories(root.resolve("packaging/sub"));
        Files.writeString(root.resolve("packaging/sample.spec"), "Name: sample");
        Files.writeString(root.resolve("Makefile"), "all:\n\ttrue\n");

        ReportInputProjection spec = projector.project(ref(MigrationInputSourceType.KB_FINDING),
                snapshot(Map.of("filePath", "packaging/sub/main.c", "lineStart", 1)), root);
        ReportInputProjection rootDescriptor = projector.project(ref(MigrationInputSourceType.KB_FINDING),
                snapshot(Map.of("filePath", "main.c", "lineStart", 1)), root);
        ReportInputProjection outside = projector.project(ref(MigrationInputSourceType.KB_FINDING),
                snapshot(Map.of("filePath", root.resolveSibling("outside.c").toAbsolutePath().toString())), root);
        ReportInputProjection noRoot = projector.project(ref(MigrationInputSourceType.KB_FINDING),
                snapshot(Map.of("filePath", root.resolve("src/main.c").toAbsolutePath().toString())), null);
        ReportInputProjection malformed = projector.project(ref(MigrationInputSourceType.KB_FINDING),
                snapshot(Map.of("filePath", "bad\u0000path.c")), root);

        assertThat(spec.moduleBasis()).isEqualTo("NEAREST_BUILD_DESCRIPTOR");
        assertThat(rootDescriptor.moduleName()).isEqualTo("项目根模块");
        assertThat(outside.locationAvailable()).isFalse();
        assertThat(noRoot.locationAvailable()).isFalse();
        assertThat(malformed.locationAvailable()).isFalse();
    }

    @Test
    void handlesSparseDetailsAndNumericEdgeCases() {
        Map<String, Object> detail = new java.util.LinkedHashMap<>();
        detail.put("filePath", " src\\main.c ");
        detail.put("lineStart", 0);
        detail.put("lineEnd", -2);
        detail.put("startColumn", "not-a-number");
        detail.put("buildTargets", List.of("", "app"));
        detail.put("buildTarget", 42);

        ReportInputProjection projection = projector.project(ref(MigrationInputSourceType.KB_FINDING), snapshot(detail), Path.of("missing-root"));
        ReportInputProjection blank = projector.project(ref(MigrationInputSourceType.KB_FINDING), snapshot(Map.of("filePath", " ")), root);

        assertThat(projection.relativePath()).isEqualTo("src/main.c");
        assertThat(projection.lineStart()).isNull();
        assertThat(projection.columnStart()).isNull();
        assertThat(projection.moduleBasis()).isEqualTo("EXPLICIT_BUILD_TARGET");
        assertThat(blank.locationAvailable()).isFalse();
    }

    private Map<String, Object> snapshot(Map<String, Object> detail) {
        return Map.of("sourceDetail", detail);
    }

    private MigrationInputRefView ref(MigrationInputSourceType type) {
        UUID projectId = UUID.randomUUID();
        return new MigrationInputRefView(UUID.randomUUID(), UUID.randomUUID(), projectId, UUID.randomUUID(),
                "issue", type, UUID.randomUUID(), "HIGH/TARGET_MISSING", "src/main.c:7", "fix", "rule",
                "src/main.c", "symbol", "anchor", "fingerprint", MigrationInputStatus.CONFIRMED, null,
                OffsetDateTime.now(), OffsetDateTime.now());
    }
}
