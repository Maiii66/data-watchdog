-- Data Watchdog - Test Database Schema & Seed Data
-- Creates an orders table with realistic data including
-- quality issues for the watchdog to detect.

CREATE TABLE IF NOT EXISTS orders (
    order_id    VARCHAR(20) PRIMARY KEY,
    customer    VARCHAR(100) NOT NULL,
    amount      NUMERIC(10, 2),
    status      VARCHAR(20) NOT NULL,
    city        VARCHAR(100),
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Insert 200 clean orders
INSERT INTO orders (order_id, customer, amount, status, city, created_at)
SELECT
    'ORD' || LPAD(i::TEXT, 4, '0'),
    (ARRAY['Alice','Bob','Charlie','Diana','Eve','Frank','Grace','Hank'])[1 + (i % 8)],
    ROUND((random() * 500 + 10)::NUMERIC, 2),
    (ARRAY['completed','pending','cancelled','returned'])[1 + (i % 4)],
    (ARRAY['New York','London','Tokyo','Berlin','Sydney','Mumbai','Toronto','Paris'])[1 + (i % 8)],
    NOW() - (random() * INTERVAL '30 days')
FROM generate_series(1, 200) AS i;

-- Insert 5 orders with NULL amounts (quality issue: null spike)
INSERT INTO orders (order_id, customer, amount, status, city, created_at) VALUES
    ('ORD0201', 'Zara',   NULL, 'pending',   'Berlin',   NOW() - INTERVAL '1 day'),
    ('ORD0202', 'Yusuf',  NULL, 'completed', 'Tokyo',    NOW() - INTERVAL '1 day'),
    ('ORD0203', 'Xena',   NULL, 'cancelled', 'Sydney',   NOW() - INTERVAL '1 day'),
    ('ORD0204', 'Walter', NULL, 'returned',  'Mumbai',   NOW() - INTERVAL '1 day'),
    ('ORD0205', 'Vera',   NULL, 'pending',   'Toronto',  NOW() - INTERVAL '1 day');
