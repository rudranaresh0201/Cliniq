"""
ClinIQ 2.0 clinical planner.

Receives a user query and patient/case context, asks Groq (llama-3.3-70b)
to produce an ordered tool plan, then executes each tool through the
registry — injecting each tool's output into dependent tools automatically.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field

from agents.tool_registry import REGISTRY
from backend.llm.router import llm_chat
from db.models import Case, Patient

logger = logging.getLogger("cliniq.planner")

# ---------------------------------------------------------------------------
# System prompt
# Stored as a plain string; placeholders filled with .replace() so that the
# literal JSON braces inside the prompt body are never misread as format args.
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are the ClinIQ clinical planner. Your job is to analyze \
a patient query and decide which tools to invoke to help the doctor or patient.

Available tools: PLACEHOLDER_TOOLS_JSON

Patient context: PLACEHOLDER_PATIENT_CONTEXT
Case context: PLACEHOLDER_CASE_CONTEXT

Given the user input, return ONLY a valid JSON object following \
this exact schema — no markdown, no explanation, just JSON:
{
  "reasoning": "...",
  "tool_calls": [
    {
      "tool_name": "exact tool name from registry",
      "inputs": {exact inputs matching tool input_schema},
      "depends_on": null or "tool_name_whose_output_feeds_here",
      "reason": "one sentence why"
    }
  ],
  "expected_outcome": "..."
}

Rules you must follow:
- Only use tool names that exist in the available tools list
- Always start with symptom_extractor if the input is free text symptoms
- Always run india_epidemiology_reranker after clinical_reasoner
- Always run monitoring_plan_writer at the end if risk_tier is moderate, high, or critical
- Maximum 6 tools per plan
- If a tool depends_on another, use that tool's output in its inputs field where logical"""


def _render_prompt(tools_json: str, patient_context: str, case_context: str) -> str:
    return (
        _SYSTEM_PROMPT
        .replace("PLACEHOLDER_TOOLS_JSON", tools_json)
        .replace("PLACEHOLDER_PATIENT_CONTEXT", patient_context)
        .replace("PLACEHOLDER_CASE_CONTEXT", case_context)
    )


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ToolCall:
    """A single tool invocation inside a plan."""

    tool_name: str
    inputs: dict
    depends_on: str | None
    reason: str


@dataclass
class ToolPlan:
    """The LLM-generated execution plan."""

    reasoning: str
    tool_calls: list[ToolCall]
    expected_outcome: str


@dataclass
class ToolExecutionResult:
    """Result of executing one tool."""

    tool_name: str
    success: bool
    output: dict
    error: str | None
    execution_time_ms: int


@dataclass
class PlanExecutionResult:
    """Result of executing an entire ToolPlan."""

    plan: ToolPlan
    results: list[ToolExecutionResult]
    all_succeeded: bool
    combined_output: dict
    total_execution_time_ms: int


# ---------------------------------------------------------------------------
# Fallback plan
# ---------------------------------------------------------------------------


def _make_fallback_plan(user_input: str) -> ToolPlan:
    """Safe three-step plan used when the LLM fails to return valid JSON."""
    return ToolPlan(
        reasoning="Fallback plan: LLM response was unavailable or unparseable.",
        tool_calls=[
            ToolCall(
                tool_name="symptom_extractor",
                inputs={"text": user_input, "language": "en"},
                depends_on=None,
                reason="Extract symptoms from free-text input.",
            ),
            ToolCall(
                tool_name="clinical_reasoner",
                inputs={"symptoms": []},
                depends_on="symptom_extractor",
                reason="Generate differentials from extracted symptoms.",
            ),
            ToolCall(
                tool_name="india_epidemiology_reranker",
                inputs={"differentials": []},
                depends_on="clinical_reasoner",
                reason="Apply India-specific prevalence to differentials.",
            ),
        ],
        expected_outcome="Basic symptom extraction and differential generation.",
    )


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


