# Validation performed before Azure access

Prepared 13 November 2026. **No resources deployed, no Azure connectivity verified, and no money spent by these checks.**

Passed:

- Bicep CLI 0.49.2 compilation with no warnings after validating storage-name length bounds.
- Python syntax compilation for shared source and cloud code.
- Eleven cloud contract/worker tests, using mocked Azure I/O: incomplete or foreign manifests, missing/duplicate files, malformed hashes, SQL schema validation, duplicate completed requests, worker failure without a completed marker, and invalid request IDs.
- Three existing local-runner tests (failure exit, stop-on-failure summary, concurrent lock).
- Cloud package dependency resolution and `pip check` in an isolated Linux/Python 3.12 environment.
- Azure SQL dbt project parsing with dbt-core 1.12.7 and dbt-sqlserver 1.9.2 using placeholder environment variables. Parsing does not connect to SQL or execute T-SQL. The adapter emitted its existing schema-concatenation behaviour warning; no custom schemas are configured here.
- Function ZIP packaging includes root function_app.py, host.json and requirements.txt plus shared src/ and config/; excludes .env and raw datasets.

Not verified:

- Subscription quotas, region/SKU availability, Microsoft policies or actual cost.
- ARM what-if against a subscription, infrastructure creation or managed identity propagation.
- Functions remote build, queue binding/lease behaviour on real storage, SEC access from an Azure IP, retries or Function timeouts under load.
- OIDC login, ODBC connectivity, SQL permission bootstrap, actual dbt SQL execution/tests, or transactional reporting publication on Azure SQL.
- GitHub Actions execution and firewall cleanup on cancellation.
- Power BI Azure SQL authentication, Power BI Service publication/licensing or scheduled refresh.

The README includes the required deployment and validation sequence. Do not describe this branch as a live Azure deployment until those steps pass and their evidence is recorded.
