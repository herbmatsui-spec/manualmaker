#!/usr/bin/env python3
"""
Coverage analysis script.
Analyzes coverage reports and identifies modules below threshold.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any


def analyze_coverage(coverage_file: str = "coverage.json", threshold: float = 80.0) -> int:
    """
    Analyze coverage report and check against threshold.
    
    Args:
        coverage_file: Path to coverage JSON report
        threshold: Minimum coverage percentage required
        
    Returns:
        Exit code (0=OK, 1=below threshold)
    """
    coverage_path = Path(coverage_file)
    
    if not coverage_path.exists():
        print(f"ERROR: Coverage file not found: {coverage_file}")
        print("Run 'pytest --cov=src --cov=config --cov-report=json' first")
        return 1
    
    try:
        with open(coverage_path, "r", encoding="utf-8") as f:
            coverage_data = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to read coverage file: {e}")
        return 1
    
    # Extract totals
    totals = coverage_data.get("totals", {})
    overall_coverage = totals.get("percent_covered", 0.0)
    
    print(f"Overall coverage: {overall_coverage:.1f}%")
    print(f"Threshold: {threshold:.1f}%")
    
    # Analyze per-module coverage
    print("\n=== Module Coverage Analysis ===")
    
    low_coverage_modules: List[Dict[str, Any]] = []
    
    for file_path, file_data in coverage_data.get("files", {}).items():
        # Skip test files and __pycache__
        if "tests" in file_path or "__pycache__" in file_path:
            continue
        
        summary = file_data.get("summary", {})
        module_coverage = summary.get("percent_covered", 0.0)
        module_name = file_path.replace("manual_processor/", "")
        
        if module_coverage < threshold:
            low_coverage_modules.append({
                "file": module_name,
                "coverage": module_coverage,
                "missing_lines": summary.get("missing_lines", 0),
                "total_lines": summary.get("num_statements", 0)
            })
    
    # Sort by coverage (lowest first)
    low_coverage_modules.sort(key=lambda x: x["coverage"])
    
    if low_coverage_modules:
        print(f"\n⚠️  {len(low_coverage_modules)} modules below {threshold}% coverage:")
        print(f"{'Module':<50} {'Coverage':<12} {'Missing':<10} {'Total':<10}")
        print("-" * 82)
        
        for module in low_coverage_modules:
            status = "❌" if module["coverage"] < 50 else "⚠️"
            print(f"{status} {module['file']:<49} {module['coverage']:>6.1f}%    {module['missing_lines']:>6}    {module['total_lines']:>6}")
        
        print("\nRecommendations:")
        print("  - Add unit tests for low-coverage modules")
        print("  - Use tests/utils/helpers.py to reduce test boilerplate")
        print("  - Consider integration tests for critical paths")
        
        return 1
    else:
        print(f"\n✅ All modules meet {threshold}% coverage threshold")
        return 0


def main(args: List[str] = None) -> int:
    """
    Main entry point.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code
    """
    coverage_file = "coverage.json"
    threshold = 80.0
    
    # Parse arguments
    if args:
        if "--file" in args:
            idx = args.index("--file")
            if idx + 1 < len(args):
                coverage_file = args[idx + 1]
        
        if "--threshold" in args:
            idx = args.index("--threshold")
            if idx + 1 < len(args):
                threshold = float(args[idx + 1])
    
    return analyze_coverage(coverage_file, threshold)


if __name__ == "__main__":
    sys.exit(main())
