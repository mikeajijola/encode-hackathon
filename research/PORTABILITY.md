# Text/config portability check

The `adapters.text_config` package is a deliberately tiny second artifact adapter. It
uses bounded `file/<relative-path>` selectors, optional JSON Pointers, UTF-8/JSON
validation, deterministic desired-value evals, and scoped edits. It reuses the same
broker and reconciliation loop used by the first adapter.

The following generic modules were unchanged while adding this adapter (SHA-256 at
the branch point):

| Module | SHA-256 |
|---|---|
| `fulfilment/models.py` | `279a409c6ffdb248bef974b4b49c331561a9ffba540bf1445966bfef123da0e7` |
| `fulfilment/broker.py` | `f7b6c76bb42c01212f2c5fe28f903ca137240614db4f2a1bdc208f9f56b919f9` |
| `fulfilment/control.py` | `c22766be9c1b10ed17047a0a6ec3ff01627c97739724b39560980fd6034276c2` |
| `fulfilment/completion.py` | `23ff55edd950f29d45f9b12b1e25299c5a4b5c6ed61e1232ccf746cd505bd832` |
| `fulfilment/evidence.py` | `6ff34321c7365f9d65d54d64630093ee78747b3932c595fd5f5428e735b23d55` |

Recheck with `sha256sum fulfilment/{models,broker,control,completion,evidence}.py`.
The integration test proves two-step convergence, scope rejection, invalid-artifact
refusal, and evidence-chain reconstruction. Rendered/multimodal evaluation is not
applicable: this adapter's contract concerns plain configuration values and has no
visual or layout semantics.
