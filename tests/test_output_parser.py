"""Tests for the test output parser module."""

import pytest
from datetime import datetime

from iterm_controller.test_output_parser import (
    CargoTestParser,
    GoTestParser,
    MakeTestParser,
    NpmTestParser,
    OutputParserRegistry,
    PytestParser,
    UnitTestResults,
    parse_test_output,
)


# =============================================================================
# Pytest Parser Tests
# =============================================================================


class TestPytestParser:
    """Tests for the pytest output parser."""

    def test_can_parse_pytest_output(self):
        """Parser should recognize pytest output."""
        parser = PytestParser()
        assert parser.can_parse("======= test session starts =======")
        assert parser.can_parse("collected 10 items")
        assert parser.can_parse("test_foo.py PASSED")

    def test_cannot_parse_non_pytest_output(self):
        """Parser should not match non-pytest output."""
        parser = PytestParser()
        # These shouldn't trigger pytest detection
        assert not parser.can_parse("random text here")
        assert not parser.can_parse("npm test completed")
        # Note: Jest output with "passed" could still match weak indicators
        # but that's acceptable since the registry uses command hints

    def test_parse_simple_success(self):
        """Parse simple successful pytest output."""
        parser = PytestParser()
        output = """
======= test session starts =======
collected 5 items

test_example.py::test_one PASSED
test_example.py::test_two PASSED
test_example.py::test_three PASSED
test_example.py::test_four PASSED
test_example.py::test_five PASSED

======= 5 passed in 0.42s =======
"""
        results = parser.parse(output)
        assert results.passed == 5
        assert results.failed == 0
        assert results.skipped == 0
        assert results.duration_seconds == pytest.approx(0.42, 0.01)
        assert results.last_run is not None

    def test_parse_mixed_results(self):
        """Parse pytest output with mixed pass/fail/skip."""
        parser = PytestParser()
        output = """
======= test session starts =======
collected 10 items

test_auth.py::test_login PASSED
test_auth.py::test_logout PASSED
test_auth.py::test_timeout FAILED
test_auth.py::test_rate_limit FAILED
test_api.py::test_response SKIPPED (reason: external API)

======= short test summary info =======
FAILED test_auth.py::test_timeout - AssertionError
FAILED test_auth.py::test_rate_limit - TimeoutError

======= 2 failed, 2 passed, 1 skipped in 1.23s =======
"""
        results = parser.parse(output)
        assert results.passed == 2
        assert results.failed == 2
        assert results.skipped == 1
        assert results.duration_seconds == pytest.approx(1.23, 0.01)
        assert len(results.failed_tests) == 2
        assert results.failed_tests[0].name == "test_auth.py::test_timeout"
        assert results.failed_tests[1].name == "test_auth.py::test_rate_limit"

    def test_parse_with_errors(self):
        """Parse pytest output with collection errors."""
        parser = PytestParser()
        output = (
            "======= test session starts =======\n"
            "ERROR test_broken.py\n"
            "\n"
            "======= 1 error in 0.10s =======\n"
        )
        results = parser.parse(output)
        assert results.errors >= 1

    def test_parse_fallback_counting(self):
        """Fallback to counting PASSED/FAILED markers when summary not found."""
        parser = PytestParser()
        output = """
test_one.py::test_a PASSED
test_one.py::test_b PASSED
test_one.py::test_c FAILED
"""
        results = parser.parse(output)
        assert results.passed == 2
        assert results.failed == 1


# =============================================================================
# NPM Test Parser Tests
# =============================================================================


