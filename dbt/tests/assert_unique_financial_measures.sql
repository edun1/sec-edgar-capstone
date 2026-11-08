select
    cik,
    period_end,
    measure
from {{ ref('stg_financial_measures') }}
group by cik, period_end, measure
having count(*) <> 1
