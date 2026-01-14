# Speed Test Framework - System Architecture

## Overview

The Speed Test Framework is a containerized network performance testing system that uses iperf3 to measure upload/download speeds against multiple servers, evaluates results against expectations, and stores data in PostgreSQL.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         LoadTest Framework                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Orchestration Layer                           │   │
│  │                    (orchestrate.py)                              │   │
│  └────────────────────────┬─────────────────────────────────────────┘   │
│                           │                                              │
│                           ├─── 1. Read main.json configuration          │
│                           ├─── 2. Initialize Docker Swarm               │
│                           ├─── 3. Deploy services                        │
│                           ├─── 4. Run tests                              │
│                           └─── 5. Export results                         │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    Docker Swarm Cluster                         │    │
│  │  ┌────────────────────────────────────────────────────────────┐ │    │
│  │  │         loadtest_network (overlay network)                 │ │    │
│  │  │                                                             │ │    │
│  │  │  ┌──────────────────────┐    ┌────────────────────────┐   │ │    │
│  │  │  │  test-container      │    │   db-container         │   │ │    │
│  │  │  │  ─────────────────   │    │   ──────────────       │   │ │    │
│  │  │  │                      │    │                        │   │ │    │
│  │  │  │  new_speed_test.py   │◄───┤   PostgreSQL 15       │   │ │    │
│  │  │  │                      │    │                        │   │ │    │
│  │  │  │  ┌────────────────┐ │    │   Database: speedtest  │   │ │    │
│  │  │  │  │ iperf3 tests   │ │    │                        │   │ │    │
│  │  │  │  │ - Download     │ │    │   Tables:              │   │ │    │
│  │  │  │  │ - Upload       │ │    │   - test_results       │   │ │    │
│  │  │  │  └────────────────┘ │    │   - test_evaluations   │   │ │    │
│  │  │  │                      │    │                        │   │ │    │
│  │  │  │  ┌────────────────┐ │    │   Views:               │   │ │    │
│  │  │  │  │ Evaluations    │ │───►│   - latest_test_summary│   │ │    │
│  │  │  │  │ - per_iteration│ │    │   - evaluation_summary │   │ │    │
│  │  │  │  │ - overall      │ │    │                        │   │ │    │
│  │  │  │  │ - scenario     │ │    │   Port: 5432           │   │ │    │
│  │  │  │  └────────────────┘ │    │                        │   │ │    │
│  │  │  │                      │    └────────────────────────┘   │ │    │
│  │  │  │  Volume Mounts:      │                                 │ │    │
│  │  │  │  - src/              │                                 │ │    │
│  │  │  │  - configurations/   │                                 │ │    │
│  │  │  │  - results/          │                                 │ │    │
│  │  │  └──────────────────────┘                                 │ │    │
│  │  └─────────────────────────────────────────────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Test Execution Flow                              │
└─────────────────────────────────────────────────────────────────────────┘

1. CONFIGURATION LOADING
   ┌─────────────────┐
   │  main.json      │
   │  ─────────────  │
   │  - scenarios    │
   │  - parameters   │
   │  - expectations │
   └────────┬────────┘
            │
            ▼
2. SCENARIO EXECUTION
   ┌─────────────────────────────────────────────────────┐
   │  For each enabled scenario:                         │
   │                                                      │
   │  ┌──────────────────────────────────────────────┐  │
   │  │  Iteration Loop (1 to N)                     │  │
   │  │                                               │  │
   │  │  ┌─────────────────────────────────────────┐ │  │
   │  │  │  For each server (private + public):    │ │  │
   │  │  │                                          │ │  │
   │  │  │  ┌────────────────────────────────┐    │ │  │
   │  │  │  │  Upload Test (iperf3)          │    │ │  │
   │  │  │  │  - Duration: 5-10s             │    │ │  │
   │  │  │  │  - Bandwidth limit: uplink     │    │ │  │
   │  │  │  │  - Result: Mbps, retransmits   │    │ │  │
   │  │  │  └────────────────────────────────┘    │ │  │
   │  │  │                                          │ │  │
   │  │  │  ┌────────────────────────────────┐    │ │  │
   │  │  │  │  Download Test (iperf3 -R)     │    │ │  │
   │  │  │  │  - Duration: 5-10s             │    │ │  │
   │  │  │  │  - Bandwidth limit: downlink   │    │ │  │
   │  │  │  │  - Result: Mbps, jitter        │    │ │  │
   │  │  │  └────────────────────────────────┘    │ │  │
   │  │  └─────────────────────────────────────────┘ │  │
   │  └──────────────────────────────────────────────┘  │
   └─────────────────────────────────────────────────────┘
            │
            ▼
