-- ============================================================
-- sql/05_extract_raw_data.sql
-- ============================================================
-- The Darko Method 2026
-- Schema: banking
--
-- PURPOSE:
--   This is the production extraction query.
--   It joins all five tables in the banking schema into one flat
--   file for fraud detection and customer risk analysis.
--
-- REAL SCHEMA TABLES (from banking_schema_postgres.sql):
--   banking.customers    — customer_id, first_name, last_name,
--                          email, phone, date_of_birth, city,
--                          credit_score, customer_since,
--                          segment, is_active
--   banking.accounts     — account_id, customer_id, account_type,
--                          account_number, balance, currency,
--                          opened_date, status, branch,
--                          interest_rate
--   banking.transactions — transaction_id, account_id, customer_id,
--                          transaction_date, transaction_time,
--                          amount, transaction_type, merchant_name,
--                          merchant_category, channel, status,
--                          is_fraud, balance_after
--   banking.loans        — loan_id, customer_id, loan_type,
--                          principal, interest_rate, term_months,
--                          monthly_payment, disbursed_date,
--                          outstanding_balance, status, risk_grade
--   banking.fraud_alerts — alert_id, transaction_id, customer_id,
--                          alert_date, alert_type, severity,
--                          status, amount_at_risk
--
-- OUTPUT: data/raw-data.csv  (43 columns, aliased for clarity)
--
-- ALIAS CONVENTIONS (prevents ambiguous column names):
--   transactions.status  -> transaction_status
--   accounts.status      -> account_status
--   accounts.interest_rate -> account_interest_rate
--   loans.status         -> loan_status
--   loans.interest_rate  -> loan_interest_rate
--   loans.outstanding_balance -> loan_outstanding_balance
--   fraud_alerts.severity -> alert_severity
--   fraud_alerts.status  -> alert_status
--
-- JOIN STRATEGY:
--   transactions is the anchor — every row is one transaction.
--   INNER JOINs on customers, accounts (every transaction must
--   have these). LEFT JOINs on loans and fraud_alerts (not every
--   transaction has a matching loan or fraud alert).
--
-- HOW TO TEST IN DBEAVER:
--   Run each section individually. Start with Section 1 to
--   understand each table, then Section 5 to verify the full
--   extract shape before running: python run.py
-- ============================================================


-- ============================================================
-- SECTION 1: BASICS — Explore each table individually
-- (Run these one at a time in DBeaver)
-- ============================================================

-- 1.1 Preview transactions
SELECT *
FROM banking.transactions
LIMIT 10;

-- 1.2 Preview customers
SELECT *
FROM banking.customers
LIMIT 10;

-- 1.3 Preview accounts
SELECT *
FROM banking.accounts
LIMIT 10;

-- 1.4 Preview loans
SELECT *
FROM banking.loans
LIMIT 10;

-- 1.5 Preview fraud_alerts
SELECT *
FROM banking.fraud_alerts
LIMIT 10;

-- 1.6 Row counts across all five tables
SELECT 'customers'    AS table_name, COUNT(*) AS row_count FROM banking.customers
UNION ALL
SELECT 'accounts',    COUNT(*) FROM banking.accounts
UNION ALL
SELECT 'transactions',COUNT(*) FROM banking.transactions
UNION ALL
SELECT 'loans',       COUNT(*) FROM banking.loans
UNION ALL
SELECT 'fraud_alerts',COUNT(*) FROM banking.fraud_alerts;

-- 1.7 Distinct account types and statuses
SELECT DISTINCT account_type, status
FROM banking.accounts
ORDER BY account_type, status;

-- 1.8 Distinct transaction types
SELECT DISTINCT transaction_type
FROM banking.transactions
ORDER BY transaction_type;

-- 1.9 Distinct channels
SELECT DISTINCT channel
FROM banking.transactions
ORDER BY channel;

-- 1.10 Distinct customer segments
SELECT DISTINCT segment
FROM banking.customers
ORDER BY segment;

-- 1.11 Distinct loan types and risk grades
SELECT DISTINCT loan_type, risk_grade
FROM banking.loans
ORDER BY loan_type, risk_grade;

-- 1.12 Distinct merchant categories
SELECT DISTINCT merchant_category
FROM banking.transactions
ORDER BY merchant_category;

-- 1.13 Distinct fraud alert types and severities
SELECT DISTINCT alert_type, severity
FROM banking.fraud_alerts
ORDER BY alert_type, severity;

