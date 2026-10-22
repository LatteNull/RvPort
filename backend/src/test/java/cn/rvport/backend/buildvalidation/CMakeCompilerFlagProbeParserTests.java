package cn.rvport.backend.buildvalidation;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;

class CMakeCompilerFlagProbeParserTests {

    @Test
    void parsesSingleLineAndQuotedCompilerFlagProbe() {
        List<CMakeCompilerFlagProbeParser.Probe> probes = CMakeCompilerFlagProbeParser.parse("CMakeLists.txt", """
                include(CheckCCompilerFlag)
                check_c_compiler_flag("-Wall" FLAG_SUPPORTED_Wall)
                check_cxx_compiler_flag('-fvisibility=hidden' FLAG_SUPPORTED_fvisibilityhidden)
                """);

        assertThat(probes)
                .extracting(CMakeCompilerFlagProbeParser.Probe::variable)
                .containsExactly("FLAG_SUPPORTED_Wall", "FLAG_SUPPORTED_fvisibilityhidden");
        assertThat(probes.get(0).flag()).isEqualTo("-Wall");
        assertThat(probes.get(0).language()).isEqualTo("C");
        assertThat(probes.get(1).flag()).isEqualTo("-fvisibility=hidden");
        assertThat(probes.get(1).language()).isEqualTo("CXX");
    }

    @Test
    void parsesMultilineGenericCompilerFlagProbeAndIgnoresComments() {
        List<CMakeCompilerFlagProbeParser.Probe> probes = CMakeCompilerFlagProbeParser.parse("cmake/Flags.cmake", """
                # check_c_compiler_flag("-Wignored" IGNORED)
                check_compiler_flag(
                  C
                  "-fstack-protector-strong" # inline comment
                  FLAG_SUPPORTED_fstackprotectorstrong
                )
                """);

        assertThat(probes).hasSize(1);
        assertThat(probes.getFirst().variable()).isEqualTo("FLAG_SUPPORTED_fstackprotectorstrong");
        assertThat(probes.getFirst().flag()).isEqualTo("-fstack-protector-strong");
        assertThat(probes.getFirst().language()).isEqualTo("C");
        assertThat(probes.getFirst().file()).isEqualTo("cmake/Flags.cmake");
        assertThat(probes.getFirst().unresolved()).isFalse();
    }

    @Test
    void reportsUnresolvedVariableExpansionWithoutThrowing() {
        List<CMakeCompilerFlagProbeParser.Probe> probes = CMakeCompilerFlagProbeParser.parse("sub/CMakeLists.txt", """
                check_c_compiler_flag("${PROJECT_FLAG}" FLAG_SUPPORTED_dynamic)
                """);

        assertThat(probes).hasSize(1);
        assertThat(probes.getFirst().unresolved()).isTrue();
        assertThat(probes.getFirst().unresolvedReason()).isEqualTo("variable_expansion");
    }

    @Test
    void expandsCommonForeachStringRegexCompilerFlagProbePattern() {
        List<CMakeCompilerFlagProbeParser.Probe> probes = CMakeCompilerFlagProbeParser.parse("CMakeLists.txt", """
                list(APPEND custom_compiler_flags
                    -Wall
                    -fstack-protector-strong
                    -fvisibility=hidden
                )
                foreach(compiler_flag ${custom_compiler_flags})
                    string(REGEX REPLACE "[^a-zA-Z0-9]" "" current_variable ${compiler_flag})
                    CHECK_C_COMPILER_FLAG(${compiler_flag} "FLAG_SUPPORTED_${current_variable}")
                endforeach()
                """);

        assertThat(probes)
                .filteredOn(probe -> !probe.unresolved())
                .extracting(CMakeCompilerFlagProbeParser.Probe::variable)
                .contains("FLAG_SUPPORTED_Wall", "FLAG_SUPPORTED_fstackprotectorstrong", "FLAG_SUPPORTED_fvisibilityhidden");
        assertThat(probes)
                .filteredOn(probe -> probe.variable().equals("FLAG_SUPPORTED_fstackprotectorstrong"))
                .singleElement()
                .satisfies(probe -> assertThat(probe.flag()).isEqualTo("-fstack-protector-strong"));
    }

    @Test
    void acceptsNullEmptyAndTextWithoutSupportedCalls() {
        assertThat(CMakeCompilerFlagProbeParser.parse(null, null)).isEmpty();
        assertThat(CMakeCompilerFlagProbeParser.parse("CMakeLists.txt", "")).isEmpty();
        assertThat(CMakeCompilerFlagProbeParser.parse("CMakeLists.txt", "project(sample)\nmessage(STATUS ok)"))
                .isEmpty();
    }

