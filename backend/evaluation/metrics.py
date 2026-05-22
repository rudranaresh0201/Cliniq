import json
import time

from backend.evaluation.ground_truth import MEDICAL_QA_GROUND_TRUTH


def evaluate_triage_accuracy(predicted: str, expected: list[str]) -> bool:
    if not predicted or not expected:
        return False
    return predicted.upper() in [e.upper() for e in expected]


def evaluate_condition_recall(
    predicted_conditions: list[str],
    expected_conditions: list[str],
) -> float:
    if not expected_conditions:
        return 1.0
    matched = 0
    for expected in expected_conditions:
        exp_lower = expected.lower()
        if any(exp_lower in pred.lower() or pred.lower() in exp_lower for pred in predicted_conditions):
            matched += 1
    return matched / len(expected_conditions)


def evaluate_keyword_presence(response_text: str, expected_keywords: list[str]) -> float:
    if not expected_keywords:
        return 1.0
    text_lower = response_text.lower()
    found = sum(1 for kw in expected_keywords if kw.lower() in text_lower)
    return found / len(expected_keywords)


async def run_evaluation_suite(
    analyze_func,
    ground_truth: list = None,
    max_cases: int = 5,
) -> dict:
    if ground_truth is None:
        ground_truth = MEDICAL_QA_GROUND_TRUTH

    per_case_results = []
    triage_scores: list[bool] = []
    condition_scores: list[float] = []
    keyword_scores: list[float] = []
    emergency_total = 0
    emergency_correct = 0

    for case in ground_truth[:max_cases]:
        start = time.time()
        try:
            result = await analyze_func(query=case["query"])
        except Exception as e:
            result = {"error": str(e)}
        latency_ms = (time.time() - start) * 1000

        full_text = json.dumps(result)

        triage_ok = None
        if "expected_triage" in case:
            triage_ok = evaluate_triage_accuracy(
                result.get("triage", ""), case["expected_triage"]
            )
            triage_scores.append(triage_ok)

            # Emergency safety tracking
            if "EMERGENCY" in [e.upper() for e in case["expected_triage"]]:
                emergency_total += 1
                if result.get("triage", "").upper() == "EMERGENCY":
                    emergency_correct += 1

        keyword_score = evaluate_keyword_presence(
            full_text, case.get("expected_keywords", [])
        )
        keyword_scores.append(keyword_score)

        condition_score = None
        if "expected_conditions" in case:
            condition_score = evaluate_condition_recall(
                [c["name"] for c in result.get("conditions", [])],
                case["expected_conditions"],
            )
            condition_scores.append(condition_score)

        per_case_results.append({
            "id": case["id"],
            "query": case["query"],
            "triage_predicted": result.get("triage"),
            "triage_ok": triage_ok,
            "keyword_score": round(keyword_score, 3),
            "condition_score": round(condition_score, 3) if condition_score is not None else None,
            "latency_ms": round(latency_ms, 1),
            "notes": case.get("notes", ""),
        })

    def _mean(lst: list) -> float | None:
        return round(sum(lst) / len(lst), 3) if lst else None

    return {
        "triage_accuracy": _mean([float(s) for s in triage_scores]),
        "condition_recall": _mean(condition_scores),
        "keyword_coverage": _mean(keyword_scores),
        "emergency_safety_rate": (
            round(emergency_correct / emergency_total, 3) if emergency_total > 0 else None
        ),
        "average_latency_ms": _mean([r["latency_ms"] for r in per_case_results]),
        "cases_evaluated": len(per_case_results),
        "per_case_results": per_case_results,
    }
