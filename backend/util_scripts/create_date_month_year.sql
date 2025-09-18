UPDATE core_decision 
SET 
    issue_date_day = DATE(issue_date),
    issue_date_month = DATE_TRUNC('month', issue_date)::date,
    issue_date_year = EXTRACT(year FROM issue_date)
WHERE issue_date IS NOT NULL 
  AND (issue_date_day IS NULL OR issue_date_month IS NULL OR issue_date_year IS NULL);