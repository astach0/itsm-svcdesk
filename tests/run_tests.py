# ai-generated: 100% - generated as the Lab 2 Stretch 3 pytest entrypoint; counts read from JUnit XML with Claude Code
import subprocess
import sys
import xml.etree.ElementTree as ET

REPORT = "/tmp/pytest-report.xml"

result = subprocess.run(
    ["pytest", "-q", f"--junitxml={REPORT}", "/tests/test_svcdesk.py"],
    text=True,
)

# Count from the JUnit report rather than hard-coding the number of tests.
try:
    suite = ET.parse(REPORT).getroot()
    if suite.tag == "testsuites":
        suite = suite.find("testsuite")
    total = int(suite.get("tests", 0))
    failed = int(suite.get("failures", 0)) + int(suite.get("errors", 0))
    skipped = int(suite.get("skipped", 0))
    passed = total - failed - skipped
except (OSError, ET.ParseError, AttributeError, ValueError):
    passed, failed = 0, 1

if result.returncode != 0 and failed == 0:
    # pytest failed without reporting a failing test (collection or usage error).
    failed = 1

# The checker requires this exact final stdout pattern.
# pytest output itself remains above this line.
sys.stdout.flush()
print(f"ITSMLAB-TESTS: passed={passed} failed={failed}")
sys.exit(result.returncode)
