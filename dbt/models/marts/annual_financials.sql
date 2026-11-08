with annual_values as (
    select
        ticker,
        cik,
        period_end,
        filing_date,
        accession_number,
        selection_policy,
        source_run_id,
        max(period_start) as period_start,
        max(duration_days) as duration_days,
        max(case when measure = 'revenue' then value end) as revenue,
        max(case when measure = 'net_income' then value end) as net_income,
        max(case when measure = 'assets' then value end) as assets,
        max(case when measure = 'liabilities' then value end) as liabilities,
        max(case when measure = 'equity' then value end) as equity,
        max(case when measure = 'operating_cash_flow' then value end)
            as operating_cash_flow
    from {{ ref('stg_financial_measures') }}
    group by
        ticker,
        cik,
        period_end,
        filing_date,
        accession_number,
        selection_policy,
        source_run_id
),

previous_periods as (
    select
        *,
        lag(revenue) over (
            partition by cik order by period_end
        ) as previous_revenue,
        lag(period_end) over (
            partition by cik order by period_end
        ) as previous_period_end
    from annual_values
)

select
    *,
    year(period_end) as fiscal_year_end_year,
    100.0 * net_income / nullif(revenue, 0) as net_profit_margin_pct,
    case
        when date_diff('day', previous_period_end, period_end)
             between 350 and 380
        then 100.0 * (revenue - previous_revenue)
             / nullif(previous_revenue, 0)
    end as revenue_growth_pct,
    assets - liabilities - equity as balance_sheet_difference_usd
from previous_periods
