
import sys
import os
from pathlib import Path

# Add src to path
# Add project root to path (assuming tests/test_query_parsing.py)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Add src/services to path because graph_query_service uses implicit sibling imports
services_dir = os.path.join(project_root, 'src', 'services')
if services_dir not in sys.path:
    sys.path.insert(0, services_dir)

# Import the function to test
# We mock the imports that might fail or cause side effects if possible, 
# but for now let's try direct import assuming env is okay.
from src.services.graph_query_service import parse_query_tags

def test_parse_tags():
    cases = [
        ("find drugs tag:car-t", "find drugs", ["car-t"]),
        ("tag:side-effect headache", "headache", ["side-effect"]),
        ("tag:drug tag:car-t yescarta", "yescarta", ["drug", "car-t"]),
        ('find notes tag:"immune system"', "find notes", ["immune system"]),
        ("no tags here", "no tags here", []),
        ("", "", []),
        ("tag:foo", "", ["foo"]),
        ("search tag:A tag:B query", "search query", ["a", "b"]),
    ]
    
    failed = 0
    for inp, expected_text, expected_tags in cases:
        out_text, out_filters = parse_query_tags(inp)
        out_tags = out_filters.get('tags', [])
        
        # Check text match
        text_match = out_text == expected_text
        # Check tags match (order might matter or not, distinctness)
        tags_match = sorted(out_tags) == sorted(expected_tags)
        
        if not text_match or not tags_match:
            print(f"FAIL: input='{inp}'")
            print(f"  Expected text='{expected_text}', got='{out_text}'")
            print(f"  Expected tags={expected_tags}, got={out_tags}")
            failed += 1
        else:
            print(f"PASS: '{inp}' -> '{out_text}' + {out_tags}")
            
    if failed == 0:
        print("\nALL TESTS PASSED")
    else:
        print(f"\n{failed} TESTS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    test_parse_tags()
