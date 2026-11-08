select
    ticker,
    cik,
    cast(period_end as date) as period_end,
    cast(nullif(period_start, '') as date) as period_start,
    cast(nullif(duration_days, '') as integer) as duration_days,
    measure,
    cast(value as decimal(38, 2)) as value,
    unit,
    source_tag,
    cast(filing_date as date) as filing_date,
    accession_number,
    form,
    selection_policy,
    source_run_id
from {{ source('landing', 'financial_measures') }}
