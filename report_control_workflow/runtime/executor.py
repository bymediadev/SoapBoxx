# report_control_workflow/runtime/executor.py
"""
Optional LLM injection layer (reserved).

Callers pass callables into :func:`report_control_workflow.pipeline.control_pipeline.run_control_pipeline`;
this module is a stable hook point for future wrappers (timeouts, retries, tracing).
"""