3. EVALUATION (Three Levels)
   ┌──────────────────────────────────────────────────────┐
   │  Level 1: PER_ITERATION                              │
   │  Each server result evaluated individually           │
   │  Output: {scenario}_evaluations.csv                  │
   └──────────────────────────────────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────────────────────┐
   │  Level 2: OVERALL (per iteration)                    │
   │  All servers aggregated within one iteration         │
   │  Methods: avg, median, p90, p95, min, max            │
   │  Output: {scenario}_evaluations.csv                  │
   └──────────────────────────────────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────────────────────┐
   │  Level 3: SCENARIO (all iterations)                  │
   │  All results across all iterations aggregated        │
   │  Methods: avg, median, p90, p95, p99, min, max       │
   │  Output: {scenario}_scenario_summary.csv             │
   └──────────────────────────────────────────────────────┘
            │
            ▼
4. DATA PERSISTENCE
   ┌──────────────────────────────────────────────────────┐
   │  PostgreSQL Database                                 │
   │  - speed_test.test_results                           │
   │  - speed_test.test_evaluations                       │
   └──────────────────────────────────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────────────────────┐
   │  CSV Files (./results/speed_test/)                   │
   │  - {scenario}_evaluations.csv                        │
   │  - {scenario}_scenario_summary.csv                   │
   │  - {scenario}_aggregation_metrics.csv                │
   │  - speed_test_results_{timestamp}.csv                │
   └──────────────────────────────────────────────────────┘
```

---

## Evaluation Scopes Explained

### 1. Per-Iteration Scope

**Purpose:** Ensure every single server meets the requirement.

```
Scenario: speed_test_public_server
Servers: [server1, server2, server3]
Iteration: 1

Test Results:
  server1: 45 Mbps (download)
  server2: 65 Mbps (download)
  server3: 55 Mbps (download)

Expectation: download_speed >= 50 Mbps

Evaluation:
  ┌─────────┬──────────┬──────────┐
  │ Server  │ Result   │ Verdict  │
  ├─────────┼──────────┼──────────┤
  │ server1 │ 45 Mbps  │ FAIL ❌  │
  │ server2 │ 65 Mbps  │ PASS ✓   │
  │ server3 │ 55 Mbps  │ PASS ✓   │
  └─────────┴──────────┴──────────┘

Result: 3 evaluations (1 per server)
```

### 2. Overall Scope

**Purpose:** Ensure the aggregated performance across servers in one iteration meets requirements.

```
Scenario: speed_test_public_server
Servers: [server1, server2, server3]
Iteration: 1

Test Results:
  server1: 45 Mbps
  server2: 65 Mbps
  server3: 55 Mbps

Expectation:
  - download_speed >= 50 Mbps (aggregation: avg)

Evaluation:
  Average = (45 + 65 + 55) / 3 = 55 Mbps
  55 >= 50 → PASS ✓

Result: 1 evaluation (aggregated value)
```

### 3. Scenario Scope

**Purpose:** Ensure performance across ALL iterations of the scenario meets requirements.

```
Scenario: speed_test_public_server
Mode: recurring (3 iterations)
Servers: [server1, server2] per iteration

All Test Results:
  Iteration 1:
    server1: 45 Mbps, server2: 55 Mbps
  Iteration 2:
    server1: 50 Mbps, server2: 60 Mbps
  Iteration 3:
    server1: 40 Mbps, server2: 50 Mbps

Expectation:
  - download_speed >= 48 Mbps (aggregation: avg, scope: scenario)

Evaluation:
  All values: [45, 55, 50, 60, 40, 50]
  Average = 50 Mbps
  50 >= 48 → PASS ✓

