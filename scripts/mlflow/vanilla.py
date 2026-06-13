"""MLflow GenAI Evaluation CLI.

Demonstrates the MLflow 3.x GenAI Evaluation workflow step by step:

  1. ``trace``         – Run a small QA function and record MLflow traces.
  2. ``dataset``       – Define and display an inline evaluation dataset.
  3. ``evaluate``      – Heuristic scoring (no Azure / LLM required).
  4. ``judge``         – LLM-judge scoring (Correctness / RelevanceToQuery).
  5. ``custom-scorer`` – Define and apply a custom @scorer.
  6. ``compare``       – Search traces / evaluation runs and print a comparison table.

Run any subcommand with ``--help`` for details.
"""

import json
import logging
import sys
from functools import lru_cache
from typing import Annotated, Any, cast

import typer
from dotenv import load_dotenv

from concierge.loggers import get_logger
from concierge.settings import get_observability_settings

# ---------------------------------------------------------------------------
# Inline evaluation dataset (5 simple QA pairs, no external download)
# ---------------------------------------------------------------------------

_DATASET: list[dict[str, Any]] = [
    {
        "inputs": {"question": "What is the capital of France?"},
        "expectations": {"expected_response": "Paris"},
    },
    {
        "inputs": {"question": "What is 2 + 2?"},
        "expectations": {"expected_response": "4"},
    },
    {
        "inputs": {"question": "Who wrote Romeo and Juliet?"},
        "expectations": {"expected_response": "William Shakespeare"},
    },
    {
        "inputs": {"question": "What is the boiling point of water in Celsius?"},
        "expectations": {"expected_response": "100"},
    },
    {
        "inputs": {"question": "What planet is closest to the Sun?"},
        "expectations": {"expected_response": "Mercury"},
    },
]

# ---------------------------------------------------------------------------
# Typer application
# ---------------------------------------------------------------------------

app = typer.Typer(
    add_completion=False,
    help="MLflow GenAI Evaluation CLI",
)

logger = get_logger(__name__)