-- 1.14 Fraud overview
SELECT
    COUNT(*)                                            AS total_transactions,
    COUNT(CASE WHEN is_fraud THEN 1 END)               AS fraud_transactions,
    ROUND(
        COUNT(CASE WHEN is_fraud THEN 1 END)::NUMERIC
        / NULLIF(COUNT(*), 0) * 100, 2
    )                                                  AS fraud_rate_pct
FROM banking.transactions;

-- 1.15 Active vs inactive customers
SELECT is_active, COUNT(*) AS customer_count
FROM banking.customers
GROUP BY is_active;


-- ============================================================
-- SECTION 2: AGGREGATIONS — Summary statistics
-- ============================================================

-- 2.1 Overall transaction summary
SELECT
    COUNT(*)                                            AS total_transactions,
    SUM(amount)                                        AS total_volume,
    ROUND(AVG(amount)::NUMERIC, 2)                     AS avg_transaction,
    MIN(amount)                                        AS min_amount,
    MAX(amount)                                        AS max_amount,
    COUNT(CASE WHEN is_fraud THEN 1 END)               AS fraud_count,
    ROUND(
        COUNT(CASE WHEN is_fraud THEN 1 END)::NUMERIC
        / NULLIF(COUNT(*), 0) * 100, 2
    )                                                  AS fraud_rate_pct
FROM banking.transactions;

-- 2.2 Transaction volume and fraud rate by channel
SELECT
    channel,
    COUNT(*)                                            AS total_transactions,
    SUM(amount)                                        AS total_volume,
    ROUND(AVG(amount)::NUMERIC, 2)                     AS avg_transaction,
    COUNT(CASE WHEN is_fraud THEN 1 END)               AS fraud_count,
    ROUND(
        COUNT(CASE WHEN is_fraud THEN 1 END)::NUMERIC
        / NULLIF(COUNT(*), 0) * 100, 2
    )                                                  AS fraud_rate_pct
FROM banking.transactions
GROUP BY channel
ORDER BY total_volume DESC;

-- 2.3 Fraud rate by merchant category
SELECT
    merchant_category,
    COUNT(*)                                            AS total_transactions,
    SUM(amount)                                        AS total_volume,
    COUNT(CASE WHEN is_fraud THEN 1 END)               AS fraud_count,
    ROUND(
        COUNT(CASE WHEN is_fraud THEN 1 END)::NUMERIC
        / NULLIF(COUNT(*), 0) * 100, 2
    )                                                  AS fraud_rate_pct
FROM banking.transactions
GROUP BY merchant_category
ORDER BY fraud_rate_pct DESC;

-- 2.4 Account balance summary by account type
SELECT
    account_type,
    COUNT(*)                                            AS total_accounts,
    ROUND(AVG(balance)::NUMERIC, 2)                    AS avg_balance,
    SUM(balance)                                       AS total_balance,
    MIN(balance)                                       AS min_balance,
    MAX(balance)                                       AS max_balance
FROM banking.accounts
GROUP BY account_type
ORDER BY total_balance DESC;

-- 2.5 Loan portfolio summary by type and risk grade
SELECT
    loan_type,
    risk_grade,
    COUNT(*)                                            AS total_loans,
    SUM(principal)                                     AS total_principal,
    SUM(outstanding_balance)                           AS total_outstanding,
    ROUND(AVG(interest_rate * 100)::NUMERIC, 2)        AS avg_interest_rate_pct,
    COUNT(CASE WHEN status = 'Delinquent' THEN 1 END)  AS delinquent_loans
FROM banking.loans
GROUP BY loan_type, risk_grade
ORDER BY loan_type, risk_grade;

-- 2.6 Customer credit score distribution by segment
SELECT
    segment,
    COUNT(*)                                            AS total_customers,
    ROUND(AVG(credit_score)::NUMERIC, 0)               AS avg_credit_score,
    MIN(credit_score)                                  AS min_credit_score,
    MAX(credit_score)                                  AS max_credit_score
FROM banking.customers
GROUP BY segment
ORDER BY avg_credit_score DESC;

-- 2.7 Monthly transaction volume trend
SELECT
    DATE_TRUNC('month', transaction_date)              AS month,
    COUNT(*)                                            AS total_transactions,
    SUM(amount)                                        AS total_volume,
    COUNT(CASE WHEN is_fraud THEN 1 END)               AS fraud_count