Result: 1 evaluation (entire scenario)
```

---

## Aggregation Methods

The framework supports multiple aggregation methods from `src/utils/aggregation.py`:

| Method | Description | Use Case |
|--------|-------------|----------|
| `avg` / `mean` | Average of all values | General performance baseline |
| `median` | Middle value | Resistant to outliers |
| `p50` | 50th percentile | Same as median |
| `p90` | 90th percentile | Catches most issues |
| `p95` | 95th percentile | SLA compliance |
| `p99` | 99th percentile | Worst-case performance |
| `min` | Minimum value | Ensure no server is too slow |
| `max` | Maximum value | Ensure no server exceeds limit |
| `std_dev` | Standard deviation | Measure consistency |
| `variance` | Variance | Statistical analysis |
| `sum` | Sum of all values | Total throughput |
| `count` | Number of samples | Sample size validation |

---

## Database Schema

```sql
-- Test Results Table
CREATE TABLE speed_test.test_results (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP,
    scenario_id VARCHAR(255),      -- e.g., "speed_test_public_server"
    iteration INTEGER,              -- 1, 2, 3, ...
    server_type VARCHAR(50),        -- "private" or "public"
    server VARCHAR(255),            -- e.g., "192.168.1.1"
    port INTEGER,                   -- e.g., 5201
    test_type VARCHAR(50),          -- "upload" or "download"
    status VARCHAR(50),             -- "success", "failed", "timeout"
    mbps DECIMAL(10, 2),            -- Speed in Mbps
    bits_per_second BIGINT,         -- Raw bits/sec
    bytes BIGINT,                   -- Total bytes transferred
    retransmits INTEGER,            -- TCP retransmits (upload only)
    jitter_ms DECIMAL(10, 3),       -- Jitter (download only)
    error_message TEXT,             -- Error details if failed
    created_at TIMESTAMP
);

-- Evaluations Table
CREATE TABLE speed_test.test_evaluations (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP,
    scenario_id VARCHAR(255),
    iteration INTEGER,              -- "all" for scenario scope
    metric VARCHAR(100),            -- "download_speed", "upload_speed"
    operator VARCHAR(50),           -- "gte", "lte", "between", etc.
    expected_value DECIMAL(10, 2),  -- Threshold value
    actual_value DECIMAL(10, 2),    -- Measured value
    unit VARCHAR(50),               -- "mbps"
    evaluation_scope VARCHAR(50),   -- "per_iteration", "overall", "scenario"
    test_index VARCHAR(50),         -- Server index or "all"/"scenario"
    passed BOOLEAN,                 -- True/False
    verdict VARCHAR(10),            -- "PASS" or "FAIL"
    created_at TIMESTAMP
);
```

---

## Output Files

### 1. Per-Iteration and Overall Evaluations
**File:** `{scenario_id}_evaluations.csv`

Contains results from:
- `per_iteration` scope: One row per server
- `overall` scope: One row per iteration with aggregated value

**Columns:**
```
iteration, metric, operator, expected_value, actual_value, unit,
evaluation_scope, aggregation, test_index, passed, verdict, scenario_id
```

### 2. Scenario Summary
**File:** `{scenario_id}_scenario_summary.csv`

Contains scenario-level evaluations across all iterations.

**Columns:**
```
scenario_id, timestamp, metric, aggregation, actual_value,
operator, expected_value, unit, sample_count, passed, verdict
```

### 3. Aggregation Metrics
**File:** `{scenario_id}_aggregation_metrics.csv`

Contains ALL aggregation methods computed for the scenario.

**Columns:**
```
scenario_id, timestamp, metric, aggregation, value, unit
```

**Example:**
```csv
scenario_id,timestamp,metric,aggregation,value,unit
speed_test_public_server,2026-01-14T10:30:00,download_speed,avg,52.5,mbps
speed_test_public_server,2026-01-14T10:30:00,download_speed,median,50.0,mbps
speed_test_public_server,2026-01-14T10:30:00,download_speed,p90,68.0,mbps
speed_test_public_server,2026-01-14T10:30:00,download_speed,p95,72.0,mbps
speed_test_public_server,2026-01-14T10:30:00,download_speed,p99,80.0,mbps
speed_test_public_server,2026-01-14T10:30:00,download_speed,min,30.0,mbps
speed_test_public_server,2026-01-14T10:30:00,download_speed,max,85.0,mbps
speed_test_public_server,2026-01-14T10:30:00,download_speed,std_dev,15.2,mbps
speed_test_public_server,2026-01-14T10:30:00,download_speed,count,12,samples
```

### 4. Raw Test Results
**File:** `speed_test_results_{timestamp}.csv`

Contains all raw iperf3 test results.

**Columns:**
```
timestamp, scenario_id, iteration, server_type, server, port,
test_type, status, mbps, bits_per_second, bytes,
retransmits, jitter_ms, error
```

---

## Scheduling System

The framework supports flexible scheduling:

```
Start Time Formats:
  - "immediate"              → Start now
  - "+5m"                    → Start in 5 minutes
  - "+2h"                    → Start in 2 hours
  - "2026-01-15T14:30:00"    → Start at specific time

