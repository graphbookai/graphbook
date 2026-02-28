"""Example 1: Basic Pipeline with DAG Inference and Logging

Demonstrates:
- @gb.step() decorator with automatic DAG edge inference
- Automatic source node detection (in-degree 0)
- gb.log() for text logging
- gb.track() for progress tracking
- gb.md() for workflow-level documentation
- gb.inspect() for object metadata

Key concept: DAG edges are inferred when one @step function calls another
@step function. The caller becomes the parent, and the callee becomes the child.
Source nodes are those with in-degree 0 (nothing calls them).
"""

import graphbook.beta as gb
from graphbook.beta.core.state import get_state, SessionState
from graphbook.beta.core.dag import get_dag_summary, get_sources, get_topology_order

# Reset state so the example is self-contained
SessionState.reset_singleton()

# Describe the workflow for AI agents
gb.md("A simple text processing pipeline that loads documents, cleans them, and extracts keywords.")


@gb.step()
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
    gb.log(f"Cleaned {len(cleaned)} documents")
    gb.inspect(cleaned, "cleaned_docs")
    return cleaned


@gb.step()
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
    return results


@gb.step()
def summarize(results: list[dict]) -> str:
    """Generate a summary report of keyword extraction results."""
    total_keywords = sum(r["keyword_count"] for r in results)
    summary = f"Processed {len(results)} documents, found {total_keywords} total keywords."
    gb.log(summary)
    gb.inspect(results, "final_results")
    return summary


@gb.step()
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

    # Execute — run_pipeline is the source node
    result = run_pipeline(file_paths)

    # Print pipeline results
    print("\n" + "=" * 60)
    print("PIPELINE RESULTS")
    print("=" * 60)
    print(f"\nSummary: {result}")

    # Show inferred DAG
    print(f"\nDAG topology: {get_dag_summary()}")
    print(f"Source nodes: {get_sources()}")
    print(f"Topological order: {get_topology_order()}")

    # Show node details
    state = get_state()
    print(f"\nRegistered nodes: {len(state.nodes)}")
    for node_id, node in state.nodes.items():
        source_tag = " [SOURCE]" if node.is_source else ""
        doc_preview = f"'{node.docstring[:60]}...'" if node.docstring and len(node.docstring) > 60 else f"'{node.docstring}'"
        print(f"  {node.func_name}{source_tag}: {node.exec_count}x, "
              f"{len(node.logs)} logs, doc={doc_preview}")

    print(f"\nEdges ({len(state.edges)}):")
    for edge in state.edges:
        src = edge.source.split(".")[-1]
        tgt = edge.target.split(".")[-1]
        print(f"  {src} → {tgt}")


if __name__ == "__main__":
    main()
