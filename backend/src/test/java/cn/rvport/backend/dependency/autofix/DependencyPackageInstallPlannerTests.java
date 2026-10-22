package cn.rvport.backend.dependency.autofix;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.dependency.DependencyRiskLevel;
import cn.rvport.backend.dependency.DependencyTargetMatchStatus;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class DependencyPackageInstallPlannerTests {

    private final DependencyPackageInstallPlanner planner = new DependencyPackageInstallPlanner();

    @Test
    void validatesNullBlankAndQuotedPackageInputs() {
        for (String invalid : new String[]{null, " ", "bad package", "bad'package"}) {
            assertThatThrownBy(() -> planner.validatePackageName(invalid))
                    .isInstanceOf(IllegalArgumentException.class);
        }
        planner.validateVersionConstraint(null);
        planner.validateVersionConstraint(" ");
        planner.validateVersionConstraint("1.2+build:4~rc1");
    }

    @Test
    void rendersRpmInstallScriptWithExactPackageVersion() {
        String script = planner.rpmInstallScript(item("zlib-devel", "1.2.13-2", DependencyRiskLevel.MEDIUM));

        assertThat(script).contains("pkg='zlib-devel'");
        assertThat(script).contains("version_constraint='1.2.13-2'");
        assertThat(script).contains("\"$pm\" -y install");
        assertThat(script).contains("RVPORT_AUTO_FIX_INSTALLED");
    }

    @Test
    void rendersHighRiskMajorVersionFallback() {
        String script = planner.rpmInstallScript(item("gcc", "12", DependencyRiskLevel.HIGH));

        assertThat(script).contains("major_constraint='12'");
        assertThat(script).contains("RVPORT_AUTO_FIX_MAJOR_UNAVAILABLE");
    }

    @Test
    void rejectsUnsafePackageNameAndVersion() {
        assertThatThrownBy(() -> planner.rpmInstallScript(item("gcc;rm -rf /", null, DependencyRiskLevel.MEDIUM)))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> planner.rpmInstallScript(item("gcc", "12 $(bad)", DependencyRiskLevel.MEDIUM)))
                .isInstanceOf(IllegalArgumentException.class);
    }

    private DependencyAutoFixItemView item(String packageName, String version, DependencyRiskLevel riskLevel) {
        return new DependencyAutoFixItemView(
                UUID.randomUUID(),
                UUID.randomUUID(),
                UUID.randomUUID(),
                UUID.randomUUID(),
                UUID.randomUUID(),
                riskLevel,
                DependencyTargetMatchStatus.REPO_AVAILABLE,
                "source-" + packageName,
                "1",
                packageName,
                version,
                packageName,
                version,
                true,
                DependencyAutoFixItemStatus.PENDING,
                null,
                null,
                Map.of(),
                null,
                null,
                OffsetDateTime.now()
        );
    }
}
