# Live comparison notes - 25 November 2026

This is a two-task qualitative pilot, not a leaderboard. Searches were performed in the signed-in browser. Models, indexes, and ranking can change. Raw account-bearing snapshots remain private; sanitized first-ten title lists are in `evaluation/live-comparison/`.

## Protocol

1. Submit the same natural-language question to Asta Find Papers in its default mode and Google Scholar's standard search interface.
2. For the date-constrained task, also use Scholar's advanced search with an expert keyword query and explicit year filters. This is a separate stronger baseline; do not score Scholar only on a verbatim natural-language prompt.
3. Preserve the first ten result titles in displayed order. Do not treat Asta's self-reported relevance scores or PaperTrail's model labels as human gold.
4. Inspect candidate abstracts before concluding a criterion is met. Missing abstract evidence remains unknown. The known-item task has ambiguous valid alternatives, so the named-target rank is diagnostic only.

## Task A: explaining graph neural networks

Question: papers from 2018 through 2024 introducing explanation methods for GNN predictions, evaluated on real graph datasets, not only synthetic graphs.

Scholar natural-language search initially returned a 2025 result; dates in prose do not substitute for date controls. With the expert query `graph neural network explanation real-world datasets` and the 2018-2024 filters, Scholar returned GNNExplainer, PGExplainer, GraphFramEx, GraphSVX, and related work within its first ten. This is a useful, competitive baseline.

Asta took approximately 75 seconds according to its interface and exposed criteria, relevance explanations, citation counts, and a source-evidence affordance. Its displayed first ten mixed new methods with surveys and evaluation work. The trustworthy-GNN survey ranked second was labelled perfectly relevant even though the question asked for method contributions. This is a candidate criterion-relaxation case requiring paper-level review, not proof that all surveys are irrelevant.

PaperTrail's initial full hosted run found source quotes for both requirements in GNNExplainer, PGM-Explainer, and Zorro and placed them first. The result's title/abstract-only assessment basis is explicit. A previous development run had overclaimed real datasets from nonspecific dataset descriptions; that error led to stricter evidence prompts. Quote matching alone did not catch this logical error.

## Task B: a partly remembered method

Question: the paper training continuous prompts at every transformer layer instead of fine-tuning all language-model weights.

Scholar placed Prefix-Tuning first. Asta's first displayed result was Visual Prompt Tuning; Prefix-Tuning was outside the first ten captured titles. PaperTrail's original MiniLM deployment placed Prefix-Tuning seventh while hosted assessment was partially unavailable. P-Tuning v2 and related deep-prompt methods may also meet the broad description, so this is not an exhaustive relevance judgment.

This case favors Scholar on the specified known target. It motivated retaining semantic-search candidates and testing a stronger local reranker instead of increasing confidence in an unvalidated ranking.

## What the observations support

PaperTrail supplies a working alternative with editable criteria, validated source attribution, explicit uncertainty, actual citation edges, bounded repair, exports, and grounded follow-up questions. Asta already has criteria and explanations; these ideas are not claimed as new in isolation. The proposed improvement is an inspectable, exportable evidence-coverage loop that changes retrieval and ordering.

Two observations cannot establish general superiority, novelty, time savings, or reliable precision. Google Scholar Labs, Asta deep search, other domains, multilingual questions, and independent human adjudication were not evaluated here. The small LitSearch transfer pilot separately measures known-target retrieval and exposes implementation regressions.
