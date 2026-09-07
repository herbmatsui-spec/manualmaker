#!/bin/bash
# Release Script for Manual Processor
# Usage: ./scripts/release.sh [version]
# Example: ./scripts/release.sh 2.1.0

set -e

VERSION=${1:-$(python -c "import src; print(src.__version__)")}
CURRENT_VERSION=$(python -c "import src; print(src.__version__)" 2>/dev/null || echo "0.0.0")

echo "============================================"
echo "Manual Processor Release Script"
echo "============================================"
echo "Current version: $CURRENT_VERSION"
echo "New version: $VERSION"
echo ""

if [ "$VERSION" = "$CURRENT_VERSION" ]; then
    read -p "Version unchanged. Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "[1/5] Running tests..."
python -m pytest tests/ -v --tb=short || { echo "Tests failed!"; exit 1; }

echo ""
echo "[2/5] Updating version in source files..."
sed -i "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" src/__init__.py

echo ""
echo "[3/5] Creating git tag..."
git add -A
git commit -m "Release v$VERSION"
git tag -a "v$VERSION" -m "Release version $VERSION"

echo ""
echo "[4/5] Building package..."
pip install build --quiet
python -m build

echo ""
echo "[5/5] Generating checksums..."
sha256sum dist/* > dist/checksums.txt
echo "Checksums:"
cat dist/checksums.txt

echo ""
echo "============================================"
echo "Release v$VERSION completed!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Review changes: git log v$CURRENT_VERSION..v$VERSION --oneline"
echo "  2. Push: git push && git push --tags"
echo "  3. Create GitHub release or run: gh release create v$VERSION"
