"""Example 4: Pipeline with a Cyclic Call Pattern

Demonstrates what happens when @step functions form a cycle:
    refine → evaluate → refine (conditional recursive call)

This is a stress test for the DAG inference system. Since graphbook
infers edges from the runtime call graph, mutual recursion between
@step functions will produce cyclic edges. Kahn's algorithm (used by
get_topology_order) silently drops nodes involved in cycles, so this
example makes that behavior visible.
"""

import time

import graphbook.beta as gb
from graphbook.beta.core.state import SessionState

# Reset state so the example is self-contained
SessionState.reset_singleton()

gb.md("A refinement loop where `refine` and `evaluate` call each other until quality converges.")


@gb.step()
def generate_draft() -> dict:
    """Generate an initial draft document with a low quality score."""
    draft = {"text": "initial draft", "version": 0, "quality": 0.2}
    gb.log(f"Generated draft v{draft['version']} (quality={draft['quality']:.2f})")
    time.sleep(0.3)
    return draft


@gb.step()
def evaluate(doc: dict) -> dict:
    """Evaluate document quality and decide whether to refine further."""
    # Simulate quality assessment — improves with each version
    score = min(doc["quality"] + 0.25, 1.0)
    doc["quality"] = score
    gb.log(f"Evaluated v{doc['version']}: quality={score:.2f}")
    gb.log_metric("quality", score, step=doc["version"])
    time.sleep(0.3)

    if score < 0.9:
        gb.log(f"Quality {score:.2f} < 0.9 — sending back for refinement")
        return refine(doc)  # Creates cycle: evaluate → refine
    else:
        gb.log(f"Quality {score:.2f} >= 0.9 — accepted!")
        return doc


@gb.step()
def refine(doc: dict) -> dict:
    """Refine the document to improve its quality score."""
    doc["version"] += 1
    doc["text"] = f"refined draft v{doc['version']}"
    gb.log(f"Refined to v{doc['version']}")
    time.sleep(0.3)
    return evaluate(doc)  # Creates cycle: refine → evaluate


@gb.step()
def run_pipeline() -> dict:
    """Top-level runner: generate a draft and enter the refine/evaluate loop."""
    draft = generate_draft()
    result = refine(draft)
    gb.log(f"Final document: {result['text']} (quality={result['quality']:.2f})")
    return result


def main():
    """Run the cyclic pipeline and inspect the resulting graph."""
    result = run_pipeline()
    print(f"\nFinal: {result['text']} (quality={result['quality']:.2f}, v{result['version']})")


if __name__ == "__main__":
    main()
