-- Create the holiday-import table in BigQuery
-- Run this in your BigQuery console for your development project

-- Create dataset if it doesn't exist
CREATE SCHEMA IF NOT EXISTS `shared_activities`;

-- Create the holiday table
CREATE OR REPLACE TABLE `shared_activities.holiday-import` (
    description STRING,
    start_date DATE,
    end_date DATE,
    region STRING
);

-- Insert sample holiday data
INSERT INTO `shared_activities.holiday-import` (description, start_date, end_date, region)
VALUES
    -- US Holidays
    ('New Year''s Day', '2024-01-01', '2024-01-01', 'US'),
    ('Martin Luther King Jr. Day', '2024-01-15', '2024-01-15', 'US'),
    ('Presidents Day', '2024-02-19', '2024-02-19', 'US'),
    ('Memorial Day', '2024-05-27', '2024-05-27', 'US'),
    ('Independence Day', '2024-07-04', '2024-07-04', 'US'),
    ('Labor Day', '2024-09-02', '2024-09-02', 'US'),
    ('Thanksgiving', '2024-11-28', '2024-11-28', 'US'),
    ('Christmas Day', '2024-12-25', '2024-12-25', 'US'),
    
    -- Canada Holidays
    ('New Year''s Day', '2024-01-01', '2024-01-01', 'CA'),
    ('Family Day', '2024-02-19', '2024-02-19', 'CA'),
    ('Good Friday', '2024-03-29', '2024-03-29', 'CA'),
    ('Victoria Day', '2024-05-20', '2024-05-20', 'CA'),
    ('Canada Day', '2024-07-01', '2024-07-01', 'CA'),
    ('Labour Day', '2024-09-02', '2024-09-02', 'CA'),
    ('Thanksgiving', '2024-10-14', '2024-10-14', 'CA'),
    ('Christmas Day', '2024-12-25', '2024-12-25', 'CA'),
    
    -- Australia Holidays
    ('New Year''s Day', '2024-01-01', '2024-01-01', 'AU'),
    ('Australia Day', '2024-01-26', '2024-01-26', 'AU'),
    ('Good Friday', '2024-03-29', '2024-03-29', 'AU'),
    ('Easter Monday', '2024-04-01', '2024-04-01', 'AU'),
    ('ANZAC Day', '2024-04-25', '2024-04-25', 'AU'),
    ('Queen''s Birthday', '2024-06-10', '2024-06-10', 'AU'),
    ('Christmas Day', '2024-12-25', '2024-12-25', 'AU'),
    ('Boxing Day', '2024-12-26', '2024-12-26', 'AU'),
    
    -- UK Holidays
    ('New Year''s Day', '2024-01-01', '2024-01-01', 'UK'),
    ('Good Friday', '2024-03-29', '2024-03-29', 'UK'),
    ('Easter Monday', '2024-04-01', '2024-04-01', 'UK'),
    ('Early May Bank Holiday', '2024-05-06', '2024-05-06', 'UK'),
    ('Spring Bank Holiday', '2024-05-27', '2024-05-27', 'UK'),
    ('Summer Bank Holiday', '2024-08-26', '2024-08-26', 'UK'),
    ('Christmas Day', '2024-12-25', '2024-12-25', 'UK'),
    ('Boxing Day', '2024-12-26', '2024-12-26', 'UK');

-- Verify the data
SELECT region, COUNT(*) as holiday_count
FROM `shared_activities.holiday-import`
GROUP BY region
ORDER BY region;