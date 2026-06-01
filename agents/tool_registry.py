"""
ClinIQ 2.0 tool registry.

Every capability the planner can invoke is registered here as a Tool.
The registry is MCP-style: tools are named, schema-typed, and callable
through a single async execute() interface so the planner never imports
agent modules directly.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("cliniq.tools")


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------


@dataclass
class Tool:
    """A single callable capability exposed to the planner."""

    name: str
    description: str
    input_schema: dict
    output_schema: dict
    agent: str
    async_fn: Callable[..., Any]


class ToolRegistry:
    """Central registry of all ClinIQ tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
        logger.debug("Registered tool '%s' (agent=%s)", tool.name, tool.agent)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict]:
        """Return name + description + input_schema for each tool — safe to send to an LLM."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in self._tools.values()
        ]

    async def execute(self, name: str, inputs: dict) -> dict:
        """
        Invoke a registered tool by name.

        Always returns {success, output, error} so callers never need
        bare try/except around tool calls.
        """
        tool = self._tools.get(name)
        if tool is None:
            logger.error("execute: unknown tool '%s'", name)
            return {"success": False, "output": {}, "error": f"Unknown tool: {name}"}

        logger.info("Executing tool '%s' | inputs=%s", name, list(inputs.keys()))
        try:
            result = await tool.async_fn(inputs)
            logger.info("Tool '%s' succeeded", name)
            return {"success": True, "output": result, "error": None}
        except Exception as exc:
            logger.exception("Tool '%s' raised an exception", name)
            return {"success": False, "output": {}, "error": str(exc)}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

REGISTRY = ToolRegistry()


# ---------------------------------------------------------------------------
# Stub functions — one per tool
# Real implementations injected in later phases.
# ---------------------------------------------------------------------------


async def _stub_pubmed_search(inputs: dict) -> dict:
    return {"articles": [], "total_found": 0}


async def _stub_openfda_check(inputs: dict) -> dict:
    return {"safety_info": {}, "interactions": [], "india_available": True}


async def _stub_india_drug_lookup(inputs: dict) -> dict:
    return {
        "brand_names": [],
        "jan_aushadhi_available": False,
        "approximate_cost": "unknown",
    }


async def _stub_symptom_extractor(inputs: dict) -> dict:
    return {
        "symptoms": [],
        "duration": "unknown",
        "severity": "unknown",
        "extracted_at": "now",
    }


async def _stub_lab_interpreter(inputs: dict) -> dict:
    return {
        "parsed_values": {},
        "abnormal_flags": [],
        "patterns": [],
        "risk_stratification": {},
        "differentials": [],
        "questions": [],
        "action_plan": {},
    }


async def _stub_clinical_reasoner(inputs: dict) -> dict:
    return {
        "differentials": [],
        "risk_tier": "low",
        "risk_flags": [],
        "recommended_tests": [],
    }


async def _stub_india_epidemiology_reranker(inputs: dict) -> dict:
    return {"reranked_differentials": [], "india_specific_flags": []}


async def _stub_monitoring_plan_writer(inputs: dict) -> dict:
    return {"plan_id": "stub", "checkpoints": [], "total_days": 0}


async def _stub_task_writer(inputs: dict) -> dict:
    return {"tasks_created": 0, "task_ids": []}


async def _stub_escalation_evaluator(inputs: dict) -> dict:
    return {
        "should_escalate": False,
        "severity": "watch",
        "reason": "",
        "evidence": [],
    }


async def _stub_whatsapp_message_composer(inputs: dict) -> dict:
    return {"message": "stub message", "language": "en"}


async def _stub_report_generator(inputs: dict) -> dict:
    return {"report_url": "stub", "generated_at": "now"}


# ---------------------------------------------------------------------------
# Tool definitions and registration
# ---------------------------------------------------------------------------

REGISTRY.register(Tool(
    name="pubmed_search",
    description="Search PubMed for clinical evidence on a topic",
    input_schema={
        "type": "object",
        "properties": {
            "query":         {"type": "string"},
            "max_results":   {"type": "integer"},
            "india_filter":  {"type": "boolean"},
        },
        "required": ["query"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "articles":    {"type": "array"},
            "total_found": {"type": "integer"},
        },
    },
    agent="research_agent",
    async_fn=_stub_pubmed_search,
))

REGISTRY.register(Tool(
    name="openfda_check",
    description="Check drug safety, interactions, and Indian market availability",
    input_schema={
        "type": "object",
        "properties": {
            "drug_name":          {"type": "string"},
            "check_interactions": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["drug_name"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "safety_info":      {"type": "object"},
            "interactions":     {"type": "array"},
            "india_available":  {"type": "boolean"},
        },
    },
    agent="drug_safety_agent",
    async_fn=_stub_openfda_check,
))

REGISTRY.register(Tool(
    name="india_drug_lookup",
    description="Look up drug availability in India, Jan Aushadhi alternatives, and CDSCO status",
    input_schema={
        "type": "object",
        "properties": {
            "drug_name": {"type": "string"},
        },
        "required": ["drug_name"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "brand_names":             {"type": "array",  "items": {"type": "string"}},
            "jan_aushadhi_available":  {"type": "boolean"},
            "approximate_cost":        {"type": "string"},
        },
    },
    agent="drug_safety_agent",
    async_fn=_stub_india_drug_lookup,
))

REGISTRY.register(Tool(
    name="symptom_extractor",
    description="Extract structured symptoms from free text or voice transcript",
    input_schema={
        "type": "object",
        "properties": {
            "text":     {"type": "string"},
            "language": {"type": "string"},
        },
        "required": ["text"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "symptoms":     {"type": "array"},
            "duration":     {"type": "string"},
            "severity":     {"type": "string"},
            "extracted_at": {"type": "string"},
        },
    },
    agent="clinical_agent",
    async_fn=_stub_symptom_extractor,
))

REGISTRY.register(Tool(
    name="lab_interpreter",
    description="Run DeepDive analysis on uploaded lab report",
    input_schema={
        "type": "object",
        "properties": {
            "report_type":       {"type": "string"},
            "raw_text":          {"type": "string"},
            "patient_age":       {"type": "integer"},
            "patient_sex":       {"type": "string"},
            "known_conditions":  {"type": "array", "items": {"type": "string"}},
        },
        "required": ["report_type", "raw_text"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "parsed_values":       {"type": "object"},
            "abnormal_flags":      {"type": "array"},
            "patterns":            {"type": "array"},
            "risk_stratification": {"type": "object"},
            "differentials":       {"type": "array"},
            "questions":           {"type": "array"},
            "action_plan":         {"type": "object"},
        },
    },
    agent="deepdive_agent",
    async_fn=_stub_lab_interpreter,
))

REGISTRY.register(Tool(
    name="clinical_reasoner",
    description="Generate differential diagnoses from symptoms and patient context",
    input_schema={
        "type": "object",
        "properties": {
            "symptoms":          {"type": "array"},
            "patient_age":       {"type": "integer"},
            "patient_sex":       {"type": "string"},
            "known_conditions":  {"type": "array", "items": {"type": "string"}},
            "lab_findings":      {"type": "object"},
            "location":          {"type": "string"},
        },
        "required": ["symptoms"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "differentials": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "diagnosis":  {"type": "string"},
                        "confidence": {"type": "number"},
                        "evidence":   {"type": "array"},
                    },
                },
            },
            "risk_tier":         {"type": "string"},
            "risk_flags":        {"type": "array"},
            "recommended_tests": {"type": "array"},
        },
    },
    agent="clinical_agent",
    async_fn=_stub_clinical_reasoner,
))

REGISTRY.register(Tool(
    name="india_epidemiology_reranker",
    description="Rerank differentials using India-specific disease prevalence and seasonal patterns",
    input_schema={
        "type": "object",
        "properties": {
            "differentials": {"type": "array"},
            "location":      {"type": "string"},
            "season":        {"type": "string"},
            "patient_age":   {"type": "integer"},
        },
        "required": ["differentials"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "reranked_differentials":  {"type": "array"},
            "india_specific_flags":    {"type": "array"},
        },
    },
    agent="clinical_agent",
    async_fn=_stub_india_epidemiology_reranker,
))

REGISTRY.register(Tool(
    name="monitoring_plan_writer",
    description="Generate a monitoring plan with checkpoints after a consultation synthesis",
    input_schema={
        "type": "object",
        "properties": {
            "case_id":            {"type": "string"},
            "diagnosis_context":  {"type": "string"},
            "risk_tier":          {"type": "string"},
            "differentials":      {"type": "array"},
            "patient_language":   {"type": "string"},
        },
        "required": ["case_id", "diagnosis_context", "risk_tier"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "plan_id":     {"type": "string"},
            "checkpoints": {"type": "array"},
            "total_days":  {"type": "integer"},
        },
    },
    agent="case_manager_agent",
    async_fn=_stub_monitoring_plan_writer,
))

REGISTRY.register(Tool(
    name="task_writer",
    description="Create follow-up tasks from clinical reasoning output",
    input_schema={
        "type": "object",
        "properties": {
            "case_id":          {"type": "string"},
            "recommended_tests": {"type": "array"},
            "medications":       {"type": "array"},
            "follow_up_days":    {"type": "integer"},
        },
        "required": ["case_id"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "tasks_created": {"type": "integer"},
            "task_ids":      {"type": "array", "items": {"type": "string"}},
        },
    },
    agent="case_manager_agent",
    async_fn=_stub_task_writer,
))

REGISTRY.register(Tool(
    name="escalation_evaluator",
    description="Evaluate if a patient response to a WhatsApp checkpoint warrants escalation",
    input_schema={
        "type": "object",
        "properties": {
            "case_id":          {"type": "string"},
            "patient_response": {"type": "string"},
            "checkpoint":       {"type": "object"},
            "case_history":     {"type": "object"},
        },
        "required": ["case_id", "patient_response", "checkpoint"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "should_escalate": {"type": "boolean"},
            "severity":        {"type": "string"},
            "reason":          {"type": "string"},
            "evidence":        {"type": "array"},
        },
    },
    agent="watch_agent",
    async_fn=_stub_escalation_evaluator,
))

REGISTRY.register(Tool(
    name="whatsapp_message_composer",
    description="Compose a clinically appropriate WhatsApp message for a checkpoint",
    input_schema={
        "type": "object",
        "properties": {
            "questions":          {"type": "array"},
            "patient_name":       {"type": "string"},
            "language":           {"type": "string"},
            "day_offset":         {"type": "integer"},
            "diagnosis_context":  {"type": "string"},
        },
        "required": ["questions", "patient_name"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "message":  {"type": "string"},
            "language": {"type": "string"},
        },
    },
    agent="watch_agent",
    async_fn=_stub_whatsapp_message_composer,
))

REGISTRY.register(Tool(
    name="report_generator",
    description="Generate a structured PDF report from a case",
    input_schema={
        "type": "object",
        "properties": {
            "case_id":     {"type": "string"},
            "report_type": {"type": "string"},
        },
        "required": ["case_id", "report_type"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "report_url":   {"type": "string"},
            "generated_at": {"type": "string"},
        },
    },
    agent="case_manager_agent",
    async_fn=_stub_report_generator,
))

# ---------------------------------------------------------------------------
# Real implementations — each module calls REGISTRY.register() at module
# level, overwriting the stub above with the real async function.
# Imports are at the bottom to avoid circular-import issues: the real modules
# do `from agents.tool_registry import REGISTRY, Tool`, so they must be
# imported AFTER REGISTRY is fully initialised above.
# india_drug_lookup, whatsapp_message_composer, report_generator have no
# real implementation yet — their stubs remain active.
# ---------------------------------------------------------------------------

import agents.tools.symptom_extractor       # noqa: E402, F401
import agents.tools.clinical_reasoner       # noqa: E402, F401
import agents.tools.india_reranker          # noqa: E402, F401
import agents.tools.monitoring_plan_writer  # noqa: E402, F401
import agents.tools.task_writer             # noqa: E402, F401
import agents.tools.escalation_evaluator    # noqa: E402, F401
import agents.tools.pubmed_search           # noqa: E402, F401
import agents.tools.openfda_check           # noqa: E402, F401
import agents.tools.deepdive               # noqa: E402, F401