Execution Modes:
  - "once"       → Run one time
  - "recurring"  → Run multiple times with intervals

Example:
{
  "schedule": {
    "mode": "recurring",
    "start_time": "+10m",
    "duration": 5,
    "recurring_interval": 15,
    "recurring_times": 4
  }
}

This will:
  1. Wait 10 minutes
  2. Run test (5 seconds per server)
  3. Wait 15 minutes
  4. Repeat 4 times total
```

---

## Operators Supported

All comparison operators from `src/utils/operator.py`:

| Operator | Symbol | Description | Example |
|----------|--------|-------------|---------|
| `eq` | `==` | Equal to | `value eq 100` |
| `neq` | `!=` | Not equal to | `errors neq 0` |
| `lt` | `<` | Less than | `jitter lt 30` |
| `lte` | `<=` | Less than or equal | `upload lte 10` |
| `gt` | `>` | Greater than | `download gt 50` |
| `gte` | `>=` | Greater than or equal | `speed gte 100` |
| `between` | `min < x < max` | Inside range | `speed between [50, 100]` |

---

## Usage Examples

### Running Tests

```bash
# Using orchestrate.py (recommended)
python3 orchestrate.py

# Manual execution (inside container)
python3 src/test_protocols/iperf/new_speed_test.py

# With custom config
python3 src/test_protocols/iperf/new_speed_test.py --config path/to/config.json
```

### Querying Results

```bash
# Latest test summary
docker exec loadtest_db psql -U postgres -d speedtest -c \
  "SELECT * FROM speed_test.latest_test_summary;"

# Evaluation summary
docker exec loadtest_db psql -U postgres -d speedtest -c \
  "SELECT * FROM speed_test.evaluation_summary;"

# Failed evaluations
docker exec loadtest_db psql -U postgres -d speedtest -c \
  "SELECT * FROM speed_test.test_evaluations WHERE verdict='FAIL';"
```

---

## Error Handling

The framework handles various error scenarios:

```
┌─────────────────────────────────────────────────────┐
│  Error Type          │  Status       │  Handling   │
├──────────────────────┼───────────────┼─────────────┤
│  Server unreachable  │  "failed"     │  Record 0   │
│  Test timeout        │  "timeout"    │  Record 0   │
│  JSON parse error    │  "parse_error"│  Record 0   │
│  Database error      │  N/A          │  Log only   │
│  Network error       │  "error"      │  Record 0   │
└─────────────────────────────────────────────────────┘

Note: Failed tests are excluded from scenario evaluations
      (only 'success' status results are aggregated)
```

---

## Performance Considerations

- **Parallel Testing:** Servers tested sequentially to avoid network contention
- **Database Writes:** Batched per iteration for efficiency
- **CSV Files:** Appended incrementally to avoid memory issues
- **Container Resources:** Test container removed after completion (--rm flag)
- **Network Overhead:** Overlay network adds ~1-2ms latency

---

## File Structure

```
LoadTest/
├── orchestrate.py                          # Main orchestration script
├── configurations/
│   └── main.json                           # Test configuration
├── src/
│   ├── test_protocols/
│   │   └── iperf/
│   │       └── new_speed_test.py          # Test runner
│   └── utils/
│       ├── aggregation.py                  # Aggregation methods
│       └── operator.py                     # Comparison operators
├── docker/
│   ├── Dockerfile                          # Test container image
│   ├── Dockerfile.postgres                 # DB container image
│   └── init_db.sql                         # Database schema
├── results/
│   └── speed_test/                         # Output directory
│       ├── {scenario}_evaluations.csv
│       ├── {scenario}_scenario_summary.csv
│       ├── {scenario}_aggregation_metrics.csv
│       └── speed_test_results_{ts}.csv
└── requirements.txt                        # Python dependencies
```

---

## Summary

The Speed Test Framework provides:

✓ **Multi-server testing** against private and public iperf3 servers
✓ **Three evaluation levels** for granular performance validation
✓ **10+ aggregation methods** for statistical analysis
✓ **Flexible scheduling** with multiple execution modes
✓ **Persistent storage** in PostgreSQL with CSV exports
✓ **Docker Swarm orchestration** for scalability
✓ **Comprehensive reporting** with multiple output formats

The system is designed for reliability, scalability, and ease of use in network performance testing scenarios.
