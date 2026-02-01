"""Test output parser for unit test runners.

Parses output from pytest, npm test, cargo test, and other test runners
to extract test results for display in the UnitTestWidget.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
logger = logging.getLogger(__name__)

__all__ = [
    "TestResult",
    "UnitTestResults",
    "TestOutputParser",
    "PytestParser",
    "NpmTestParser",
    "CargoTestParser",
    "GoTestParser",
    "MakeTestParser",
    "OutputParserRegistry",
    "parse_test_output",
    "get_parser_registry",
]


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class TestResult:
    """A single test result from the unit test runner."""

    name: str  # Test name (e.g., "test_auth.py::test_login")
    passed: bool
    duration_ms: float = 0
    error_message: str | None = None


@dataclass
class UnitTestResults:
    """Results from running unit tests."""

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_seconds: float = 0
    last_run: datetime | None = None
    failed_tests: list[TestResult] = field(default_factory=list)
    test_command: str = ""
    is_running: bool = False
    raw_output: str = ""


# =============================================================================
# Abstract Parser
# =============================================================================


class TestOutputParser(ABC):
    """Base class for test output parsers."""

    @abstractmethod
    def can_parse(self, output: str) -> bool:
        """Check if this parser can handle the given output."""
        pass

    @abstractmethod
    def parse(self, output: str) -> UnitTestResults:
        """Parse test output and return results."""
        pass


# =============================================================================
# Pytest Parser
# =============================================================================


class PytestParser(TestOutputParser):
    """Parser for pytest output.

    Handles various pytest output formats:
    - Standard test results: passed, failed, skipped, errors
    - Short test summary with failure details
    - Duration information
    """

    # Patterns for pytest output
    # Main summary pattern for lines like "= 5 passed, 2 failed in 1.23s ="
    SUMMARY_PATTERN = re.compile(
        r"={2,}\s*"
        r"(?:(?P<failed>\d+)\s+failed)?,?\s*"
        r"(?:(?P<passed>\d+)\s+passed)?,?\s*"
        r"(?:(?P<skipped>\d+)\s+skipped)?,?\s*"
        r"(?:(?P<errors>\d+)\s+errors?)?,?\s*"
        r"(?:(?P<warnings>\d+)\s+warnings?)?"
        r".*?in\s+(?P<duration>[\d.]+)s"
    )

    # Alternate summary pattern with different order
    ALT_SUMMARY_PATTERN = re.compile(
        r"(?:(?P<passed>\d+) passed)"
        r"(?:,\s*(?P<failed>\d+) failed)?"
        r"(?:,\s*(?P<skipped>\d+) skipped)?"
        r"(?:,\s*(?P<errors>\d+) errors?)?"
        r"(?:.*?in\s+(?P<duration>[\d.]+)s)?"
    )

    # Error-only summary pattern for lines like "= 1 error in 0.10s ="
    ERROR_SUMMARY_PATTERN = re.compile(
        r"={2,}\s*(?P<errors>\d+)\s+errors?\s+in\s+(?P<duration>[\d.]+)s"
    )

    # Pattern for failed test names in short test summary
    FAILED_TEST_PATTERN = re.compile(r"^FAILED\s+(.+?)(?:\s+-|$)", re.MULTILINE)

    # Pattern for test errors
    ERROR_PATTERN = re.compile(r"^ERROR\s+(.+?)(?:\s+-|$)", re.MULTILINE)

    def can_parse(self, output: str) -> bool:
        """Check if output looks like pytest output."""
        # Strong indicators that uniquely identify pytest
        strong_indicators = [
            "pytest",
            "collected",
            "test session starts",
            "::test_",  # pytest test naming pattern
            ".py::Test",  # pytest class test pattern
        ]
        if any(indicator in output for indicator in strong_indicators):
            return True

        # Weak indicators - only match if combined with PASSED/FAILED markers
        # that have pytest-style spacing (space before PASSED/FAILED)
        weak_indicators = [
            " PASSED",
            " FAILED",
        ]
        return any(indicator in output for indicator in weak_indicators)

    def parse(self, output: str) -> UnitTestResults:
        """Parse pytest output."""
        results = UnitTestResults(raw_output=output)

        # Try to find summary line
        # Match the standard summary format: "= X passed, Y failed in Z.XXs ="
        match = self.SUMMARY_PATTERN.search(output)
        if not match:
            match = self.ALT_SUMMARY_PATTERN.search(output)
        if not match:
            match = self.ERROR_SUMMARY_PATTERN.search(output)

        if match:
            groups = match.groupdict()

            if groups.get("passed"):
                results.passed = int(groups["passed"])
            if groups.get("failed"):
                results.failed = int(groups["failed"])
            if groups.get("skipped"):
                results.skipped = int(groups["skipped"])
            if groups.get("errors"):
                results.errors = int(groups["errors"])
            if groups.get("duration"):
                results.duration_seconds = float(groups["duration"])

        # Fallback: count individual test results
        if results.passed == 0 and results.failed == 0 and results.errors == 0:
            results.passed = output.count(" PASSED")
            results.failed = output.count(" FAILED")
            results.skipped = output.count(" SKIPPED")
            results.errors = output.count(" ERROR")

        # Extract failed test names
        for match in self.FAILED_TEST_PATTERN.finditer(output):
            test_name = match.group(1).strip()
            results.failed_tests.append(
                TestResult(name=test_name, passed=False)
            )

        # Extract error test names
        for match in self.ERROR_PATTERN.finditer(output):
            test_name = match.group(1).strip()
            results.failed_tests.append(
                TestResult(name=test_name, passed=False, error_message="Error during collection/setup")
            )

        results.last_run = datetime.now()
        return results

    def _extract_count(self, text: str) -> int:
        """Extract count from text like '5 passed'."""
        match = re.search(r"(\d+)", text)
        if match:
            return int(match.group(1))
        return 0


# =============================================================================
# NPM Test Parser
# =============================================================================


class NpmTestParser(TestOutputParser):
    """Parser for npm test output (Jest, Mocha, etc.).

    Handles Jest and Mocha output formats commonly used in npm projects.
    """

    # Jest summary pattern
    JEST_SUMMARY_PATTERN = re.compile(
        r"Tests:\s+"
        r"(?:(?P<failed>\d+)\s+failed,\s*)?"
        r"(?:(?P<skipped>\d+)\s+skipped,\s*)?"
        r"(?:(?P<passed>\d+)\s+passed,\s*)?"
        r"(?P<total>\d+)\s+total"
    )

    # Jest time pattern
    JEST_TIME_PATTERN = re.compile(r"Time:\s+(?P<duration>[\d.]+)\s*s")

    # Mocha summary pattern
    MOCHA_SUMMARY_PATTERN = re.compile(
        r"(?P<passed>\d+)\s+passing\s+\((?P<duration>[\d.]+)(?:s|ms)\)"
    )

    MOCHA_FAILING_PATTERN = re.compile(r"(?P<failed>\d+)\s+failing")

    # Failed test patterns
    JEST_FAILED_PATTERN = re.compile(r"●\s+(.+?)$", re.MULTILINE)
    MOCHA_FAILED_PATTERN = re.compile(r"^\s*\d+\)\s+(.+?)$", re.MULTILINE)

    def can_parse(self, output: str) -> bool:
        """Check if output looks like npm test output."""
        indicators = [
            "PASS ",
            "FAIL ",
            "Test Suites:",
            "Tests:",
            "passing",
            "failing",
            "jest",
            "mocha",
        ]
        return any(indicator in output for indicator in indicators)

    def parse(self, output: str) -> UnitTestResults:
        """Parse npm test output."""
        results = UnitTestResults(raw_output=output)

        # Try Jest format first
        jest_match = self.JEST_SUMMARY_PATTERN.search(output)
        if jest_match:
            groups = jest_match.groupdict()
            if groups.get("passed"):
                results.passed = int(groups["passed"])
            if groups.get("failed"):
                results.failed = int(groups["failed"])
            if groups.get("skipped"):
                results.skipped = int(groups["skipped"])

            # Get duration
            time_match = self.JEST_TIME_PATTERN.search(output)
            if time_match:
                results.duration_seconds = float(time_match.group("duration"))

            # Extract failed test names
            for match in self.JEST_FAILED_PATTERN.finditer(output):
                test_name = match.group(1).strip()
                if test_name and not test_name.startswith("›"):
                    results.failed_tests.append(
                        TestResult(name=test_name, passed=False)
                    )

            results.last_run = datetime.now()
            return results

        # Try Mocha format
        mocha_match = self.MOCHA_SUMMARY_PATTERN.search(output)
        if mocha_match:
            groups = mocha_match.groupdict()
            results.passed = int(groups.get("passed", 0))

            duration_str = groups.get("duration", "0")
            duration = float(duration_str)
            # Convert ms to seconds if needed
            if "ms" in output[mocha_match.start():mocha_match.end() + 10]:
                duration /= 1000
            results.duration_seconds = duration

            # Check for failures
            fail_match = self.MOCHA_FAILING_PATTERN.search(output)
            if fail_match:
                results.failed = int(fail_match.group("failed"))

            # Extract failed test names
            for match in self.MOCHA_FAILED_PATTERN.finditer(output):
                test_name = match.group(1).strip()
                results.failed_tests.append(
                    TestResult(name=test_name, passed=False)
                )

            results.last_run = datetime.now()
            return results

        # Fallback: count PASS/FAIL occurrences
        results.passed = output.count("PASS ")
        results.failed = output.count("FAIL ")
        results.last_run = datetime.now()
        return results


# =============================================================================
# Cargo Test Parser
# =============================================================================


class CargoTestParser(TestOutputParser):
    """Parser for cargo test output (Rust).

    Handles Rust's cargo test output format.
    """

    # Summary pattern: "test result: ok. 10 passed; 0 failed; 0 ignored"
    SUMMARY_PATTERN = re.compile(
        r"test result:\s+(?P<status>ok|FAILED)\.\s+"
        r"(?P<passed>\d+)\s+passed;\s+"
        r"(?P<failed>\d+)\s+failed;\s+"
        r"(?P<ignored>\d+)\s+ignored"
    )

    # Duration pattern: "finished in 1.23s"
    DURATION_PATTERN = re.compile(r"finished in\s+(?P<duration>[\d.]+)s")

    # Failed test pattern
    FAILED_TEST_PATTERN = re.compile(r"^test\s+(.+?)\s+\.\.\.\s+FAILED$", re.MULTILINE)

    def can_parse(self, output: str) -> bool:
        """Check if output looks like cargo test output."""
        indicators = [
            "running",
            "test result:",
            "cargo test",
            "Compiling",
            "... ok",
            "... FAILED",
        ]
        return any(indicator in output for indicator in indicators)

    def parse(self, output: str) -> UnitTestResults:
        """Parse cargo test output."""
        results = UnitTestResults(raw_output=output)

        # Find summary
        match = self.SUMMARY_PATTERN.search(output)
        if match:
            groups = match.groupdict()
            results.passed = int(groups.get("passed", 0))
            results.failed = int(groups.get("failed", 0))
            results.skipped = int(groups.get("ignored", 0))

        # Find duration
        duration_match = self.DURATION_PATTERN.search(output)
        if duration_match:
            results.duration_seconds = float(duration_match.group("duration"))

        # Extract failed test names
        for match in self.FAILED_TEST_PATTERN.finditer(output):
            test_name = match.group(1).strip()
            results.failed_tests.append(
                TestResult(name=test_name, passed=False)
            )

        # Fallback counting
        if results.passed == 0 and results.failed == 0:
            results.passed = output.count("... ok")
            results.failed = output.count("... FAILED")

        results.last_run = datetime.now()
        return results


# =============================================================================
# Go Test Parser
# =============================================================================


class GoTestParser(TestOutputParser):
    """Parser for go test output.

    Handles Go's test output format.
    """

    # Summary patterns
    PASS_PATTERN = re.compile(r"^ok\s+", re.MULTILINE)
    FAIL_PATTERN = re.compile(r"^FAIL\s+", re.MULTILINE)

    # Individual test result pattern
    TEST_PATTERN = re.compile(
        r"^---\s+(?P<status>PASS|FAIL):\s+(?P<name>\S+)\s+\((?P<duration>[\d.]+)s\)$",
        re.MULTILINE
    )

    # Total duration pattern
    DURATION_PATTERN = re.compile(r"\s+(?P<duration>[\d.]+)s$", re.MULTILINE)

    def can_parse(self, output: str) -> bool:
        """Check if output looks like go test output."""
        indicators = [
            "go test",
            "--- PASS:",
            "--- FAIL:",
            "=== RUN",
            "ok  \t",
            "FAIL\t",
        ]
        return any(indicator in output for indicator in indicators)

    def parse(self, output: str) -> UnitTestResults:
        """Parse go test output."""
        results = UnitTestResults(raw_output=output)

        # Count individual test results
        for match in self.TEST_PATTERN.finditer(output):
            status = match.group("status")
            name = match.group("name")
            duration = float(match.group("duration"))

            if status == "PASS":
                results.passed += 1
            else:
                results.failed += 1
                results.failed_tests.append(
                    TestResult(name=name, passed=False, duration_ms=duration * 1000)
                )

        # If no individual results, count package results
        if results.passed == 0 and results.failed == 0:
            results.passed = len(self.PASS_PATTERN.findall(output))
            results.failed = len(self.FAIL_PATTERN.findall(output))

        # Try to extract duration from the last line
        duration_matches = list(self.DURATION_PATTERN.finditer(output))
        if duration_matches:
            results.duration_seconds = float(duration_matches[-1].group("duration"))

        results.last_run = datetime.now()
        return results


# =============================================================================
# Make Test Parser
# =============================================================================


class MakeTestParser(TestOutputParser):
    """Parser for make test output.

    This is a generic fallback that tries to detect test patterns.
    """

    def can_parse(self, output: str) -> bool:
        """Check if output looks like make test output."""
        return "make" in output.lower() or "makefile" in output.lower()

    def parse(self, output: str) -> UnitTestResults:
        """Parse make test output - delegates to other parsers."""
        results = UnitTestResults(raw_output=output)

        # Try to detect which test framework is being used
        parsers = [
            PytestParser(),
            NpmTestParser(),
            CargoTestParser(),
            GoTestParser(),
        ]

        for parser in parsers:
            if parser.can_parse(output):
                return parser.parse(output)

        # Generic fallback - count common patterns
        results.passed = (
            output.count("PASS") +
            output.count("OK") +
            output.count("✓")
        )
        results.failed = (
            output.count("FAIL") +
            output.count("ERROR") +
            output.count("✗")
        )
        results.last_run = datetime.now()
        return results


# =============================================================================
# Parser Registry
# =============================================================================


class OutputParserRegistry:
    """Registry of test output parsers.

    Automatically selects the appropriate parser for given output.
    """

    def __init__(self) -> None:
        """Initialize with default parsers."""
        self._parsers: list[TestOutputParser] = [
            PytestParser(),
            NpmTestParser(),
            CargoTestParser(),
            GoTestParser(),
            MakeTestParser(),
        ]

    def add_parser(self, parser: TestOutputParser) -> None:
        """Add a custom parser (inserted at the beginning for priority)."""
        self._parsers.insert(0, parser)

    def parse(self, output: str, test_command: str = "") -> UnitTestResults:
        """Parse test output using the appropriate parser.

        Args:
            output: The test runner output to parse.
            test_command: The command that was run (helps with parser selection).

        Returns:
            Parsed UnitTestResults.
        """
        # Try to select parser based on command if provided
        if test_command:
            if "pytest" in test_command:
                results = PytestParser().parse(output)
                results.test_command = test_command
                return results
            elif "npm" in test_command:
                results = NpmTestParser().parse(output)
                results.test_command = test_command
                return results
            elif "cargo" in test_command:
                results = CargoTestParser().parse(output)
                results.test_command = test_command
                return results
            elif "go test" in test_command:
                results = GoTestParser().parse(output)
                results.test_command = test_command
                return results

        # Try each parser in order
        for parser in self._parsers:
            if parser.can_parse(output):
                results = parser.parse(output)
                results.test_command = test_command
                return results

        # No parser matched - return empty results
        logger.warning("No parser matched for test output")
        results = UnitTestResults(raw_output=output, test_command=test_command)
        results.last_run = datetime.now()
        return results


# Global registry instance
_registry = OutputParserRegistry()


def parse_test_output(output: str, test_command: str = "") -> UnitTestResults:
    """Parse test output and return results.

    This is the main entry point for parsing test output.

    Args:
        output: The test runner output to parse.
        test_command: The command that was run (optional, helps with parser selection).

    Returns:
        Parsed UnitTestResults.
    """
    return _registry.parse(output, test_command)


def get_parser_registry() -> OutputParserRegistry:
    """Get the global parser registry for customization."""
    return _registry
