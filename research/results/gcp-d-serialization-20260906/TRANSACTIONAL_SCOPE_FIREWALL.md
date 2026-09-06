# Transactional scope firewall

Hypothesis: reconstructing approved value/formula changes against the original
package prevents serializer side effects without changing completion decisions.
Parent: c70e0b5. The services/completion implementation and official scorer are
unchanged. Existing recalculation rollback is unchanged.

The generic broker snapshots, stages, invokes, inspects, authorizes, atomically
commits or rolls back, and traces the actual final hash. Spreadsheet hooks own
package reconstruction. Every registered spreadsheet MUTATE capability uses
the same boundary. No spreadsheet imports enter the generic broker.

The candidate executes in a separate file. Raw XML value reconstruction copies
only authorized cell nodes into the original worksheet bytes, retaining original
style IDs and all other package members. Shared strings become inline strings
using the candidate's resolved value. Target style changes and partial formula
groups fail closed. The reconstructed workbook is loaded and independently
diffed before commit. Unsupported features are retained from the original.

File staging is isolation for cooperative adapter code, not a security sandbox
against arbitrary malicious code with filesystem access. Other artifact adapters
can implement the same hooks; legacy snapshot-only adapters retain their prior
behavior. Thus this experiment proves spreadsheet coverage and reusable broker
semantics, not complete transaction coverage for arbitrary future adapters.

Four fixed-transition strategies are compared offline: retained ordinary save,
openpyxl reconstruction from original, tree-level OOXML cell transplantation,
and raw XML value reconstruction. The tree strategy exposed invalid style-ID
references on 47766. The first raw implementation exposed a self-closing-cell
regex bug on 58147. Both failed trials are retained. The selected raw strategy
fixes that parsing boundary, uses original style IDs, and is validated before any
new model run. Extra model calls and model actions for reconstruction are zero.

Pre-registered remote gate: <=1 preservation violation, original fixes preserved,
FFR=0, precision=100%, validity=100%, and pass rate >=45%. Zero FULFILLED claims
does not satisfy precision. Any failed gate stops before A/B/C/D.
