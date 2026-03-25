#!/usr/bin/env python3
"""
Test script for MCP path resolution improvements.
Tests case-insensitive matching, fuzzy matching, and file suggestions.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src" / "mcp"))

# Set environment variables for testing
os.environ["OBSIDIAN_VAULT_PATH"] = "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"

# Import the functions we want to test
from obsidian_rag_unified_mcp import _get_vault_root, _resolve_vault_path, _find_similar_files


def test_vault_root():
    """Test that vault root is correctly configured."""
    print("=" * 80)
    print("TEST 1: Vault Root Configuration")
    print("=" * 80)

    vault_root = _get_vault_root()
    if vault_root:
        print(f"✅ Vault root found: {vault_root}")
        print(f"   Exists: {vault_root.exists()}")
        return True
    else:
        print("❌ Vault root not configured")
        return False


def test_exact_case_insensitive_match():
    """Test case-insensitive file matching."""
    print("\n" + "=" * 80)
    print("TEST 2: Case-Insensitive Exact Match")
    print("=" * 80)

    test_cases = [
        # (input_path, should_exist)
        ("Lymphoma Progession Assessment.md", True),
        ("lymphoma progession assessment.md", True),  # lowercase
        ("LYMPHOMA PROGESSION ASSESSMENT.MD", True),  # uppercase
        ("Medical/Lymphoma/media/1st PET Scan.pdf", True),
        ("Medical/Lymphoma/media/1ST PET SCAN.PDF", True),  # uppercase
    ]

    results = []
    for path, should_exist in test_cases:
        resolved, error = _resolve_vault_path(path)
        success = (resolved is not None) == should_exist

        if success:
            print(f"✅ '{path}'")
            if resolved:
                print(f"   → Found: {resolved.name}")
        else:
            print(f"❌ '{path}'")
            if error:
                print(f"   Error: {error}")

        results.append(success)

    return all(results)


def test_fuzzy_matching():
    """Test fuzzy file name matching with suggestions."""
    print("\n" + "=" * 80)
    print("TEST 3: Fuzzy Matching with Suggestions")
    print("=" * 80)

    test_cases = [
        # (path, requires_path_context)
        # Files that don't exist exactly but have similar matches
        ("Lymphoma Progession Assessment Log.md", False),  # Extra "Log" word, at root
        ("Medical/Lymphoma/media/1st PET-CT.pdf", False),  # Hyphen instead of space, with path
        ("Medical/Lymphoma/media/2nd PET-CT scan.pdf", False),  # Another variant
    ]

    results = []
    for path, requires_context in test_cases:
        print(f"\nTesting: '{path}'")
        resolved, error = _resolve_vault_path(path)

        if resolved is None and error and "Did you mean" in error:
            print(f"✅ Got helpful suggestions:")
            print(error)
            results.append(True)
        elif resolved is not None:
            print(f"✅ Found exact match: {resolved.name}")
            results.append(True)
        else:
            # Fuzzy matching without path context may not find files due to vault size
            # This is expected behavior - user should provide some path context
            if requires_context:
                print(f"⚠️  No suggestions (expected - needs path context)")
                results.append(True)
            else:
                print(f"❌ No match and no suggestions")
                if error:
                    print(f"   Error: {error}")
                results.append(False)

    return all(results)


def test_specific_failing_files():
    """Test the specific files that were failing before the fix."""
    print("\n" + "=" * 80)
    print("TEST 4: Previously Failing Files")
    print("=" * 80)

    test_cases = [
        {
            "name": "Lymphoma Progression Assessment (root level)",
            "path": "Lymphoma Progession Assessment.md",
            "expected": True
        },
        {
            "name": "1st PET Scan PDF",
            "path": "Medical/Lymphoma/media/1st PET Scan.pdf",
            "expected": True
        },
        {
            "name": "3rd PET Scan PDF",
            "path": "Medical/Lymphoma/media/3rd PET Scan.pdf",
            "expected": True
        },
        {
            "name": "4th PET Scan PDF",
            "path": "Medical/Lymphoma/media/4th PET Scan.pdf",
            "expected": True
        },
    ]

    results = []
    for test_case in test_cases:
        name = test_case["name"]
        path = test_case["path"]
        expected = test_case["expected"]

        resolved, error = _resolve_vault_path(path)
        success = (resolved is not None) == expected

        if success:
            print(f"✅ {name}")
            if resolved:
                print(f"   Path: {resolved.relative_to(_get_vault_root())}")
        else:
            print(f"❌ {name}")
            if error:
                print(f"   Error: {error}")

        results.append(success)

    return all(results)


def test_similar_files_function():
    """Test the _find_similar_files function directly."""
    print("\n" + "=" * 80)
    print("TEST 5: Similar Files Function")
    print("=" * 80)

    vault_root = _get_vault_root()
    if not vault_root:
        print("❌ Vault root not configured")
        return False

    test_cases = [
        ("assessment.md", "Should find assessment-related files"),
        ("PET Scan.pdf", "Should find PET scan PDFs"),
        ("Lymphoma.md", "Should find Lymphoma notes"),
    ]

    results = []
    for target_name, description in test_cases:
        print(f"\nSearching for similar files to: '{target_name}'")
        print(f"  ({description})")

        similar = _find_similar_files(vault_root, target_name, vault_root)

        if similar:
            print(f"✅ Found {len(similar)} similar files:")
            for s in similar:
                print(f"   • {s}")
            results.append(True)
        else:
            print(f"⚠️  No similar files found")
            results.append(False)

    return any(results)  # At least one should find matches


def test_vault_root_files():
    """Test accessing files at the vault root level."""
    print("\n" + "=" * 80)
    print("TEST 6: Vault Root Level Files")
    print("=" * 80)

    vault_root = _get_vault_root()
    if not vault_root:
        print("❌ Vault root not configured")
        return False

    # List actual markdown files at vault root
    root_files = []
    try:
        for item in vault_root.iterdir():
            if item.is_file() and item.suffix.lower() == ".md":
                root_files.append(item.name)
    except Exception as e:
        print(f"❌ Error listing vault root: {e}")
        return False

    print(f"Found {len(root_files)} markdown files at vault root")

    # Test accessing a few of them
    test_count = min(3, len(root_files))
    results = []

    for filename in root_files[:test_count]:
        resolved, error = _resolve_vault_path(filename)
        success = resolved is not None

        if success:
            print(f"✅ Can access: {filename}")
        else:
            print(f"❌ Cannot access: {filename}")
            if error:
                print(f"   Error: {error}")

        results.append(success)

    return all(results) if results else True


def run_all_tests():
    """Run all test cases."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "MCP PATH RESOLUTION TEST SUITE" + " " * 28 + "║")
    print("╚" + "=" * 78 + "╝")

    tests = [
        ("Vault Root Configuration", test_vault_root),
        ("Case-Insensitive Matching", test_exact_case_insensitive_match),
        ("Fuzzy Matching", test_fuzzy_matching),
        ("Previously Failing Files", test_specific_failing_files),
        ("Similar Files Search", test_similar_files_function),
        ("Vault Root Access", test_vault_root_files),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed with error:")
            print(f"   {type(e).__name__}: {e}")
            results[test_name] = False

    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
