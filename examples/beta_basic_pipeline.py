"""Example 1: Basic Pipeline with DAG Inference and Logging

Demonstrates:
- @gb.fn() decorator with automatic DAG edge inference
- Automatic source node detection (in-degree 0)
- gb.log() for text logging
- gb.track() for progress tracking
- gb.md() for workflow-level documentation
Key concept: DAG edges are inferred when one @fn function calls another
@fn function. The caller becomes the parent, and the callee becomes the child.
Source nodes are those with in-degree 0 (nothing calls them).
"""

import time
import graphbook.beta as gb


# Describe the workflow for AI agents
gb.md("A simple text processing pipeline that loads documents, cleans them, and extracts keywords.")


@gb.fn()
def clean_text(documents: list[dict]) -> list[dict]:
    """Clean and normalize document text by lowering case and stripping whitespace."""
    cleaned = []
    for doc in gb.track(documents, name="cleaning"):
        cleaned_doc = {
            **doc,
            "content": doc["content"].lower().strip(),
            "cleaned": True,
        }
        cleaned.append(cleaned_doc)
        time.sleep(0.3)
    gb.log(f"Cleaned {len(cleaned)} documents")
    return cleaned


@gb.fn()
def extract_keywords(documents: list[dict]) -> list[dict]:
    """Extract keywords from cleaned documents using simple word frequency."""
    keywords_list = ["python", "ai", "machine", "learning", "data", "science"]
    results = []
    for doc in gb.track(documents, name="extracting"):
        words = doc["content"].split()
        found = [w for w in words if w in keywords_list]
        result = {
            "path": doc["path"],
            "keywords": found,
            "keyword_count": len(found),
        }
        results.append(result)
        gb.log(f"Found {len(found)} keywords in {doc['path']}")
        time.sleep(0.3)
    return results


@gb.fn()
def summarize(results: list[dict]) -> str:
    """Generate a summary report of keyword extraction results."""
    total_keywords = sum(r["keyword_count"] for r in results)
    summary = f"Processed {len(results)} documents, found {total_keywords} total keywords."
    gb.log(summary)
    return summary


@gb.fn()
def run_pipeline(file_paths: list[str]) -> str:
    """Run the full text processing pipeline end-to-end.

    This is the source node — it calls clean_text → extract_keywords → summarize,
    and graphbook infers the DAG edges automatically from the call chain.
    """
    # Simulate loading documents
    documents = []
    for path in gb.track(file_paths, name="loading"):
        doc = {
            "path": path,
            "content": f"This is the content of {path}. It has Python, AI, and machine learning keywords.",
            "size": len(path) * 100,
        }
        documents.append(doc)
        gb.log(f"Loaded document: {path} ({doc['size']} bytes)")
        time.sleep(0.3)

    # Pipeline: each call creates a DAG edge from run_pipeline → callee
    cleaned = clean_text(documents)
    keywords = extract_keywords(cleaned)
    result = summarize(keywords)

    return result


def main():
    """Run the text processing pipeline."""
    file_paths = [
        "docs/intro.txt",
        "docs/chapter1.txt",
        "docs/chapter2.txt",
        "docs/conclusion.txt",
        "docs/appendix.txt",
    ]

    result = run_pipeline(file_paths)
    print(f"\nSummary: {result}")


if __name__ == "__main__":
    main()
