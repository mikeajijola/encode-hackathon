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
using the candidate's resolved value. Target style changes are discarded because
the current capability effects are value/formula-only; partial formula groups
fail closed. The reconstructed workbook is loaded and independently
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
fixes that parsing boundary, uses original style IDs, and is validated before the
controlled task rerun. Extra model calls and model actions for reconstruction are zero.

Integration preflight exposed two additional boundary requirements. Checkpoints
must be recorded after commit, otherwise recovery analysis sees isolated candidate
states. Recalculation must preserve target styles while transacting values:
LibreOffice changed target style metadata even in a two-cell calculation probe.
Both changes are restricted to transaction/evidence handling; three-valued
completion and official evaluation code are unchanged.

The image's default home was root-owned, and an attempted registered host-UID
configuration also failed LibreOffice profile creation. The validated execution
configuration therefore retains the image's runner UID and adds a writable
tmpfs at its existing home. This operational deviation is explicit. The brief
default-home task run was aborted on the independent profile-creation failure,
before using task outcomes to change code; its evidence is retained separately.

Pre-registered remote gate: <=1 preservation violation, original fixes preserved,
FFR=0, precision=100%, validity=100%, and pass rate >=45%. Zero FULFILLED claims
does not satisfy precision. Any failed gate stops before A/B/C/D.
