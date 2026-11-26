# HOST-010.7 — Bounded RED/PATCH/GREEN cycle

Date: 2026-11-26. Status: VERIFIED for fixed approved fixture and disposable copy.

- Bridge v0.4.0 commit `22406a6ec3498b4796b92b9cd59dcf16bb2236e7`.
- n8n workflow `dD8SkU7mZwf1JN9Y`, manual execution `139`, success.
- UTC 20:46:18.971–20:46:32.393; 13.422 seconds.
- ACP v1, configured model `gemma4:26b`, endpoint `http://127.0.0.1:11434/v1`, toolEvents=0.
- Original SHA-256 `3c11d5994973d4491e99996d11f57bdedcd311d073d5fbfd82a88530ff1815d9`; patched SHA-256 `a3b34c60180aea5c9ac3e33b11bd94f7c06d51e952df6d0ba5fcd1940ec9be83`.
- Original unchanged; temporary workspace removed.
- Model review line 4: The tax is subtracted from the subtotal instead of added. Proposed `return round(subtotal + tax, 2)`.

| Subtotal | Tax rate | Expected | RED actual | GREEN actual |
|---|---|---|---|---|
|100|0.21|121|79|121|
|200|0.10|220|180|220|
|100|0|100|100|100|
|19.99|0.21|24.19|15.79|24.19|

RED 1/4 pass; GREEN 4/4 pass. Independent n8n verifier succeeded. Bridge applied only an allowlisted line change to a temporary copy and executed fixed tests; Hermes did not receive filesystem or terminal tools. No arbitrary execution or general editing validated. Model identity is configured rather than independently attested. No full OS sandbox. Existing workflows and normal Hermes/Ollama services left unchanged. Next: consolidate verified mission interfaces and assess bounded reusable engineering workflow before expanding permissions or integrating CrewAI.