class TestNpmTestParser:
    """Tests for the npm test (Jest/Mocha) output parser."""

    def test_can_parse_jest_output(self):
        """Parser should recognize Jest output."""
        parser = NpmTestParser()
        assert parser.can_parse("PASS src/App.test.js")
        assert parser.can_parse("Tests:       5 passed, 5 total")
        assert parser.can_parse("Test Suites: 2 passed")

    def test_can_parse_mocha_output(self):
        """Parser should recognize Mocha output."""
        parser = NpmTestParser()
        assert parser.can_parse("5 passing (2s)")
        assert parser.can_parse("1 failing")

    def test_parse_jest_success(self):
        """Parse successful Jest output."""
        parser = NpmTestParser()
        output = """
 PASS  src/App.test.js
 PASS  src/utils.test.js
 PASS  src/api.test.js

Test Suites: 3 passed, 3 total
Tests:       12 passed, 12 total
Snapshots:   0 total
Time:        2.45 s
"""
        results = parser.parse(output)
        assert results.passed == 12
        assert results.failed == 0
        assert results.duration_seconds == pytest.approx(2.45, 0.1)

    def test_parse_jest_with_failures(self):
        """Parse Jest output with failures."""
        parser = NpmTestParser()
        output = """
 FAIL  src/App.test.js
  ● App › renders correctly

    expect(received).toEqual(expected)

 PASS  src/utils.test.js

Test Suites: 1 failed, 1 passed, 2 total
Tests:       1 failed, 2 skipped, 10 passed, 13 total
Time:        3.12 s
"""
        results = parser.parse(output)
        assert results.passed == 10
        assert results.failed == 1
        assert results.skipped == 2

    def test_parse_mocha_success(self):
        """Parse successful Mocha output."""
        parser = NpmTestParser()
        output = """
  Test Suite
    ✓ should pass first test
    ✓ should pass second test
    ✓ should pass third test

  3 passing (150ms)
"""
        results = parser.parse(output)
        assert results.passed == 3
        assert results.failed == 0
        # Duration is in ms, should be converted to seconds
        assert results.duration_seconds < 1

    def test_parse_mocha_with_failures(self):
        """Parse Mocha output with failures."""
        parser = NpmTestParser()
        output = """
  Test Suite
    ✓ should pass first test
    1) should fail this test
    ✓ should pass third test

  2 passing (2s)
  1 failing

  1) Test Suite
       should fail this test:
     AssertionError: expected 1 to equal 2
"""
        results = parser.parse(output)
        assert results.passed == 2
        assert results.failed == 1


# =============================================================================
# Cargo Test Parser Tests
# =============================================================================


class TestCargoTestParser:
    """Tests for the cargo test output parser."""

    def test_can_parse_cargo_output(self):
        """Parser should recognize cargo test output."""
        parser = CargoTestParser()
        assert parser.can_parse("running 5 tests")
        assert parser.can_parse("test result: ok")
        assert parser.can_parse("test example ... ok")

    def test_parse_success(self):
        """Parse successful cargo test output."""
        parser = CargoTestParser()
        output = """
   Compiling my_crate v0.1.0
    Finished test [unoptimized + debuginfo] target(s) in 2.15s
     Running target/debug/deps/my_crate-abc123

running 5 tests
test tests::test_one ... ok
test tests::test_two ... ok
test tests::test_three ... ok
test tests::test_four ... ok
test tests::test_five ... ok

test result: ok. 5 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.15s
"""
        results = parser.parse(output)
        assert results.passed == 5
        assert results.failed == 0
        assert results.skipped == 0
        assert results.duration_seconds == pytest.approx(0.15, 0.01)

    def test_parse_with_failures(self):
        """Parse cargo test output with failures."""
        parser = CargoTestParser()
        output = """
running 5 tests
test tests::test_one ... ok
test tests::test_two ... FAILED
test tests::test_three ... ok
test tests::test_four ... FAILED
test tests::test_five ... ok

failures:

---- tests::test_two stdout ----
thread 'tests::test_two' panicked at 'assertion failed'

---- tests::test_four stdout ----
thread 'tests::test_four' panicked at 'expected 1, got 2'


failures:
    tests::test_two
    tests::test_four

test result: FAILED. 3 passed; 2 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.23s
"""
        results = parser.parse(output)
        assert results.passed == 3
        assert results.failed == 2
        assert len(results.failed_tests) == 2

    def test_parse_with_ignored(self):
        """Parse cargo test output with ignored tests."""
        parser = CargoTestParser()
        output = """
running 4 tests
test tests::test_one ... ok
test tests::test_two ... ok
test tests::test_ignored ... ignored
test tests::test_three ... ok

test result: ok. 3 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out; finished in 0.08s
"""
        results = parser.parse(output)
        assert results.passed == 3
        assert results.failed == 0
        assert results.skipped == 1


# =============================================================================
# Go Test Parser Tests
# =============================================================================


class TestGoTestParser:
    """Tests for the go test output parser."""

    def test_can_parse_go_output(self):
        """Parser should recognize go test output."""
        parser = GoTestParser()
        assert parser.can_parse("=== RUN   TestExample")
        assert parser.can_parse("--- PASS: TestExample")
        assert parser.can_parse("ok  \tgithub.com/user/pkg")

    def test_parse_success(self):
        """Parse successful go test output."""
        parser = GoTestParser()
        output = """
=== RUN   TestOne
--- PASS: TestOne (0.00s)
=== RUN   TestTwo
--- PASS: TestTwo (0.01s)
=== RUN   TestThree
--- PASS: TestThree (0.02s)
PASS
ok  	github.com/example/pkg	0.05s
"""
        results = parser.parse(output)
        assert results.passed == 3
        assert results.failed == 0

    def test_parse_with_failures(self):
        """Parse go test output with failures."""
        parser = GoTestParser()
        output = """
=== RUN   TestOne
--- PASS: TestOne (0.00s)
=== RUN   TestTwo
    example_test.go:15: expected 1, got 2
--- FAIL: TestTwo (0.01s)
=== RUN   TestThree
--- PASS: TestThree (0.02s)
FAIL
FAIL	github.com/example/pkg	0.10s
"""
        results = parser.parse(output)
        assert results.passed == 2
        assert results.failed == 1
        assert len(results.failed_tests) == 1
        assert results.failed_tests[0].name == "TestTwo"