FROM banking.transactions
GROUP BY month
ORDER BY month;

-- 2.8 Fraud alert summary by severity
SELECT
    severity,
    COUNT(*)                                            AS total_alerts,
    SUM(amount_at_risk)                                AS total_amount_at_risk,
    ROUND(AVG(amount_at_risk)::NUMERIC, 2)             AS avg_amount_at_risk
FROM banking.fraud_alerts
GROUP BY severity
ORDER BY
    CASE severity
        WHEN 'Critical' THEN 1
        WHEN 'High'     THEN 2
        WHEN 'Medium'   THEN 3
        WHEN 'Low'      THEN 4
    END;


-- ============================================================
-- SECTION 3: JOINS — Combined views
-- ============================================================

-- 3.1 Transactions with customer and account details
SELECT
    t.transaction_id,
    t.transaction_date,
    t.transaction_type,
    t.amount,
    t.channel,
    t.is_fraud,
    c.first_name,
    c.last_name,
    c.segment,
    c.credit_score,
    a.account_type,
    a.balance                                          AS account_balance,
    a.status                                           AS account_status
FROM banking.transactions t
JOIN banking.customers c ON t.customer_id = c.customer_id
JOIN banking.accounts  a ON t.account_id  = a.account_id
ORDER BY t.transaction_date DESC
LIMIT 20;

-- 3.2 Fraudulent transactions with fraud alert details
SELECT
    t.transaction_id,
    t.transaction_date,
    t.amount,
    t.merchant_name,
    t.merchant_category,
    t.channel,
    c.first_name || ' ' || c.last_name                 AS customer_name,
    c.segment,
    c.credit_score,
    fa.alert_type,
    fa.severity,
    fa.status                                          AS alert_status,
    fa.amount_at_risk
FROM banking.transactions t
JOIN banking.customers c       ON t.customer_id     = c.customer_id
LEFT JOIN banking.fraud_alerts fa ON t.transaction_id = fa.transaction_id
WHERE t.is_fraud = TRUE
ORDER BY t.transaction_date DESC
LIMIT 20;

-- 3.3 Customers with their loan and account overview
SELECT
    c.customer_id,
    c.first_name || ' ' || c.last_name                 AS customer_name,
    c.segment,
    c.credit_score,
    a.account_type,
    a.balance,
    a.status                                           AS account_status,
    l.loan_type,
    l.principal,
    l.outstanding_balance,
    l.risk_grade,
    l.status                                           AS loan_status
FROM banking.customers c
JOIN banking.accounts a  ON c.customer_id = a.customer_id
LEFT JOIN banking.loans l ON c.customer_id = l.customer_id
ORDER BY c.customer_id
LIMIT 20;

-- 3.4 Full five-table join — one row per transaction
SELECT
    t.transaction_id,
    t.transaction_date,
    t.amount,
    t.transaction_type,
    t.merchant_category,
    t.channel,
    t.is_fraud,
    c.first_name,
    c.last_name,
    c.segment,
    c.credit_score,
    a.account_type,
    a.balance                                          AS account_balance,
    l.loan_type,
    l.risk_grade,
    l.outstanding_balance                              AS loan_outstanding,
    fa.alert_type,
    fa.severity                                        AS alert_severity,
    fa.status                                          AS alert_status
FROM banking.transactions t
JOIN banking.customers c   ON t.customer_id     = c.customer_id
JOIN banking.accounts a    ON t.account_id      = a.account_id
LEFT JOIN banking.loans l  ON t.customer_id     = l.customer_id
LEFT JOIN banking.fraud_alerts fa ON t.transaction_id = fa.transaction_id
ORDER BY t.transaction_date DESC;

-- 3.5 High-risk customers — fraud flag + low credit + active loans
SELECT
    c.customer_id,
    c.first_name || ' ' || c.last_name                 AS customer_name,
    c.credit_score,
    c.segment,
    COUNT(DISTINCT t.transaction_id)                   AS total_transactions,
    COUNT(CASE WHEN t.is_fraud THEN 1 END)             AS fraud_count,
    l.loan_type,
    l.risk_grade,
    l.outstanding_balance,
    COUNT(fa.alert_id)                                 AS total_alerts,
    MAX(fa.severity)                                   AS worst_alert_severity
