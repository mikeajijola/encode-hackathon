# Evidence retention verification

Remote and local archive SHA-256 independently match:
3d927b08e10045ee39be2073aad107d265466a7dde25e316c162775162a58ce6.

The archive extracts successfully. It contains the complete final run, all
mutation checkpoints and official scores, contracts, observations, discrepancies,
broker evidence, model traces, manifests, image/runtime provenance, offline
strategy artifacts and diffs, rendered comparisons, the parent retained run,
20 initial development artifacts, and failed setup/operational trials.

All available broker hash chains verify; final artifact hashes match task
records; every mutation-checkpoint hash matches its event. An independent final
artifact audit finds zero preservation violations. A literal credential scan of
all 563 extracted files finds zero matches. The secret exists in neither the
archive nor its extracted evidence. Offline official labels remain outside the
fulfilment-time image and mount boundary.

The full A/B/C/D experiment is not authorized by the measured gate: final pass
rate is 30%, versus the parent's 45%. No held-out experiment was run.
