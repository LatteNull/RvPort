import unittest

from kb_scanner.frontends.build.cmake.test_registration import _ancestors
from .support import command as c, project


def registrations(result):
    return [r.metadata["cmake"]["testRegistration"]
            for part in result.values() for r in part.records
            if "testRegistration" in r.metadata.get("cmake", {})]


class TestRegistrationTests(unittest.TestCase):
    def test_registration_inside_unexecuted_function_is_preserved_as_candidate(self):
        result=project(c("enable_testing"), c("add_executable","app","a.c",line=2),
            c("function","register",line=3), c("add_test","NAME","x","COMMAND","app",line=4),
            c("endfunction",line=5))
        item,=registrations(result)
        self.assertEqual("candidate",item["role"])
        self.assertEqual("unknown",item["registrationStatus"])
        self.assertIn("test-registration-unsupported",item["reasonCodes"])

    def test_forward_target_and_real_source_keys(self):
        result = project(c("enable_testing"),
                         c("add_test", "NAME", "plain", "COMMAND", "app", line=2),
                         c("add_executable", "app", "main.c", line=3))
        item, = registrations(result)
        self.assertEqual("selected", item["registrationStatus"])
        self.assertEqual("selected", item["buildStatus"])
        self.assertEqual("confirmed", item["role"])
        self.assertEqual(3, len(item["sourceKeys"]))
        self.assertEqual((), item["reasonCodes"])
        self.assertEqual(["a/b", "a", "."], list(_ancestors("a/b")))

    def test_disabled_is_not_compile_exclusion_and_last_known_assignment(self):
        for value, expected in (("TRUE", "not_selected"), ("OFF", "selected")):
            result = project(c("enable_testing"), c("add_executable", "app", "x86.c", line=2),
                c("add_test", "NAME", "plain", "COMMAND", "app", line=3),
                c("set_tests_properties", "plain", "PROPERTIES", "DISABLED", "ON", line=4),
                c("set_tests_properties", "plain", "PROPERTIES", "DISABLED", value, line=5))
            item, = registrations(result)
            self.assertEqual(expected, item["registrationStatus"])
            self.assertEqual("selected", item["buildStatus"])
            source = next(r for r in result["CMakeLists.txt"].records if r.kind == "build_source")
            self.assertEqual("selected", source.metadata["selectionStatus"])

    def test_unknown_and_unsupported_registration_forms(self):
        for args in ((), ("old", "app"), ("NAME",), ("NAME", "x"),
                     ("NAME", "x", "COMMAND", "${MISSING}"),
                     ("NAME", "x", "COMMAND", "outside"),
                     ("NAME", "x", "COMMAND", "app", "CONFIGURATIONS", "Debug"),
                     ("NAME", "x", "COMMAND", "app", "WORKING_DIRECTORY", "."),
                     ("NAME", "x", "COMMAND", "app", "--filter=foo")):
            with self.subTest(args=args):
                result = project(c("enable_testing"), c("add_executable", "app", "a.c", line=2),
                                 c("add_test", *args, line=3))
                item, = registrations(result)
                self.assertEqual("unknown", item["registrationStatus"])
                self.assertTrue(item["reasonCodes"])
                self.assertTrue(result["CMakeLists.txt"].partial)

    def test_no_enable_or_non_executable_or_nonordinary_target(self):
        cases = [((), c("add_executable", "app", "a.c")),
                 ((c("enable_testing"),), c("add_library", "app", "a.c")),
                 ((c("enable_testing"),), c("add_executable", "app", "IMPORTED")),
                 ((c("enable_testing"),), c("add_executable", "app", "EXCLUDE_FROM_ALL", "a.c"))]
        for start, target in cases:
            result = project(*start, target, c("add_test", "NAME", "x", "COMMAND", "app", line=4))
            self.assertEqual("unknown", registrations(result)[0]["registrationStatus"])

    def test_duplicate_live_registration_and_duplicate_targets_are_unknown(self):
        result = project(c("enable_testing"), c("add_executable", "app", "a.c", line=2),
                         c("add_test", "NAME", "x", "COMMAND", "app", line=3),
                         c("add_test", "NAME", "x", "COMMAND", "app", line=4))
        self.assertTrue(all("test-registration-conflict" in t["reasonCodes"] for t in registrations(result)))
        result = project(c("enable_testing"), c("add_executable", "app", "a.c", line=2),
                         c("add_executable", "app", "b.c", line=3),
                         c("add_test", "NAME", "x", "COMMAND", "app", line=4))
        self.assertIn("test-target-not-unique-local-executable", registrations(result)[0]["reasonCodes"])

    def test_inactive_registration_and_properties_do_not_borrow_selection(self):
        result = project(c("enable_testing"), c("add_executable", "app", "a.c", line=2),
                         c("if", "OFF", line=3),
                         c("set_tests_properties", "plain", "PROPERTIES", "DISABLED", "ON", line=4),
                         c("add_test", "NAME", "excluded", "COMMAND", "absent", line=5),
                         c("endif", line=6),
                         c("add_test", "NAME", "plain", "COMMAND", "app", line=7))
        items = {t["name"]: t for t in registrations(result)}
        self.assertEqual("inactive", items["excluded"]["registrationStatus"])
        self.assertEqual("selected", items["plain"]["registrationStatus"])

    def test_property_invalid_value_order_and_condition(self):
        for args in (("plain",), ("plain", "PROPERTIES"), ("plain", "PROPERTIES", "DISABLED"),
                     ("plain", "PROPERTIES", "DISABLED", "${UNKNOWN}"),
                     ("plain", "PROPERTIES", "TIMEOUT", "10")):
            result = project(c("enable_testing"), c("add_executable", "app", "a.c", line=2),
                             c("add_test", "NAME", "plain", "COMMAND", "app", line=3),
                             c("set_tests_properties", *args, line=4))
            self.assertIn("test-property-unsupported-or-unknown", registrations(result)[0]["reasonCodes"])
        result = project(c("enable_testing"), c("add_executable", "app", "a.c", line=2),
                         c("set_tests_properties", "plain", "PROPERTIES", "DISABLED", "ON", line=3),
                         c("add_test", "NAME", "plain", "COMMAND", "app", line=4))
        self.assertIn("test-property-order-unknown", registrations(result)[0]["reasonCodes"])
        result = project(c("enable_testing"), c("add_executable", "app", "a.c", line=2),
                         c("add_test", "NAME", "plain", "COMMAND", "app", line=3),
                         c("if", "UNKNOWN", line=4),
                         c("set_tests_properties", "plain", "PROPERTIES", "DISABLED", "ON", line=5),
                         c("endif", line=6))
        self.assertEqual("unknown", registrations(result)[0]["registrationStatus"])

    def test_directories_do_not_merge_and_enable_inherits(self):
        extra = {"sub/CMakeLists.txt": (c("add_executable", "child", "child.c"),
                  c("add_test", "NAME", "same", "COMMAND", "child", line=2))}
        result = project(c("enable_testing"), c("add_executable", "app", "a.c", line=2),
                         c("add_test", "NAME", "same", "COMMAND", "app", line=3),
                         c("add_subdirectory", "sub", line=4), extra=extra)
        self.assertEqual({".", "sub"}, {t["directory"] for t in registrations(result)})
        self.assertTrue(all(t["registrationStatus"] == "selected" for t in registrations(result)))

    def test_unknown_target_state_isolated_fragment_and_fatal(self):
        for prefix in ((c("if", "UNKNOWN"),),
                       (c("message", "FATAL_ERROR"),)):
            result = project(c("enable_testing"), *prefix, c("add_executable", "app", "a.c", line=3),
                             c("add_test", "NAME", "x", "COMMAND", "app", line=4))
            item, = registrations(result)
            self.assertEqual("unknown", item["registrationStatus"])
            self.assertIn("test-target-selection-unknown", item["reasonCodes"])
        result = project(extra={"loose.cmake": (c("enable_testing"), c("add_test", "NAME", "x", "COMMAND", "app", line=2))})
        self.assertEqual("unknown", registrations(result)[0]["registrationStatus"])

    def test_variable_expansion_and_inactive_same_name(self):
        result = project(c("enable_testing"), c("set", "TARGET", "app", line=2),
                         c("if", "OFF", line=3), c("add_executable", "app", "old.c", line=4),
                         c("add_test", "NAME", "plain", "COMMAND", "app", line=5),
                         c("endif", line=6), c("add_executable", "app", "new.c", line=7),
                         c("add_test", "NAME", "plain", "COMMAND", "${TARGET}", line=8))
        self.assertEqual(["inactive", "selected"], [t["registrationStatus"] for t in registrations(result)])

    def test_empty_input_is_identity(self):
        self.assertEqual([], registrations(project()))
