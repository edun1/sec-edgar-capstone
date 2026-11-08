select
    cik,
    period_end
from {{ ref('annual_financials') }}
group by cik, period_end
having count(*) <> 1

union all

select
    cik,
    period_end
from {{ ref('annual_financials') }}
where revenue is null
   or net_income is null
   or assets is null
   or liabilities is null
   or equity is null
   or operating_cash_flow is null
   or abs(balance_sheet_difference_usd) > 1
