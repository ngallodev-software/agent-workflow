# PROC-002 control-intent matrix

The installed delegation journey `test_installed_control_intent_matrix_is_durable_correlated_and_append_only` exercises one isolated run for each bridge edge case:

| Request | Expected authority evidence |
| --- | --- |
| duplicate request ID | first intent is applied; the repeat is durably rejected as a duplicate |
| malformed control kind | intent is durably rejected and its request ID appears in the host error message |
| stale sequence | the valid predecessor is applied; the out-of-order intent is durably rejected |
| post-exit request | the intent is durably rejected after executor exit |

Each row reads the installed product's `control-intents.jsonl` and `messages.jsonl`. The former is append-only host disposition evidence; the latter carries the correlated request ID in the authoritative error event. The journey does not exercise late steering, inbox, supervisor, or wake/resume behavior.
