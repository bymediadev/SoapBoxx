# CURSOR EXECUTION PROMPT — FINAL 10% HARDENING PLAN

## SYSTEM INSTRUCTIONS (DO NOT IGNORE)

You are operating inside a production-grade Python backend system with a fully working evaluation architecture.

### HARD CONSTRAINTS

* Do NOT refactor architecture
* Do NOT rename existing core entities unless explicitly listed
* Do NOT change snapshot/evaluator/finalizer structure
* Do NOT modify passing tests unless required for new fields
* Do NOT add new abstraction layers
* Do NOT introduce new parallel evaluation paths
* Preserve deterministic behavior at all times

### EXECUTION RULE

* Work in phases
* STOP after EACH phase
* Run tests after EACH phase
* Do NOT proceed unless all phase tests pass
* Report results before continuing

---

## GOAL

Harden the system for production readiness by implementing:

* failure safety
* retry correctness
* observability consistency
* deterministic execution under load
* schema/version safety

---

## PHASE 1 — EXECUTION CONTROL (CRITICAL PATH)

### Task 1: Cancellation Safety

* Ensure `_ollama_chat` cannot leave:

  * orphan threads
  * dangling HTTP reads
  * runaway heartbeat loops

* Add cleanup on:

  * timeout
  * exception
  * cancellation

#### ACCEPTANCE CHECK

* Forced cancellation → no background threads remain

---

### Task 2: Retry System (Bounded + Classified)

* Add exponential backoff retry wrapper for Ollama calls
* Add hard retry limit
* Classify retry types:

  * `connect_failure`
  * `read_timeout`
  * `http_5xx`

#### ACCEPTANCE CHECK

* Simulated failure → retries occur and terminate cleanly

---

### Task 3: Timeout Classification

* Split timeout types:

  * `timeout_first_byte`
  * `timeout_read_body`

* Ensure classification is returned in final metadata

#### ACCEPTANCE CHECK

* Delayed response simulation → correct timeout type emitted

---

### STOP CONDITION (MANDATORY)

After Phase 1:

1. Run full test suite
2. Ensure all tests pass
3. Summarize changes
4. STOP EXECUTION

DO NOT PROCEED UNTIL EXPLICITLY APPROVED

---

## PHASE 2 — FAILURE CONSISTENCY LAYER

### Task 4: Unified Failure Taxonomy

Create strict enum/constants:

* `timeout_first_byte`
* `timeout_read_body`
* `cancelled`
* `degraded`
* `evaluation_failed`

Ensure ALL failure paths use this system.

---

### Task 5: Degraded Mode Path

* If evaluation fails:

  * return minimal valid brief
  * set `export_status = degraded`
  * preserve trace + snapshot hash

---

### STOP CONDITION

* Run full test suite
* Verify degraded mode works
* STOP EXECUTION

---

## PHASE 3 — OBSERVABILITY HARDENING

### Task 6: Trace ID Propagation

Add `trace_id` to:

* workflow
* evaluator snapshot
* finalizer output
* heartbeat logs

---

### Task 7: Joinable Timeline Logging

Ensure every log entry includes:

* trace_id
* stage name
* timestamp

---

### STOP CONDITION

* Run full tests
* Validate trace continuity across modules
* STOP EXECUTION

---

## PHASE 4 — STABILITY VERIFICATION

### Task 8: Parallel Determinism Test

* Same input executed twice concurrently
* Must produce identical:

  * `snapshot_hash`
  * evaluation output

---

### Task 9: Memory / Teardown Safety

* Ensure no cross-run state leakage:

  * evaluator
  * workflow cache
  * heartbeat state

---

### Task 10: Batch Stability Test

* Run 50–200 episode loop
* Validate:

  * no memory growth
  * no latency drift
  * no divergence

---

### STOP CONDITION

* Run full suite + batch test
* Confirm stability metrics
* STOP EXECUTION

---

## PHASE 5 — CONTRACT LOCKING

### Task 11: Schema Version Lock

Add:

* `evaluation_snapshot_version`
* `resolver_version`

Reject mixed-version execution within a run.

---

### Task 12: Compatibility Layer

Ensure:

* existing `export_status` consumers still function
* no breaking API changes

---

## FINAL ACCEPTANCE CRITERIA

System is complete ONLY if:

### Correctness

* All tests pass
* No ambiguous failure states

### Stability

* 50+ episode batch shows no drift

### Observability

* Every run reconstructable via `trace_id`

### Failure Behavior

* Every failure maps to exactly one taxonomy class

### Determinism

* Identical inputs → identical outputs (even in parallel)

---

## ABSOLUTE PROHIBITIONS

* Do not redesign architecture
* Do not introduce new evaluation systems
* Do not duplicate snapshot logic
* Do not bypass finalizer
* Do not create parallel truth sources

---

## EXECUTION STYLE

* Implement minimally
* Prefer modification over addition
* Stop frequently
* Report clearly after each phase
* Never proceed without passing tests

---

## Optional follow-up

Convert this plan into a **GitHub Actions CI gate** so accidental drift gets blocked at PR level.
