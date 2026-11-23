# Azure ingestion contribution and integration

Hephzibah-Techbro submitted PR #5 with four commits adding the Azure Functions
HTTP ingestion entry point, Function host/dependency configuration, development
ignore rules, and a structured result return from `src/run_ingestion.py`.
The original commits remain in the branch history.

Integration corrections combine that HTTP entry-point contribution with the
queue-triggered implementation already on `main`. The deployed app lives in
`azure/functions`; the parallel `azure_function` app has been consolidated into
that directory. Both main's private-output ignore rules and the submitted Azurite
rules are retained.

## Request and completion contract

- Send POST `/api/ingest` with a Function key using the `x-functions-key` header.
  Do not commit or print the key.
- HTTP 202 returns a fresh `request_id` and `manifest_path`. It means accepted,
  not completed. The output binding writes to `ingestion-requests` using the
  existing `AzureWebJobsStorage` connection.
- The existing queue worker performs extraction, verification, transformation
  and upload using the configured lake identity. It writes the completed
  manifest last. Inspect that marker to establish success, and inspect logs /
  the poison queue if processing fails.
- The GitHub pipeline may continue submitting directly to the same queue;
  introducing this endpoint does not enable a schedule or deploy resources.
- Local temporary files remain intentional: completed data is uploaded to the
  lake only after validation. The HTTP wrapper itself does not implement direct
  ADLS upload. Shared company config, retries and throttling predate this PR.

## Validation

Run `python -m unittest discover -s azure/tests -v` after installing
`azure/functions/requirements.txt`. Tests cover HTTP acceptance, Function-key
binding, queue contract, packaging and existing publication failure protection.
Cloud deployment and an authenticated live HTTP request require separate runtime
verification; offline tests do not establish a successful cloud deployment.
