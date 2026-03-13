"""Example 5: Interactive Pipeline with gb.ask()

Demonstrates:
- gb.ask() for pausing execution and prompting the user
- gb.ask() with constrained options
- gb.ask() with free-form text input
- Branching pipeline logic based on user responses
"""

import time
import graphbook.beta as gb


gb.md("An interactive pipeline that asks the user for input at key decision points.")


@gb.fn()
def collect_preferences() -> dict:
    """Gather user preferences to configure the pipeline."""
    name = gb.ask("What is your name?")
    gb.log(f"User: {name}")

    mode = gb.ask("Which processing mode?", options=["fast", "balanced", "thorough"])
    gb.log(f"Mode: {mode}")

    return {"name": name, "mode": mode}


@gb.fn()
def generate_data(mode: str) -> list[float]:
    """Generate data with size based on the chosen mode."""
    sizes = {"fast": 10, "balanced": 50, "thorough": 200}
    n = sizes.get(mode, 50)
    data = [i * 0.1 for i in range(n)]
    gb.log(f"Generated {n} data points in '{mode}' mode")
    time.sleep(0.3)
    return data


@gb.fn()
def process(data: list[float]) -> dict:
    """Process the data and compute summary statistics."""
    result = {
        "count": len(data),
        "sum": sum(data),
        "mean": sum(data) / len(data) if data else 0,
    }
    gb.log(f"Processed {result['count']} points: mean={result['mean']:.2f}")
    time.sleep(0.3)
    return result


@gb.fn()
def review_results(prefs: dict, result: dict) -> str:
    """Present results and ask the user whether to accept or retry."""
    gb.log(f"Results for {prefs['name']}: count={result['count']}, mean={result['mean']:.2f}")

    decision = gb.ask(
        f"Mean is {result['mean']:.2f}. Accept these results?",
        options=["yes", "no"],
    )
    gb.log(f"Decision: {decision}")
    return decision


@gb.fn()
def run_pipeline() -> dict:
    """Interactive pipeline: collect preferences, generate, process, review."""
    prefs = collect_preferences()
    data = generate_data(prefs["mode"])
    result = process(data)

    decision = review_results(prefs, result)
    if decision == "no":
        gb.log("User rejected results — re-running with thorough mode")
        data = generate_data("thorough")
        result = process(data)

    gb.log(f"Final result: {result}")
    return result


def main():
    result = run_pipeline()
    print(f"\nDone: {result}")


if __name__ == "__main__":
    main()
