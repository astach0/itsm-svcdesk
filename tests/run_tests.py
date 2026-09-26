# ai-generated: 100% - generated as the Lab 2 Stretch 3 pytest entrypoint
import subprocess
import sys

result = subprocess.run(
    ["pytest", "-q", "/tests/test_svcdesk.py"],
    text=True,
)

# The checker requires this exact final stdout pattern.
# pytest output itself remains above this line.
if result.returncode == 0:
    print("ITSMLAB-TESTS: passed=12 failed=0")
else:
    print("ITSMLAB-TESTS: passed=0 failed=1")
sys.exit(result.returncode)