FROM banking.customers c
JOIN banking.transactions t    ON c.customer_id     = t.customer_id
LEFT JOIN banking.loans l      ON c.customer_id     = l.customer_id
LEFT JOIN banking.fraud_alerts fa ON t.transaction_id = fa.transaction_id
GROUP BY
    c.customer_id, c.first_name, c.last_name,
    c.credit_score, c.segment,
    l.loan_type, l.risk_grade, l.outstanding_balance
HAVING COUNT(CASE WHEN t.is_fraud THEN 1 END) > 0
ORDER BY fraud_count DESC
LIMIT 10;


-- ============================================================
-- SECTION 4: CTEs & WINDOW FUNCTIONS
-- ============================================================

-- 4.1 CTE — Customer risk profile summary
WITH customer_risk AS (
    SELECT
        c.customer_id,
        c.first_name || ' ' || c.last_name             AS customer_name,
        c.segment,
        c.credit_score,
        c.city,
        COUNT(t.transaction_id)                        AS total_transactions,
        SUM(t.amount)                                  AS total_volume,
        COUNT(CASE WHEN t.is_fraud THEN 1 END)         AS fraud_count,
        ROUND(AVG(t.amount)::NUMERIC, 2)               AS avg_transaction,
        COUNT(fa.alert_id)                             AS total_alerts,
        SUM(fa.amount_at_risk)                         AS total_amount_at_risk
    FROM banking.customers c
    JOIN banking.transactions t    ON c.customer_id     = t.customer_id
    LEFT JOIN banking.fraud_alerts fa ON t.transaction_id = fa.transaction_id
    GROUP BY
        c.customer_id, c.first_name, c.last_name,
        c.segment, c.credit_score, c.city
)
SELECT *
FROM customer_risk
ORDER BY fraud_count DESC, total_amount_at_risk DESC;

-- 4.2 CTE — Loan health summary
WITH loan_health AS (
    SELECT
        l.customer_id,
        c.first_name || ' ' || c.last_name             AS customer_name,
        c.credit_score,
        l.loan_type,
        l.risk_grade,
        l.principal,
        l.outstanding_balance,
        l.status                                       AS loan_status,
        ROUND(
            l.outstanding_balance / NULLIF(l.principal, 0) * 100, 2
        )                                              AS pct_outstanding
    FROM banking.loans l
    JOIN banking.customers c ON l.customer_id = c.customer_id
)
SELECT *
FROM loan_health
ORDER BY pct_outstanding DESC;

-- 4.3 Window function — Rank customers by transaction volume
SELECT
    c.customer_id,
    c.first_name || ' ' || c.last_name                 AS customer_name,
    c.segment,
    SUM(t.amount)                                      AS total_volume,
    RANK() OVER (
        ORDER BY SUM(t.amount) DESC
    )                                                  AS volume_rank
FROM banking.customers c
JOIN banking.transactions t ON c.customer_id = t.customer_id
GROUP BY c.customer_id, c.first_name, c.last_name, c.segment
ORDER BY volume_rank;

-- 4.4 Window function — Rank customers by volume within each segment
SELECT
    c.first_name || ' ' || c.last_name                 AS customer_name,
    c.segment,
    SUM(t.amount)                                      AS total_volume,
    RANK() OVER (
        PARTITION BY c.segment
        ORDER BY SUM(t.amount) DESC
    )                                                  AS rank_in_segment
FROM banking.customers c
JOIN banking.transactions t ON c.customer_id = t.customer_id
GROUP BY c.customer_id, c.first_name, c.last_name, c.segment
ORDER BY c.segment, rank_in_segment;

-- 4.5 Window function — Running balance after each transaction per account
SELECT
    transaction_id,
    account_id,
    transaction_date,
    transaction_time,
    amount,
    transaction_type,
    balance_after,
    LAG(balance_after) OVER (
        PARTITION BY account_id
        ORDER BY transaction_date, transaction_time
    )                                                  AS prev_balance,
    balance_after - LAG(balance_after) OVER (
        PARTITION BY account_id
        ORDER BY transaction_date, transaction_time
    )                                                  AS balance_change
FROM banking.transactions
ORDER BY account_id, transaction_date, transaction_time;