class ClinIQPlanner:
    """Orchestrates LLM-driven tool planning and sequential execution."""

    def __init__(self) -> None:
        self._tool_list = REGISTRY.list_tools()
        logger.info("ClinIQPlanner initialised with %d tools", len(self._tool_list))

    # ------------------------------------------------------------------
    # plan()
    # ------------------------------------------------------------------

    async def plan(
        self,
        user_input: str,
        patient: Patient,
        case: Case,
        additional_context: dict | None = None,
    ) -> ToolPlan:
        """Ask Groq to produce an ordered tool plan for this query."""
        additional_context = additional_context or {}
        system_prompt = _render_prompt(
            tools_json=json.dumps(self._tool_list, indent=2),
            patient_context=self._patient_summary(patient),
            case_context=self._case_summary(case, additional_context),
        )

        try:
            raw = await self._call_groq(system_prompt, user_input)
            plan = self._parse_plan(raw)
            logger.info(
                "Plan generated | tools=%s | reasoning=%s",
                [tc.tool_name for tc in plan.tool_calls],
                plan.reasoning[:120],
            )
            return plan
        except Exception:
            logger.exception("plan() failed — returning fallback plan")
            return _make_fallback_plan(user_input)

    async def _call_groq(self, system_prompt: str, user_input: str) -> str:
        return await llm_chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            temperature=0.1,
            max_tokens=1024,
        )

    def _parse_plan(self, raw: str) -> ToolPlan:
        """Parse the LLM JSON response into a ToolPlan, raising on bad JSON."""
        raw = raw.strip()
        # Strip accidental markdown code fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        tool_calls = [
            ToolCall(
                tool_name=tc["tool_name"],
                inputs=tc.get("inputs", {}),
                depends_on=tc.get("depends_on"),
                reason=tc.get("reason", ""),
            )
            for tc in data.get("tool_calls", [])
        ]
        return ToolPlan(
            reasoning=data.get("reasoning", ""),
            tool_calls=tool_calls,
            expected_outcome=data.get("expected_outcome", ""),
        )

    # ------------------------------------------------------------------
    # execute_plan()
    # ------------------------------------------------------------------

    async def execute_plan(
        self,
        plan: ToolPlan,
        patient: Patient,
        case: Case,
    ) -> PlanExecutionResult:
        """Execute every tool in the plan in order, injecting dependency outputs."""
        results: list[ToolExecutionResult] = []
        # keyed by tool_name for fast dependency lookup
        outputs_by_tool: dict[str, dict] = {}
        plan_start = time.perf_counter()

        for tool_call in plan.tool_calls:
            inputs = self._resolve_inputs(tool_call, outputs_by_tool, patient, case)
            result = await self._execute_one(tool_call.tool_name, inputs)
            results.append(result)
            if result.success:
                outputs_by_tool[tool_call.tool_name] = result.output

        total_ms = int((time.perf_counter() - plan_start) * 1000)
        all_succeeded = all(r.success for r in results)
        combined = {r.tool_name: r.output for r in results if r.success}

        logger.info(
            "Plan execution complete | success=%s | tools=%d | total_ms=%d",
            all_succeeded,
            len(results),
            total_ms,
        )
        return PlanExecutionResult(
            plan=plan,
            results=results,
            all_succeeded=all_succeeded,
            combined_output=combined,
            total_execution_time_ms=total_ms,
        )

    async def _execute_one(self, tool_name: str, inputs: dict) -> ToolExecutionResult:
        """Execute a single tool and return a timed result."""
        start = time.perf_counter()
        raw = await REGISTRY.execute(tool_name, inputs)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        if raw["success"]:
            logger.info("Tool '%s' OK | ms=%d", tool_name, elapsed_ms)
        else:
            logger.warning(
                "Tool '%s' FAILED | ms=%d | error=%s",
                tool_name,
                elapsed_ms,
                raw.get("error"),
            )

        return ToolExecutionResult(
            tool_name=tool_name,
            success=raw["success"],
            output=raw.get("output", {}),
            error=raw.get("error"),
            execution_time_ms=elapsed_ms,
        )

    def _resolve_inputs(
        self,
        tool_call: ToolCall,
        outputs_by_tool: dict[str, dict],
        patient: Patient,
        case: Case,
    ) -> dict:
        """
        Merge dependency output into tool inputs.

        The LLM-provided inputs take precedence; the dependency output
        fills any keys the LLM left empty (or adds supplemental context).
        """
        inputs = dict(tool_call.inputs)
        if tool_call.depends_on and tool_call.depends_on in outputs_by_tool:
            dep_output = outputs_by_tool[tool_call.depends_on]
            # Dependency output is authoritative: the planner's inputs are
            # planning-time guesses; the actual tool output must always win.
            for key, value in dep_output.items():
                inputs[key] = value
            # Bridge key mismatch: india_epidemiology_reranker outputs
            # "reranked_differentials" but downstream tools read "differentials".
            if "reranked_differentials" in dep_output:
                inputs["differentials"] = dep_output["reranked_differentials"]
        return inputs

    # ------------------------------------------------------------------
    # Context serialisers
    # ------------------------------------------------------------------

    @staticmethod
    def _patient_summary(patient: Patient) -> str:
        return json.dumps(
            {
                "name": patient.name,
                "age": patient.age,
                "sex": patient.sex,
                "language": patient.language_preference,
                "location": patient.location,
                "known_conditions": patient.known_conditions,
                "current_medications": patient.current_medications,
            },
            default=str,
        )

    @staticmethod
    def _case_summary(case: Case, extra: dict) -> str:
        data = {
            "case_id": str(case.case_id),
            "status": case.status,
            "chief_complaint": case.chief_complaint,
            "risk_tier": case.risk_tier,
            "risk_flags": case.risk_flags,
            "diagnosis_hypotheses": [
                {"diagnosis": d.diagnosis, "confidence": d.confidence}
                for d in case.diagnosis_hypotheses
            ],
        }
        data.update(extra)
        return json.dumps(data, default=str)
