# Synthetic four-arm infrastructure experiment

> **Not benchmark or model evidence.** Scripted outcomes test orchestration, treatment separation, metrics, and evidence plumbing only.

| Arm | Pass rate | Cell accuracy | FFR | Recovery yield | Valid artifacts | Actions | Tokens | Latency | Cost |
|---|---|---|---|---|---|---|---|---|---|
| A | 0.2500 | 0.2500 | N/A | N/A | 1.0000 | 1.0000 | 5.0000 | 0.2500 | 0.0000 |
| B | 0.5000 | 0.5000 | N/A | N/A | 1.0000 | 1.0000 | 10.0000 | 0.0000 | 0.0000 |
| C | 0.5000 | 0.5000 | 0.3333 | N/A | 1.0000 | 1.0000 | 10.0000 | 0.2500 | 0.0000 |
| D | 1.0000 | 1.0000 | 0.0000 | 1.0000 | 1.0000 | 1.5000 | 5.0000 | 1.0000 | 0.0000 |

Expected falsification signal: Arm C deliberately records one false fulfilment; Arm D recovers both first-transition failures. Observed metrics match that construction. The result validates infrastructure arithmetic only and cannot support the research hypothesis.

The visual-intent task s3 retains a deterministic PPM render and `render_eval` event. This validates multimodal evidence plumbing, not visual-model accuracy.
