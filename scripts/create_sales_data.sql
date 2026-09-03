-- Data Watchdog - Sales Data Table
-- Sample table for testing PostgreSQL monitoring

CREATE TABLE IF NOT EXISTS sales_data (
    id SERIAL PRIMARY KEY,
    customer_id INT,
    product_name VARCHAR(100),
    amount DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample sales data
INSERT INTO sales_data (customer_id, product_name, amount) VALUES
(1, 'Laptop', 1299.99),
(2, 'Mouse', 29.99),
(3, 'Keyboard', 89.99),
(1, 'Monitor', 399.99),
(4, 'USB Cable', 9.99),
(2, 'Headphones', 79.99);

-- Verify insertion
SELECT COUNT(*) as total_rows FROM sales_data;