# =============================================================================
# Registry Tests
# =============================================================================


class TestMakeTestParser:
    """Tests for the MakeTestParser singleton behavior."""

    def test_singleton_parsers_reused(self):
        """MakeTestParser should reuse singleton parser instances."""
        parser = MakeTestParser()

        # Get parsers twice
        parsers1 = parser._get_parsers()
        parsers2 = parser._get_parsers()

        # Should be the same list with same instances
        assert parsers1 == parsers2
        for p1, p2 in zip(parsers1, parsers2):
            assert p1 is p2

    def test_delegates_to_detected_parser(self):
        """MakeTestParser should delegate to detected parser."""
        parser = MakeTestParser()

        # Pytest output embedded in make output
        output = """
make test
pytest tests/
======= 3 passed in 0.50s =======
make: leaving directory
"""
        results = parser.parse(output)
        assert results.passed == 3
        assert results.duration_seconds == 0.50

    def test_fallback_counting(self):
        """MakeTestParser should fallback to counting patterns."""
        parser = MakeTestParser()
        output = """
make test
Running tests...
PASS: test_one
PASS: test_two
FAIL: test_three
OK
make: done
"""
        results = parser.parse(output)
        # Fallback counts PASS, OK, etc.
        assert results.passed > 0


class TestParserRegistry:
    """Tests for the parser registry."""

    def test_selects_pytest_parser(self):
        """Registry should select pytest parser for pytest output."""
        output = "======= test session starts ======="
        results = parse_test_output(output, "pytest")
        assert results.test_command == "pytest"

    def test_selects_npm_parser(self):
        """Registry should select npm parser for npm test output."""
        output = "Test Suites: 1 passed, 1 total"
        results = parse_test_output(output, "npm test")
        assert results.test_command == "npm test"

    def test_fallback_to_empty_results(self):
        """Registry should return empty results for unrecognized output."""
        results = parse_test_output("some random text", "")
        assert results.last_run is not None
        assert results.passed == 0
        assert results.failed == 0

    def test_command_hint_helps_selection(self):
        """Command hint should help select correct parser."""
        # This output could match multiple parsers, but command hint should help
        output = "5 passing"
        results = parse_test_output(output, "npm test")
        assert results.test_command == "npm test"

    def test_singleton_parsers_reused(self):
        """Registry should reuse singleton parser instances."""
        registry = OutputParserRegistry()

        # Parsers should be initialized once and reused
        assert registry._pytest_parser is not None
        assert registry._npm_parser is not None
        assert registry._cargo_parser is not None
        assert registry._go_parser is not None
        assert registry._make_parser is not None

        # Command parsers dict should reference the same instances
        assert registry._command_parsers["pytest"] is registry._pytest_parser
        assert registry._command_parsers["npm"] is registry._npm_parser
        assert registry._command_parsers["cargo"] is registry._cargo_parser
        assert registry._command_parsers["go test"] is registry._go_parser

    def test_parsers_list_uses_instances(self):
        """Registry's parser list should use singleton instances."""
        registry = OutputParserRegistry()

        # All parsers in list should be the singleton instances
        assert registry._pytest_parser in registry._parsers
        assert registry._npm_parser in registry._parsers
        assert registry._cargo_parser in registry._parsers
        assert registry._go_parser in registry._parsers
        assert registry._make_parser in registry._parsers


# =============================================================================
# UnitTestResults Tests
# =============================================================================


class TestUnitTestResults:
    """Tests for the UnitTestResults dataclass."""

    def test_default_values(self):
        """Results should have sensible defaults."""
        results = UnitTestResults()
        assert results.passed == 0
        assert results.failed == 0
        assert results.skipped == 0
        assert results.errors == 0
        assert results.duration_seconds == 0
        assert results.last_run is None
        assert results.failed_tests == []
        assert results.test_command == ""
        assert results.is_running is False

    def test_populated_values(self):
        """Results should store populated values correctly."""
        results = UnitTestResults(
            passed=10,
            failed=2,
            skipped=1,
            duration_seconds=1.5,
            test_command="pytest",
            is_running=False,
        )
        assert results.passed == 10
        assert results.failed == 2
        assert results.skipped == 1
        assert results.duration_seconds == 1.5
        assert results.test_command == "pytest"
