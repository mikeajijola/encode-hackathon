# Three-valued epistemic completion

The aggregation domain is `FULFILLED | UNFULFILLED | UNKNOWN`.

- `FULFILLED`: all required assertions and safety conditions have positive,
  adequately covered evidence.
- `UNFULFILLED`: evidence positively establishes a required semantic or safety
  failure and execution has terminated.
- `UNKNOWN`: required evidence is missing, errored, uncertain, insufficiently
  covered, or cannot distinguish the representation being inspected from the
  property required by the contract.

Aggregation order:

1. Proven artifact invalidity, preservation failure, invariant violation, or a
   definite desired-state failure produces `UNFULFILLED`.
2. Missing required evals, evaluator errors/uncertainty, incomplete source
   coverage, and representation ambiguity produce `UNKNOWN`.
3. Only complete required passes with adequate evidence produce `FULFILLED`.

`UNKNOWN` is not a completion claim and is excluded from the FFR denominator. It
is retained separately in benchmark reporting, including its external PASS/FAIL
split. The decision record includes status, failed/unknown conditions,
observation, discrepancies, and artifact hash, so it is reconstructable.

The policy is artifact-neutral. Adapters expose evidence-adequacy metadata; the
generic completion layer performs the three-valued aggregation.
