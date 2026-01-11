#!/bin/bash
# FlowWatch Production Readiness Check
# Run with: ./scripts/check_release.sh

set -e

cd "$(dirname "$0")/.."

echo "
╔══════════════════════════════════════════════════════════════╗
║           FLOWWATCH PRODUCTION READINESS CHECKLIST           ║
╚══════════════════════════════════════════════════════════════╝
"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    FAILED=1
}

FAILED=0

# Tests
echo "Running tests..."
if uv run pytest tests/ -q 2>&1 | grep -q "passed"; then
    TESTS=$(uv run pytest tests/ -q 2>&1 | grep passed)
    check_pass "Tests:        $TESTS"
else
    check_fail "Tests:        FAILED"
fi

# Lint
echo "Running linter..."
if uv run ruff check src/ examples/ 2>&1 | grep -q "All checks passed"; then
    check_pass "Lint:         All checks passed"
else
    check_fail "Lint:         Issues found"
    uv run ruff check src/ examples/
fi

# Type check
echo "Running type checker..."
if uv run mypy src/ --ignore-missing-imports 2>&1 | grep -q "Success"; then
    check_pass "Type check:   No issues found"
else
    check_fail "Type check:   Issues found"
    uv run mypy src/ --ignore-missing-imports
fi

# License
if [ -f "LICENSE" ]; then
    check_pass "License:      Present (MIT)"
else
    check_fail "License:      MISSING!"
fi

# Version
VERSION=$(grep 'version = ' pyproject.toml | head -1 | cut -d'"' -f2)
check_pass "Version:      $VERSION"

# py.typed
if [ -f "src/flowwatch/py.typed" ]; then
    check_pass "py.typed:     Present (PEP 561)"
else
    check_fail "py.typed:     MISSING!"
fi

# README
README_LINES=$(wc -l < README.md | tr -d ' ')
check_pass "README:       $README_LINES lines"

# CONTRIBUTING
CONTRIB_LINES=$(wc -l < CONTRIBUTING.md | tr -d ' ')
check_pass "CONTRIBUTING: $CONTRIB_LINES lines"

# Examples
EXAMPLE_COUNT=$(ls examples/*.py 2>/dev/null | wc -l | tr -d ' ')
check_pass "Examples:     $EXAMPLE_COUNT files"

echo ""
echo "=== Package Exports ==="
uv run python -c "import flowwatch; print('  Count:', len(flowwatch.__all__))"

echo ""
echo "=== Optional Extras ==="
grep -E "^(dashboard|fastapi|all) = " pyproject.toml | sed 's/^/  /'

echo ""
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}                    ✓ READY FOR RELEASE                       ${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
else
    echo -e "${RED}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}                    ✗ NOT READY - FIX ISSUES                   ${NC}"
    echo -e "${RED}══════════════════════════════════════════════════════════════${NC}"
    exit 1
fi
