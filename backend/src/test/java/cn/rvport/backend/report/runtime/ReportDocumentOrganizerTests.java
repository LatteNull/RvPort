package cn.rvport.backend.report.runtime;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.migration.MigrationInputRefView;
import cn.rvport.backend.migration.MigrationInputSourceType;
import cn.rvport.backend.migration.MigrationInputStatus;
import cn.rvport.backend.report.ReportInputProjection;
import cn.rvport.backend.report.ReportRepository;
import java.time.OffsetDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class ReportDocumentOrganizerTests {
    @Test
    void formalMemoryAndFloatingResultsRemainInCodeGroups() {
        var memory = new ReportRepository.ReportInputSnapshot(ref(MigrationInputSourceType.MEMORY_ORDER_FINDING, "HIGH"),
                Map.of("sourceDetail", Map.of("pendingVerification", false)), ReportInputProjection.none("MEMORY_ORDER_FINDING", "HIGH"));
        var floating = new ReportRepository.ReportInputSnapshot(ref(MigrationInputSourceType.FLOATING_POINT_FINDING, "HIGH"),
                Map.of("sourceDetail", Map.of()), ReportInputProjection.none("FLOATING_POINT_FINDING", "HIGH"));
        var result = ReportDocumentOrganizer.organize(List.of(memory, floating));
        assertThat(result.get("codeModules").toString()).contains("findingCount=2");
        assertThat(result.get("pendingVerification")).isEqualTo(List.of());
    }
    @Test
    void manuallyIncludedSourceCandidateRemainsSeparateFromFormalRisk() {
        var ref = ref(MigrationInputSourceType.MEMORY_ORDER_FINDING, "HIGH");
        var raw = Map.<String, Object>of("sourceDetail", Map.of("pendingVerification", true, "findingKind", "SOURCE_CANDIDATE"));
        var candidate = new ReportRepository.ReportInputSnapshot(ref, raw, ReportInputProjection.none("MEMORY_ORDER_FINDING", "HIGH"));
        var organization = ReportDocumentOrganizer.organize(List.of(candidate));
        assertThat((List<?>) organization.get("codeModules")).isEmpty();
        assertThat(organization.get("pendingVerification")).isEqualTo(List.of(raw));
        assertThat(ref.status()).isEqualTo(MigrationInputStatus.CONFIRMED);
        assertThat(ref.detectedLevel()).isEqualTo("HIGH");
    }

    @Test
    void organizesCodeOnceAndGroupsDependencyEvidenceByPackage() {
        ReportRepository.ReportInputSnapshot first = code("src/a.c", "module", "HEADER", 20, "HIGH");
        ReportRepository.ReportInputSnapshot second = code("src/a.c", "module", "INTRINSIC", 5, "MEDIUM");
        ReportRepository.ReportInputSnapshot dependencyA = dependency("gcc", "LINK_LIBRARY", Map.of("library", "libgcc_s.so.1"));
        ReportRepository.ReportInputSnapshot dependencyB = dependency("gcc", "BUILD_PACKAGE", Map.of("tool", "gcc"));

        Map<String, Object> organized = ReportDocumentOrganizer.organize(List.of(first, second, dependencyA, dependencyB));

        assertThat(organized.get("rawEvidenceCount")).isEqualTo(4);
        assertThat(organized.get("codeModules").toString()).contains("findingCount=2").contains("findingTypeCount=2")
                .contains("firstLine=5").contains("highestRisk=HIGH");
        assertThat(organized.get("dependencyPackages").toString()).contains("packageName=gcc")
                .contains("LINK_LIBRARY").contains("BUILD_PACKAGE");
        assertThat((List<?>) organized.get("dependencyPackages")).hasSize(1);
    }

    @Test
    void preservesNullableDependencyEvidenceWithoutFailingReportRendering() {
        Map<String, Object> detail = new LinkedHashMap<>();
        detail.put("dependencyName", "glibc");
        detail.put("sourceProviderPackage", "glibc");
        detail.put("sourceProviderVersion", "2.38");
        detail.put("targetProviderPackage", null);
        detail.put("targetProviderVersion", null);
        detail.put("targetMatchStatus", "MISSING");
        ReportRepository.ReportInputSnapshot snapshot = new ReportRepository.ReportInputSnapshot(
                ref(MigrationInputSourceType.DEPENDENCY_RESULT, "HIGH"), Map.of("sourceDetail", detail),
                ReportInputProjection.none("DEPENDENCY_RESULT", "HIGH"));

        Map<String, Object> organization = ReportDocumentOrganizer.organize(List.of(snapshot));

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> dependencies = (List<Map<String, Object>>) organization.get("dependencyPackages");
        assertThat(dependencies).singleElement().satisfies(item -> {
            assertThat(item).containsEntry("packageName", "glibc").containsEntry("sourceVersion", "2.38");
            assertThat(item.get("targetVersion")).isNull();
        });
    }

    @Test
    void normalizesSparseCodeAndUnknownDependencyEvidence() {
        MigrationInputRefView codeRef = ref(MigrationInputSourceType.KB_FINDING, null);
        ReportInputProjection sparseProjection = new ReportInputProjection("KB_FINDING", null, null, null, null, null,
                null, null, null, null, null, null, null, null, null, null, false);
        ReportRepository.ReportInputSnapshot sparseCode = new ReportRepository.ReportInputSnapshot(
                codeRef, Map.of("sourceDetail", "invalid"), sparseProjection);
        ReportRepository.ReportInputSnapshot unknownDependency = new ReportRepository.ReportInputSnapshot(
                ref(MigrationInputSourceType.DEPENDENCY_RESULT, "ALIEN"), Map.of("sourceDetail", "invalid"),
                ReportInputProjection.none("DEPENDENCY_RESULT", "ALIEN"));
        ReportRepository.ReportInputSnapshot ignored = new ReportRepository.ReportInputSnapshot(
                ref(MigrationInputSourceType.KB_FINDING, "LOW"), Map.of(), null);

        Map<String, Object> organization = ReportDocumentOrganizer.organize(List.of(sparseCode, unknownDependency, ignored));

        assertThat(organization.get("codeModules").toString()).contains("moduleKey=unlocated")
                .contains("findingType=UNCLASSIFIED").contains("highestRisk=INFO")
                .contains("contextAvailable=false").contains("symbolCount=0");
        assertThat(organization.get("dependencyPackages").toString()).contains("packageKey=path")
                .contains("packageName=path").contains("highestRisk=ALIEN");
        assertThat(organization.get("rawEvidenceCount")).isEqualTo(3);
    }

    private ReportRepository.ReportInputSnapshot code(String path, String module, String type, int line, String risk) {
        MigrationInputRefView ref = ref(MigrationInputSourceType.KB_FINDING, risk);
        ReportInputProjection projection = new ReportInputProjection("KB_FINDING", risk, module, module, "DIRECTORY", "LOW",
                List.of(), "file", path, type, line, line, null, null, "symbol", "hash", true);
        return new ReportRepository.ReportInputSnapshot(ref, Map.of("sourceDetail", Map.of("filePath", path)), projection);
    }

    private ReportRepository.ReportInputSnapshot dependency(String packageName, String type, Map<String, Object> evidence) {
        MigrationInputRefView ref = ref(MigrationInputSourceType.DEPENDENCY_RESULT, "MEDIUM");
        ReportInputProjection projection = ReportInputProjection.none("DEPENDENCY_RESULT", "MEDIUM");
        return new ReportRepository.ReportInputSnapshot(ref, Map.of("sourceDetail", Map.of(
                "sourcePackageName", packageName, "sourcePackageVersion", "12.1", "targetPackageName", packageName,
                "targetPackageVersion", "13.2", "dependencyType", type, "targetMatchStatus", "TARGET_NEWER", "evidence", evidence
        )), projection);
    }

    private MigrationInputRefView ref(MigrationInputSourceType type, String risk) {
        return new MigrationInputRefView(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
                "issue", type, UUID.randomUUID(), risk, "location", "fix", "rule", "path", "symbol", "anchor",
                UUID.randomUUID().toString(), MigrationInputStatus.CONFIRMED, null, OffsetDateTime.now(), OffsetDateTime.now());
    }
}
