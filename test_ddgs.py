from duckduckgo_search import DDGS
import json

def test_search():
    print("Testing DuckDuckGo Search...")
    try:
        with DDGS() as ddgs:
            queries = [
                "RCHOP lymphoma treatment",
                "Diffuse Large B-Cell Lymphoma treatment",
                "lymphoma chemotherapy success rates"
            ]
            for q in queries:
                print(f"\nQuery: {q}")
                results = list(ddgs.text(q, region='us-en', max_results=2))
                for r in results:
                    print(f"- {r['title']}: {r['href']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_search()
