with periods as (
    select cik, period_end, count(*) as measure_count,
           count(distinct measure) as distinct_measures
    from {{ ref('stg_financial_measures') }}
    group by cik, period_end
)
select cast('invalid period measure count' as varchar(100)) as reason
from periods where measure_count <> 6 or distinct_measures <> 6
union all
select 'invalid total record count'
where (select count(*) from {{ ref('annual_financials') }}) <> 15
union all
select 'invalid source filing coverage'
from {{ source('landing', 'raw_annual_filings') }} f
left join {{ ref('annual_financials') }} a
  on f.cik = a.cik and cast(f.period_end as date) = a.period_end
  and f.accession_number = a.accession_number
where a.cik is null
union all
select 'invalid annual periods per company'
from {{ ref('annual_financials') }}
group by cik having count(*) <> 5
