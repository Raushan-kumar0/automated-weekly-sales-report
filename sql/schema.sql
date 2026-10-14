-- One row per invoice line from the UCI / Kaggle "Online Retail" dataset (after cleaning).
-- MySQL 8.0+
CREATE TABLE IF NOT EXISTS order_lines (
    line_id      INT AUTO_INCREMENT PRIMARY KEY,
    invoice_no   VARCHAR(10)   NOT NULL,
    line_type    VARCHAR(6)    NOT NULL,          -- 'sale' or 'return' (invoice numbers starting with C)
    invoice_ts   DATETIME      NOT NULL,
    invoice_date DATE          NOT NULL,
    stock_code   VARCHAR(20)   NOT NULL,
    description  VARCHAR(60)   NOT NULL,
    quantity     INT           NOT NULL,          -- negative for returns
    unit_price   DECIMAL(10,2) NOT NULL,
    revenue      DECIMAL(12,2) NOT NULL,          -- quantity x unit_price (negative for returns)
    customer_id  VARCHAR(10)   NULL,              -- missing for about a quarter of lines (guest checkouts)
    country      VARCHAR(30)   NOT NULL,
    INDEX idx_lines_date (invoice_date),
    INDEX idx_lines_type_date (line_type, invoice_date)
);
