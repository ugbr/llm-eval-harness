# llm-eval-harness

An eval harness for an LLM document extraction pipeline. It answers a question that is
surprisingly hard to answer about LLM systems: did that change make things better or worse, and
how do you know?

The system under test is a structured data extractor that turns scanned receipts into typed JSON
(company, address, date, total). The harness wraps it with:

- **traces** for every model call, with input, raw output, model, tokens, latency and cost
- **error analysis** over hand-read traces, clustered into a named failure taxonomy with counts
- **code-based evals** for the failures a machine can check
- **an LLM-as-judge** for the ones it can't, validated against hand labels and reported with
  true-positive and true-negative rates rather than a single accuracy number
- **a CI gate** that fails the build when a prompt or model change regresses past threshold

## Status

Early. Nothing here works yet. This README will get real numbers, a taxonomy table, and judge
agreement rates as they exist, and not before.

## Stack

Python, uv, Pydantic, Langfuse for traces, pytest and GitHub Actions for the gate.

## License

MIT