    @Test
    void parsesGenericProbeAndEscapedQuotedArguments() {
        List<CMakeCompilerFlagProbeParser.Probe> probes = CMakeCompilerFlagProbeParser.parse(null, """
                CHECK_COMPILER_FLAG(CXX "-DNAME=\\\"quoted value\\\"" RESULT_VAR)
                """);

        assertThat(probes).singleElement().satisfies(probe -> {
            assertThat(probe.language()).isEqualTo("CXX");
            assertThat(probe.flag()).isEqualTo("-DNAME=\"quoted value\"");
            assertThat(probe.variable()).isEqualTo("RESULT_VAR");
            assertThat(probe.file()).isNull();
            assertThat(probe.function()).isEqualTo("check_compiler_flag");
        });
    }

    @Test
    void reportsInsufficientArgumentsForEverySupportedFunction() {
        List<CMakeCompilerFlagProbeParser.Probe> probes = CMakeCompilerFlagProbeParser.parse("flags.cmake", """
                check_c_compiler_flag(-Wall)
                check_cxx_compiler_flag()
                check_compiler_flag(C -Wextra)
                """);

        assertThat(probes).hasSize(3).allSatisfy(probe -> {
            assertThat(probe.unresolved()).isTrue();
            assertThat(probe.unresolvedReason()).isEqualTo("insufficient_arguments");
        });
    }

    @Test
    void reportsVariableExpansionInFlagOrResultVariable() {
        List<CMakeCompilerFlagProbeParser.Probe> probes = CMakeCompilerFlagProbeParser.parse("flags.cmake", """
                check_c_compiler_flag(${FLAG} RESULT)
                check_cxx_compiler_flag(-Wall ${RESULT})
                """);

        assertThat(probes).hasSize(2).allSatisfy(probe ->
                assertThat(probe.unresolvedReason()).isEqualTo("variable_expansion"));
    }

    @Test
    void toleratesWhitespaceCommentsNestedParenthesesAndTrailingIdentifiers() {
        List<CMakeCompilerFlagProbeParser.Probe> probes = CMakeCompilerFlagProbeParser.parse("flags.cmake", """
                check_c_compiler_flag # between name and block
                ("-DVALUE=(nested)" RESULT) suffix_without_call
                check_c_compiler_flag_without_parentheses
                """);

        assertThat(probes).singleElement().satisfies(probe -> {
            assertThat(probe.flag()).isEqualTo("-DVALUE=(nested)");
            assertThat(probe.variable()).isEqualTo("RESULT");
        });
    }

    @Test
    void reportsUnbalancedSupportedCallAndStopsSafely() {
        List<CMakeCompilerFlagProbeParser.Probe> probes = CMakeCompilerFlagProbeParser.parse("broken.cmake",
                "check_c_compiler_flag(-Wall RESULT");

        assertThat(probes).singleElement().satisfies(probe -> {
            assertThat(probe.unresolved()).isTrue();
            assertThat(probe.unresolvedReason()).isEqualTo("unbalanced_parentheses");
            assertThat(probe.variable()).isEmpty();
            assertThat(probe.flag()).isEmpty();
        });
    }

    @Test
    void expandsSetListAppendDirectValuesAndMissingVariables() {
        List<CMakeCompilerFlagProbeParser.Probe> probes = CMakeCompilerFlagProbeParser.parse("flags.cmake", """
                set(BASE_FLAGS -Wall)
                list(APPEND BASE_FLAGS -Wextra)
                list(PREPEND IGNORED -Werror)
                foreach(flag ${BASE_FLAGS} -pedantic ${MISSING_FLAGS})
                  check_cxx_compiler_flag(${flag} HAS_${flag})
                endforeach()
                """);

        assertThat(probes)
                .filteredOn(probe -> !probe.unresolved())
                .extracting(CMakeCompilerFlagProbeParser.Probe::flag)
                .contains("-Wall", "-Wextra", "-pedantic");
    }

    @Test
    void usesOriginalLoopValueWhenDerivedRegexIsInvalid() {
        List<CMakeCompilerFlagProbeParser.Probe> probes = CMakeCompilerFlagProbeParser.parse("flags.cmake", """
                foreach(flag -Wall)
                  string(REGEX REPLACE "[" "x" derived ${flag})
                  check_c_compiler_flag(${flag} ${derived})
                endforeach()
                """);

        assertThat(probes).filteredOn(probe -> !probe.unresolved()).singleElement().satisfies(probe -> {
            assertThat(probe.flag()).isEqualTo("-Wall");
            assertThat(probe.variable()).isEqualTo("-Wall");
        });
    }