-- 4.6 CTE + Window — Month-over-month transaction volume growth
WITH monthly_volume AS (
    SELECT
        DATE_TRUNC('month', transaction_date)          AS month,
        SUM(amount)                                    AS volume,
        COUNT(*)                                       AS transaction_count,
        COUNT(CASE WHEN is_fraud THEN 1 END)           AS fraud_count
    FROM banking.transactions
    GROUP BY month
)
SELECT
    month,
    volume,
    transaction_count,
    fraud_count,
    LAG(volume) OVER (ORDER BY month)                  AS prev_month_volume,
    ROUND(
        (volume - LAG(volume) OVER (ORDER BY month))
        / NULLIF(LAG(volume) OVER (ORDER BY month), 0) * 100, 2
    )                                                  AS pct_growth
FROM monthly_volume
ORDER BY month;

-- 4.7 Window function — Fraud velocity (running fraud count per customer)
SELECT
    t.customer_id,
    t.transaction_date,
    t.amount,
    t.is_fraud,
    SUM(CASE WHEN t.is_fraud THEN 1 ELSE 0 END) OVER (
        PARTITION BY t.customer_id
        ORDER BY t.transaction_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )                                                  AS cumulative_fraud_count
FROM banking.transactions t
ORDER BY t.customer_id, t.transaction_date;


-- ============================================================
-- SECTION 5: RAW DATA EXTRACT (produces data/raw-data.csv)
-- ============================================================
-- Joins all five tables into one flat extract of 43 columns.
-- transactions is the anchor — every row is one transaction.
-- loans and fraud_alerts use LEFT JOINs — NULLs are expected
-- and intentionally preserved for Module 05 ETL.
--
-- COLUMN COUNT: 43
--   transactions (13): transaction_id, account_id, customer_id,
--     transaction_date, transaction_time, amount, transaction_type,
--     merchant_name, merchant_category, channel,
--     transaction_status, is_fraud, balance_after
--   customers (8): first_name, last_name, email, city,
--     date_of_birth, credit_score, customer_since, segment
--   accounts (7): account_type, account_number, balance,
--     currency, opened_date, account_status, account_interest_rate
--   loans (9, LEFT JOIN): loan_id, loan_type, principal,
--     loan_interest_rate, term_months, monthly_payment,
--     loan_outstanding_balance, loan_status, risk_grade
--   fraud_alerts (6, LEFT JOIN): alert_id, alert_date,
--     alert_type, alert_severity, alert_status, amount_at_risk
-- ============================================================

SELECT
    -- ── transactions ─────────────────────────────────────────
    t.transaction_id,
    t.account_id,
    t.customer_id,
    t.transaction_date,
    t.transaction_time,
    t.amount,
    t.transaction_type,
    t.merchant_name,
    t.merchant_category,
    t.channel,
    t.status                                           AS transaction_status,
    t.is_fraud,
    t.balance_after,

    -- ── customers ────────────────────────────────────────────
    c.first_name,
    c.last_name,
    c.email,
    c.city,
    c.date_of_birth,
    c.credit_score,
    c.customer_since,
    c.segment,

    -- ── accounts ─────────────────────────────────────────────
    a.account_type,
    a.account_number,
    a.balance,
    a.currency,
    a.opened_date,
    a.status                                           AS account_status,
    a.interest_rate                                    AS account_interest_rate,

    -- ── loans (LEFT JOIN — may be NULL) ──────────────────────
    l.loan_id,
    l.loan_type,
    l.principal,
    l.interest_rate                                    AS loan_interest_rate,
    l.term_months,
    l.monthly_payment,
    l.outstanding_balance                              AS loan_outstanding_balance,
    l.status                                           AS loan_status,
    l.risk_grade,

    -- ── fraud_alerts (LEFT JOIN — may be NULL) ────────────────
    fa.alert_id,
    fa.alert_date,
    fa.alert_type,
    fa.severity                                        AS alert_severity,
    fa.status                                          AS alert_status,
    fa.amount_at_risk

FROM banking.transactions t

-- Every transaction must have a customer and an account
JOIN banking.customers c   ON t.customer_id     = c.customer_id
JOIN banking.accounts a    ON t.account_id      = a.account_id

-- Not every transaction has a matching loan (customer-level join)
LEFT JOIN banking.loans l  ON t.customer_id     = l.customer_id

-- Not every transaction triggers a fraud alert
LEFT JOIN banking.fraud_alerts fa ON t.transaction_id = fa.transaction_id

ORDER BY t.transaction_date DESC;