@app.callback()
def _global_options(
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose (DEBUG) logging",
        ),
    ] = False,
) -> None:
    """MLflow GenAI Evaluation CLI – global options applied to every subcommand."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
        logger.setLevel(logging.DEBUG)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _setup_mlflow() -> str:
    """Configure MLflow tracking URI and experiment, return the experiment name."""
    import mlflow

    settings = get_observability_settings()
    tracking_uri = settings.mlflow_tracking_uri
    experiment_name = settings.mlflow_experiment_name
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    logger.info("MLflow configured (tracking_uri=%s, experiment=%s)", tracking_uri, experiment_name)
    return experiment_name


def _simple_qa(question: str) -> str:
    """A minimal QA function used as the target application.

    Returns hard-coded answers for the bundled dataset so that the
    evaluation commands run end-to-end without an LLM back-end.
    """
    answers = {
        "what is the capital of france?": "Paris",
        "what is 2 + 2?": "4",
        "who wrote romeo and juliet?": "William Shakespeare",
        "what is the boiling point of water in celsius?": "100 degrees Celsius",
        "what planet is closest to the sun?": "Mercury",
    }
    return answers.get(question.lower().strip(), "I don't know.")


# ---------------------------------------------------------------------------
# Subcommand: trace
# ---------------------------------------------------------------------------


@app.command(help="Run the QA function and record traces in MLflow.")
def trace(
    question: Annotated[
        str,
        typer.Option(
            "--question",
            "-q",
            help="Question to answer (default: first item in the built-in dataset)",
        ),
    ] = _DATASET[0]["inputs"]["question"],
    experiment: Annotated[
        str | None,
        typer.Option(
            "--experiment",
            "-e",
            help="MLflow experiment name (default: from MLFLOW_EXPERIMENT_NAME / observability settings)",
        ),
    ] = None,
) -> None:
    """Run the QA function once and record the call as an MLflow trace.

    Open http://127.0.0.1:5000 after running to see the trace in the UI.
    """
    import mlflow

    _setup_mlflow()
    if experiment:
        mlflow.set_experiment(experiment)

    @mlflow.trace
    def traced_qa(q: str) -> str:
        return _simple_qa(q)

    answer = traced_qa(question)
    print(f"Q: {question}")
    print(f"A: {answer}")
    logger.info("Trace recorded. Open http://127.0.0.1:5000 to inspect it.")


# ---------------------------------------------------------------------------
# Subcommand: dataset
# ---------------------------------------------------------------------------


@app.command(help="Print the inline evaluation dataset as JSON.")
def dataset(
    output: Annotated[
        str | None,
        typer.Option(
            "--output",
            "-o",
            help="Write dataset to this file path instead of stdout",
        ),
    ] = None,
) -> None:
    """Display the built-in evaluation dataset.

    Each row has ``inputs`` (a dict with a ``question`` key) and
    ``expected_response`` (the gold-standard answer).
    """
    text = json.dumps(_DATASET, indent=2, ensure_ascii=False)
    if output:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"Dataset written to {output} ({len(_DATASET)} rows).")
    else:
        print(text)


# ---------------------------------------------------------------------------
# Subcommand: evaluate  (heuristic scorers – no LLM required)
# ---------------------------------------------------------------------------


@app.command(help="Run heuristic evaluation (exact-match + length) – no Azure required.")
def evaluate(
    experiment: Annotated[
        str | None,
        typer.Option(
            "--experiment",
            "-e",
            help="MLflow experiment name (default: observability settings)",
        ),
    ] = None,
    run_name: Annotated[
        str,
        typer.Option(
            "--run-name",
            help="MLflow run name for this evaluation",
        ),
    ] = "heuristic-eval",
) -> None:
    """Evaluate the QA function using heuristic scorers.

    Scorers applied:

    * ``exact_match``  – 1.0 when output equals expected_response (case-insensitive).
    * ``contains``     – 1.0 when output contains expected_response (case-insensitive).
    * ``non_empty``    – 1.0 when output is non-empty.

    All three scorers are pure Python – no LLM or Azure credentials needed.
    """
    import mlflow
    from mlflow.genai.scorers import scorer

    _setup_mlflow()
    if experiment:
        mlflow.set_experiment(experiment)

    # ------------------------------------------------------------------
    # Define heuristic scorers using the @scorer decorator
    # ------------------------------------------------------------------

    @scorer
    def exact_match(outputs: str, expectations: dict[str, Any]) -> float:
        """Return 1.0 when the output exactly matches the expected response."""
        expected_response = expectations["expected_response"]
        return 1.0 if outputs.strip().lower() == expected_response.strip().lower() else 0.0

    @scorer
    def contains(outputs: str, expectations: dict[str, Any]) -> float:
        """Return 1.0 when the output contains the expected response."""
        expected_response = expectations["expected_response"]
        return 1.0 if expected_response.strip().lower() in outputs.strip().lower() else 0.0

    @scorer
    def non_empty(outputs: str) -> float:
        """Return 1.0 when the output is non-empty."""
        return 1.0 if outputs.strip() else 0.0

    # ------------------------------------------------------------------
    # Run evaluation
    # ------------------------------------------------------------------

    # MLflow unpacks each row's ``inputs`` dict as keyword arguments, so the
    # parameter name must match the dataset key (``question``).
    def _predict(question: str) -> str:
        return _simple_qa(question)

    with mlflow.start_run(run_name=run_name):
        results = mlflow.genai.evaluate(
            data=_DATASET,
            predict_fn=_predict,
            scorers=[exact_match, contains, non_empty],
        )

    print(results.metrics)
    print("\nPer-row results:")
    print(results.tables["eval_results"].to_string(index=False))
    logger.info("Evaluation complete. Open http://127.0.0.1:5000 to view results.")


# ---------------------------------------------------------------------------
# Subcommand: judge  (LLM-judge scorers – requires Azure / OpenAI)
# ---------------------------------------------------------------------------


@app.command(help="Run LLM-judge evaluation (Correctness, RelevanceToQuery) – requires Azure.")
def judge(
    experiment: Annotated[
        str | None,
        typer.Option(
            "--experiment",
            "-e",
            help="MLflow experiment name (default: observability settings)",
        ),
    ] = None,
    run_name: Annotated[
        str,
        typer.Option(
            "--run-name",
            help="MLflow run name for this evaluation",
        ),
    ] = "llm-judge-eval",
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model string for the LLM judge (e.g. azure_ai:gpt-5)",
        ),
    ] = "azure_ai:gpt-5",
) -> None:
    """Evaluate the QA function with LLM-judge scorers.

    Judges applied:

    * ``correctness``         – Is the answer factually correct (vs. expected_response)?
    * ``relevance_to_query``  – Is the answer relevant to the question?

    Both judges are custom ``@scorer`` functions backed by the same
    ``langchain``/Azure AI Foundry model the rest of the project uses
    (authenticated via ``DefaultAzureCredential``). This avoids the built-in
    litellm judges, which require API-key auth that this project does not use.

    This command requires Azure credentials and a deployed model. When
    credentials are missing the command exits with a clear (skip) message.
    """
    import mlflow
    from langchain.chat_models import init_chat_model
    from mlflow.entities import Feedback
    from mlflow.genai.scorers import scorer

    _setup_mlflow()
    if experiment:
        mlflow.set_experiment(experiment)

    # Validate that a judge model is accessible before running evaluation.
    try:
        judge_model = init_chat_model(model)
        # Minimal smoke-test: a tiny invocation to catch auth failures early.
        judge_model.invoke("ping")
    except Exception as exc:
        logger.warning(
            "LLM judge model '%s' is not reachable: %s. "
            "Make sure Azure credentials are configured (az login / .env) "
            "and the model is deployed. Skipping judge evaluation.",
            model,
            exc,
        )
        print(
            f"[skip] LLM judge skipped: {exc}\nConfigure Azure credentials and retry.",
            file=sys.stderr,
        )
        raise typer.Exit(code=0) from exc

    def _judge(prompt: str, name: str) -> Feedback:
        """Ask the judge model for a PASS/FAIL verdict and capture its rationale."""
        response = judge_model.invoke(prompt)
        text = str(getattr(response, "content", response)).strip()
        verdict_line = text.splitlines()[0].lower() if text else ""
        passed = "pass" in verdict_line and "fail" not in verdict_line
        return Feedback(name=name, value=passed, rationale=text)

    @scorer
    def correctness(inputs: dict[str, Any], outputs: str, expectations: dict[str, Any]) -> Feedback:
        """LLM judge: is the answer factually correct vs. the expected response?"""
        prompt = (
            "You are a strict grader. Decide whether the ANSWER is factually correct "
            "for the QUESTION, using EXPECTED as the ground-truth answer.\n"
            "Respond with 'PASS' or 'FAIL' on the first line, then a one-sentence reason.\n\n"
            f"QUESTION: {inputs['question']}\n"
            f"EXPECTED: {expectations['expected_response']}\n"
            f"ANSWER: {outputs}\n"
        )
        return _judge(prompt, "correctness")

    @scorer
    def relevance_to_query(inputs: dict[str, Any], outputs: str) -> Feedback:
        """LLM judge: is the answer relevant to the question (ignoring accuracy)?"""
        prompt = (
            "You are a strict grader. Decide whether the ANSWER is relevant to the "
            "QUESTION, regardless of factual accuracy.\n"
            "Respond with 'PASS' or 'FAIL' on the first line, then a one-sentence reason.\n\n"
            f"QUESTION: {inputs['question']}\n"
            f"ANSWER: {outputs}\n"
        )
        return _judge(prompt, "relevance_to_query")

    with mlflow.start_run(run_name=run_name):
        results = mlflow.genai.evaluate(
            data=_DATASET,
            predict_fn=_simple_qa,
            scorers=[correctness, relevance_to_query],
        )

    print(results.metrics)
    print("\nPer-row results:")
    print(results.tables["eval_results"].to_string(index=False))
    logger.info("LLM-judge evaluation complete. Open http://127.0.0.1:5000 to view results.")


# ---------------------------------------------------------------------------
# Subcommand: custom-scorer
# ---------------------------------------------------------------------------


@app.command(name="custom-scorer", help="Run evaluation with a custom @scorer.")
def custom_scorer(
    experiment: Annotated[
        str | None,
        typer.Option(
            "--experiment",
            "-e",
            help="MLflow experiment name (default: observability settings)",
        ),
    ] = None,
    run_name: Annotated[
        str,
        typer.Option(
            "--run-name",
            help="MLflow run name for this evaluation",
        ),
    ] = "custom-scorer-eval",
) -> None:
    """Demonstrate a custom @scorer that counts shared tokens.

    The ``token_overlap`` scorer tokenises both output and expected_response
    on whitespace, then returns the Jaccard similarity of the two token sets.
    It runs entirely locally – no LLM required.
    """
    import mlflow
    from mlflow.genai.scorers import scorer

    _setup_mlflow()
    if experiment:
        mlflow.set_experiment(experiment)

    # ------------------------------------------------------------------
    # Custom scorer: token overlap (Jaccard similarity)
    # ------------------------------------------------------------------

    @scorer
    def token_overlap(outputs: str, expectations: dict[str, Any]) -> float:
        """Jaccard similarity between output and expected_response token sets.

        Tokenises on whitespace (lowercase), then returns
        |A ∩ B| / |A ∪ B|.  Returns 0.0 when both sets are empty.
        """
        expected_response = expectations["expected_response"]
        a = set(outputs.lower().split())
        b = set(expected_response.lower().split())
        if not a and not b:
            return 0.0
        return len(a & b) / len(a | b)

    # MLflow unpacks each row's ``inputs`` dict as keyword arguments, so the
    # parameter name must match the dataset key (``question``).
    def _predict(question: str) -> str:
        return _simple_qa(question)

    with mlflow.start_run(run_name=run_name):
        results = mlflow.genai.evaluate(
            data=_DATASET,
            predict_fn=_predict,
            scorers=[token_overlap],
        )

    print(results.metrics)
    print("\nPer-row results:")
    print(results.tables["eval_results"].to_string(index=False))
    logger.info("Custom-scorer evaluation complete. Open http://127.0.0.1:5000 to view results.")


# ---------------------------------------------------------------------------
# Subcommand: compare
# ---------------------------------------------------------------------------


@app.command(help="Fetch recent evaluation runs and print a comparison table.")
def compare(
    experiment: Annotated[
        str | None,
        typer.Option(
            "--experiment",
            "-e",
            help="MLflow experiment name to query (default: observability settings)",
        ),
    ] = None,
    max_results: Annotated[
        int,
        typer.Option(
            "--max-results",
            "-n",
            help="Maximum number of runs to include",
        ),
    ] = 10,
) -> None:
    """Search MLflow runs and display a comparison table.

    Fetches the latest evaluation runs from the configured experiment and
    prints a side-by-side summary of their metrics. Use this to compare
    heuristic vs. LLM-judge vs. custom-scorer runs.

    The MLflow UI (http://127.0.0.1:5000) provides an interactive version
    of this comparison with charts and filtering.
    """
    import mlflow
    import pandas as pd

    _setup_mlflow()
    target_experiment = experiment or get_observability_settings().mlflow_experiment_name

    runs = cast(
        pd.DataFrame,
        mlflow.search_runs(
            experiment_names=[target_experiment],
            max_results=max_results,
            output_format="pandas",
        ),
    )

    if runs.empty:
        print(f"No runs found in experiment '{target_experiment}'.")
        print("Run 'evaluate', 'judge', or 'custom-scorer' first to create some results.")
        return

    # Select a readable subset of columns
    keep_cols = [
        c for c in runs.columns if c.startswith("metrics.") or c in {"run_id", "tags.mlflow.runName", "start_time"}
    ]
    display = runs[keep_cols].rename(columns={"tags.mlflow.runName": "run_name"})
    display = display.sort_values("start_time", ascending=False) if "start_time" in display.columns else display

    print(f"\nExperiment: {target_experiment}  ({len(display)} run(s))\n")
    print(display.to_string(index=False))
    print(f"\nFull comparison: http://127.0.0.1:5000/#/experiments/{target_experiment}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not load_dotenv(override=True, verbose=True):
        logging.warning("No .env file found; using defaults")
    app()
