package cn.rvport.backend.migration;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class MigrationInputRiskPolicyTests {

    @Test
    void normalizesRiskTokensFromPlainAndCombinedDetectedLevels() {
        assertThat(MigrationInputRiskPolicy.normalizeRiskToken("high")).isEqualTo("HIGH");
        assertThat(MigrationInputRiskPolicy.normalizeRiskToken("medium/TARGET_OLDER")).isEqualTo("MEDIUM");
        assertThat(MigrationInputRiskPolicy.normalizeRiskToken("unknown")).isEqualTo("INFO");
        assertThat(MigrationInputRiskPolicy.normalizeRiskToken(null)).isEqualTo("INFO");
        assertThat(MigrationInputRiskPolicy.normalizeRiskToken("   ")).isEqualTo("INFO");
        assertThat(MigrationInputRiskPolicy.normalizeRiskToken(" /target_present")).isEqualTo("INFO");
        assertThat(MigrationInputRiskPolicy.isKnownRiskToken(" critical/target_missing ")).isTrue();
        assertThat(MigrationInputRiskPolicy.isKnownRiskToken("unknown")).isFalse();
        assertThat(MigrationInputRiskPolicy.isKnownRiskToken(null)).isFalse();
        assertThat(MigrationInputRiskPolicy.isKnownRiskToken(" ")).isFalse();
    }

    @Test
    void lowDefaultsToCandidateAndOtherKnownLevelsDefaultToConfirmed() {
        assertThat(MigrationInputRiskPolicy.defaultStatus("LOW")).isEqualTo(MigrationInputStatus.CANDIDATE);
        assertThat(MigrationInputRiskPolicy.defaultStatus("CRITICAL")).isEqualTo(MigrationInputStatus.CONFIRMED);
        assertThat(MigrationInputRiskPolicy.defaultStatus("HIGH")).isEqualTo(MigrationInputStatus.CONFIRMED);
        assertThat(MigrationInputRiskPolicy.defaultStatus("MEDIUM")).isEqualTo(MigrationInputStatus.CONFIRMED);
        assertThat(MigrationInputRiskPolicy.defaultStatus("INFO")).isEqualTo(MigrationInputStatus.CONFIRMED);
        assertThat(MigrationInputRiskPolicy.defaultStatus("COMMENT")).isEqualTo(MigrationInputStatus.CONFIRMED);
    }

    @Test
    void combinedDetectedLevelKeepsStatusAndUsesNormalizedRisk() {
        assertThat(MigrationInputRiskPolicy.normalizedDetectedLevel("low", "target_newer"))
                .isEqualTo("LOW/TARGET_NEWER");
        assertThat(MigrationInputRiskPolicy.normalizedDetectedLevel("high", null))
                .isEqualTo("HIGH/UNKNOWN");
        assertThat(MigrationInputRiskPolicy.normalizedDetectedLevel("high", " "))
                .isEqualTo("HIGH/UNKNOWN");
    }
}
