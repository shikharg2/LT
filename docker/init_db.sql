-- Database Schema for Speed Test Results
-- This schema stores speed test results from iperf3 tests

-- Create schema if not exists
CREATE SCHEMA IF NOT EXISTS speed_test;

-- Set search path
SET search_path TO speed_test, public;

-- Table for storing test results
CREATE TABLE IF NOT EXISTS test_results (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    scenario_id VARCHAR(255) NOT NULL,
    iteration INTEGER NOT NULL,
    server_type VARCHAR(50) NOT NULL,
    server VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL,
    test_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    mbps DECIMAL(10, 2),
    bits_per_second BIGINT,
    bytes BIGINT,
    retransmits INTEGER,
    jitter_ms DECIMAL(10, 3),
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Table for storing evaluation results
CREATE TABLE IF NOT EXISTS test_evaluations (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    scenario_id VARCHAR(255) NOT NULL,
    iteration INTEGER NOT NULL,
    metric VARCHAR(100) NOT NULL,
    operator VARCHAR(50) NOT NULL,
    expected_value DECIMAL(10, 2),
    actual_value DECIMAL(10, 2),
    unit VARCHAR(50),
    evaluation_scope VARCHAR(50),
    test_index VARCHAR(50),
    passed BOOLEAN NOT NULL,
    verdict VARCHAR(10) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_test_results_timestamp ON test_results(timestamp);
CREATE INDEX IF NOT EXISTS idx_test_results_scenario ON test_results(scenario_id);
CREATE INDEX IF NOT EXISTS idx_test_results_server_type ON test_results(server_type);
CREATE INDEX IF NOT EXISTS idx_test_evaluations_timestamp ON test_evaluations(timestamp);
CREATE INDEX IF NOT EXISTS idx_test_evaluations_scenario ON test_evaluations(scenario_id);
CREATE INDEX IF NOT EXISTS idx_test_evaluations_verdict ON test_evaluations(verdict);

-- Create view for latest test results summary
CREATE OR REPLACE VIEW latest_test_summary AS
SELECT
    scenario_id,
    MAX(timestamp) as last_run,
    COUNT(*) as total_tests,
    AVG(mbps) as avg_mbps,
    MAX(mbps) as max_mbps,
    MIN(mbps) as min_mbps
FROM test_results
WHERE status = 'success'
GROUP BY scenario_id;

-- Create view for evaluation summary
CREATE OR REPLACE VIEW evaluation_summary AS
SELECT
    scenario_id,
    metric,
    COUNT(*) as total_evaluations,
    SUM(CASE WHEN passed THEN 1 ELSE 0 END) as passed_count,
    SUM(CASE WHEN NOT passed THEN 1 ELSE 0 END) as failed_count,
    ROUND(100.0 * SUM(CASE WHEN passed THEN 1 ELSE 0 END) / COUNT(*), 2) as pass_rate
FROM test_evaluations
GROUP BY scenario_id, metric;

-- Grant permissions (adjust as needed)
GRANT ALL PRIVILEGES ON SCHEMA speed_test TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA speed_test TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA speed_test TO postgres;
