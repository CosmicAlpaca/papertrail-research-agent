# Pilot artifacts and interpretation

`litsearch-pilot-tasks.json` froze eight questions before the initial runs: seed 20261125, quality 2 and specificity 1, sampled from the first 100 official LitSearch query rows. This is a narrow inline-ACL development pilot. Source: https://huggingface.co/datasets/princeton-nlp/LitSearch . Gold titles are the supplied corpus titles, including an unusually prefixed readability title; no fuzzy matching is used.

`results/` preserves eight genuine initial MiniLM mixed-score runs, including provider failures and labelled rule-based planner fallbacks. Six runs contain hosted-analysis warnings. They must not be presented as eight successful full-LLM evaluations. `metrics.py` reports title-based known-target Hit@10, target recall@10 and MRR@10 for each stage. It does not pretend unknown papers are non-relevant or compute unsupported precision/nDCG.

`onnx-model-replay.json` reranks those cached candidate pools with the current int8 GTE ModernBERT model. A same-60 control and protected-pool variant distinguish model choice from candidate additions. This is model selection on inspected development data, not held-out validation. The replay does not rerun the LLM assessor or prove that coverage repair helps.

`replay-candidates.json` contains the relevant OpenAlex metadata snapshot (IDs, titles, abstracts, years) needed to reproduce reranking without the private cache database. No full texts, keys, workspace capabilities or account headers are included. `model_replay.py` prefers this snapshot and downloads the official pinned ONNX model. Numerical ties may vary across hardware/runtime versions. Run with `python -m evaluation.model_replay`; no hosted inference calls are made by that replay.

`live-comparison/` contains manually captured first-ten title lists from Asta and Scholar. The exact protocol, natural-language and expert-keyword distinction, known-item ambiguity, and limits are in `docs/live-comparison.md`. These lists do not constitute independent human relevance judgments.

Do not cite any of these results as an official LitSearch benchmark score or evidence of general superiority over Google Scholar. A larger blind, pooled, independently adjudicated comparison remains necessary.