    @Test
    void ignoresMalformedAndEmptyForeachForms() {
        assertThat(CMakeCompilerFlagProbeParser.parse("flags.cmake", "foreach value\nmessage(ok)"))
                .isEmpty();
        assertThat(CMakeCompilerFlagProbeParser.parse("flags.cmake", "foreach(value -Wall"))
                .isEmpty();
        assertThat(CMakeCompilerFlagProbeParser.parse("flags.cmake", "foreach(value -Wall)\nmessage(ok)"))
                .isEmpty();
        assertThat(CMakeCompilerFlagProbeParser.parse("flags.cmake", "foreach(value)\nendforeach()"))
                .isEmpty();
        assertThat(CMakeCompilerFlagProbeParser.parse("flags.cmake", "foreach(value ${MISSING})\nendforeach()"))
                .isEmpty();
    }

    @Test
    void doesNotTreatCommentedOrUnsupportedForeachBodyCallsAsProbes() {
        List<CMakeCompilerFlagProbeParser.Probe> probes = CMakeCompilerFlagProbeParser.parse("flags.cmake", """
                foreach(flag -Wall)
                  # check_c_compiler_flag(${flag} COMMENTED)
                  message(STATUS ${flag})
                  broken_call(
                endforeach()
                """);

        assertThat(probes).isEmpty();
    }

    @Test
    void toleratesCommentsAtEndOfFileAndSupportedNamesWithoutCalls() {
        assertThat(CMakeCompilerFlagProbeParser.parse("flags.cmake", "# final comment"))
                .isEmpty();
        assertThat(CMakeCompilerFlagProbeParser.parse("flags.cmake", "check_c_compiler_flag # no call"))
                .isEmpty();
        assertThat(CMakeCompilerFlagProbeParser.parse("flags.cmake", "1 + punctuation\n_check_not_supported(value)"))
                .isEmpty();
    }

    @Test
    void ignoresIncompleteListSetAndDerivedVariableDefinitions() {
        List<CMakeCompilerFlagProbeParser.Probe> probes = CMakeCompilerFlagProbeParser.parse("flags.cmake", """
                list(APPEND ONLY_NAME)
                set(ONLY_NAME)
                foreach(flag -Wall)
                  string(TOUPPER ${flag} upper)
                  string(REGEX MATCH x y ${flag})
                  string(REGEX REPLACE x y output plain)
                  check_c_compiler_flag(${flag} RESULT)
                endforeach()
                """);

        assertThat(probes).filteredOn(probe -> !probe.unresolved()).singleElement()
                .satisfies(probe -> assertThat(probe.variable()).isEqualTo("RESULT"));
    }

    @Test
    void parsesQuotedEscapesCommentsAndEmptyArgumentsAtBlockBoundaries() {
        List<CMakeCompilerFlagProbeParser.Probe> probes = CMakeCompilerFlagProbeParser.parse("flags.cmake", """
                check_c_compiler_flag("-DVALUE='x'" "RESULT") # trailing comment
                check_cxx_compiler_flag( '' EMPTY_FLAG )
                """);

        assertThat(probes).hasSize(2);
        assertThat(probes.getFirst().flag()).isEqualTo("-DVALUE='x'");
        assertThat(probes.get(1).unresolvedReason()).isEqualTo("insufficient_arguments");
    }

    @Test
    void unresolvedProbeNormalizesNullMetadataAndKeepsExplicitMetadata() {
        CMakeCompilerFlagProbeParser.Probe empty = CMakeCompilerFlagProbeParser.Probe.unresolved(
                null, null, null, null, "reason");
        CMakeCompilerFlagProbeParser.Probe explicit = CMakeCompilerFlagProbeParser.Probe.unresolved(
                "RESULT", "-Wall", "flags.cmake", "check_c_compiler_flag", "reason");

        assertThat(empty.variable()).isEmpty();
        assertThat(empty.flag()).isEmpty();
        assertThat(empty.file()).isEmpty();
        assertThat(empty.function()).isEmpty();
        assertThat(explicit.variable()).isEqualTo("RESULT");
        assertThat(explicit.flag()).isEqualTo("-Wall");
        assertThat(explicit.file()).isEqualTo("flags.cmake");
        assertThat(explicit.function()).isEqualTo("check_c_compiler_flag");
    }
}
