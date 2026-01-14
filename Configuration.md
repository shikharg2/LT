# Configuration Guide

Complete guide for configuring the LoadTest Speed Test Framework.

---

## Table of Contents

1. [Configuration File Structure](#configuration-file-structure)
2. [Global Settings](#global-settings)
3. [Scenario Configuration](#scenario-configuration)
4. [Schedule Configuration](#schedule-configuration)
5. [Parameters Configuration](#parameters-configuration)
6. [Expectations Configuration](#expectations-configuration)
7. [Evaluation Scopes](#evaluation-scopes)
8. [Aggregation Methods](#aggregation-methods)
9. [Operators](#operators)
10. [Complete Examples](#complete-examples)

---

## Configuration File Structure

The main configuration file is `configurations/main.json`:

```json
{
  "global_settings": {
    "report_path": "./results/speed_test/",
    "log_level": "INFO"
  },
  "scenarios": [
    {
      "id": "scenario_unique_id",
      "description": "Human-readable description",
      "protocol": "speed_test",
      "enabled": true,
      "schedule": { ... },
      "parameters": { ... },
      "expectations": [ ... ]
    }
  ]
}
```

---

## Global Settings

Controls framework-wide behavior.

### Available Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `report_path` | string | `"./results/speed_test/"` | Directory for CSV reports |
| `log_level` | string | `"INFO"` | Logging verbosity |

### Log Levels

- `DEBUG` - Detailed debugging information
- `INFO` - General informational messages (recommended)
- `WARNING` - Warning messages only
- `ERROR` - Error messages only
- `CRITICAL` - Critical errors only

### Example

```json
{
  "global_settings": {
    "report_path": "/var/log/loadtest/results/",
    "log_level": "DEBUG"
  }
}
```

---

## Scenario Configuration

Each scenario represents a complete test configuration.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier for the scenario |
| `description` | string | Human-readable description |
| `protocol` | string | Must be `"speed_test"` for iperf3 tests |
| `enabled` | boolean | `true` to run, `false` to skip |

### Example

```json
{
  "id": "speed_test_public_server",
  "description": "Test against public iperf3 servers",
  "protocol": "speed_test",
  "enabled": true
}
```

### Best Practices

- Use descriptive IDs (e.g., `speed_test_office_wifi`, `5g_network_test`)
- IDs are used in filenames, so avoid special characters
- Disable scenarios with `"enabled": false` instead of deleting them

---

## Schedule Configuration

Controls when and how often tests run.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | string | Yes | `"once"` or `"recurring"` |
| `start_time` | string | Yes | When to start (see formats below) |
| `duration` | integer | Yes | Test duration in seconds |
| `interval` | integer | No | Time between runs (recurring mode) |
| `unit` | string | No | Time unit: `"minutes"`, `"hours"` |
| `recurring_interval` | integer | No | Alternative: interval in minutes |
| `recurring_times` | integer | No | Number of times to repeat |

### Start Time Formats

| Format | Example | Description |
|--------|---------|-------------|
| Immediate | `"immediate"` | Start right away |
| Relative (minutes) | `"+5m"` | Start in 5 minutes |
| Relative (hours) | `"+2h"` | Start in 2 hours |
| ISO datetime | `"2026-01-15T14:30:00"` | Start at specific time |

### Mode: Once

Run the test a single time.

```json
{
  "schedule": {
    "mode": "once",
    "start_time": "immediate",
    "duration": 10
  }
}
```

### Mode: Recurring

Run the test multiple times with intervals.

```json
{
  "schedule": {
    "mode": "recurring",
    "start_time": "+10m",
    "duration": 5,
    "recurring_interval": 15,
    "recurring_times": 4
  }
}
```

**This will:**
1. Wait 10 minutes
2. Run test (5 seconds per server)
3. Wait 15 minutes
4. Repeat for total of 4 iterations

### Complete Examples

**Run daily at 2 AM:**
```json
{
  "schedule": {
    "mode": "once",
    "start_time": "2026-01-15T02:00:00",
    "duration": 10
  }
}
```

**Run every hour, 10 times:**
```json
{
  "schedule": {
    "mode": "recurring",
    "start_time": "immediate",
    "duration": 5,
    "recurring_interval": 60,
    "recurring_times": 10
  }
}
```

---

## Parameters Configuration

Defines test servers and bandwidth limits.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `private` | array | Private iperf3 servers (internal network) |
| `public` | array | Public iperf3 servers (internet) |
| `uplink` | string | Upload bandwidth limit in Mbps |
| `downlink` | string | Download bandwidth limit in Mbps |

### Server Format

Servers can be specified as:
- `"ip:port"` - e.g., `"192.168.1.1:5201"`
- `"hostname:port"` - e.g., `"iperf.example.com:5201"`
- Default port is `5201` if omitted

### Example

```json
{
  "parameters": {
    "private": [
      "192.168.1.100:5201",
      "10.0.0.50:5201"
    ],
    "public": [
      "speedtest.shinternet.ch:5201",
      "iperf.online.net:5201"
    ],
    "uplink": "50",
    "downlink": "100"
  }
}
```

### Bandwidth Limits

The `uplink` and `downlink` values control iperf3's `-b` parameter:
- Set realistic limits to match your connection
- Values in Mbps (Megabits per second)
- Use `"0"` for unlimited (not recommended)

### Server Selection

**Private Servers:**
- Internal network servers
- Lower latency
- Used for infrastructure testing

**Public Servers:**
- Internet-based servers
- Real-world performance
- Used for ISP/WAN testing

**Public iperf3 Servers:**
- `speedtest.shinternet.ch:5201`
- `iperf.online.net:5201`
- `bouygues.iperf.fr:5201`
- `ping.online.net:5201`

---

## Expectations Configuration

Defines success criteria for tests.

### Structure

```json
{
  "expectations": [
    {
      "metric": "download_speed",
      "operator": "gte",
      "value": 50,
      "unit": "mbps",
      "evaluation_scope": "per_iteration",
      "aggregation": "avg"
    }
  ]
}
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `metric` | string | `"download_speed"` or `"upload_speed"` |
| `operator` | string | Comparison operator (see [Operators](#operators)) |
| `value` | number/array | Expected value or range |
| `unit` | string | Unit of measurement (typically `"mbps"`) |
| `evaluation_scope` | string | When to evaluate (see [Evaluation Scopes](#evaluation-scopes)) |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `aggregation` | string | `"avg"` | How to aggregate values (required for `overall` and `scenario` scopes) |

### Metrics

| Metric | Description | Test Type |
|--------|-------------|-----------|
| `download_speed` | Download throughput in Mbps | Download (iperf3 -R) |
| `upload_speed` | Upload throughput in Mbps | Upload (iperf3) |

---

## Evaluation Scopes

Controls how and when expectations are evaluated.

### 1. per_iteration

**Description:** Each server result is evaluated individually.

**Use Case:** Ensure every server meets the threshold.

**Example:**
```json
{
  "metric": "download_speed",
  "operator": "gte",
  "value": 50,
  "unit": "mbps",
  "evaluation_scope": "per_iteration"
}
```

**Behavior:**
- 3 servers → 3 evaluations
- Each server must pass independently
- Strict requirement

**Output:**
```
Server 1: 45 Mbps → FAIL
Server 2: 65 Mbps → PASS
Server 3: 55 Mbps → PASS
```

### 2. overall

**Description:** All servers in one iteration are aggregated, then evaluated.

**Use Case:** Ensure average/median/percentile performance meets threshold within an iteration.

**Example:**
```json
{
  "metric": "download_speed",
  "operator": "gte",
  "value": 40,
  "unit": "mbps",
  "aggregation": "avg",
  "evaluation_scope": "overall"
}
```

**Behavior:**
- Aggregates all servers in the iteration
- One evaluation per iteration
- Allows some servers to underperform if overall is good

**Output:**
```
Servers: [45, 65, 55]
Average: 55 Mbps → PASS
```

### 3. scenario

**Description:** All results across ALL iterations are aggregated, then evaluated.

**Use Case:** Ensure long-term performance trend meets threshold.

**Example:**
```json
{
  "metric": "download_speed",
  "operator": "gte",
  "value": 30,
  "unit": "mbps",
  "aggregation": "p95",
  "evaluation_scope": "scenario"
}
```

**Behavior:**
- Aggregates across all iterations
- One evaluation per scenario
- Looks at overall scenario performance

**Output:**
```
All iterations (6 results): [45, 65, 55, 50, 60, 40]
P95: 62 Mbps → PASS
```

### Comparison Table

| Scope | Granularity | Aggregation | Evaluations | Output File |
|-------|-------------|-------------|-------------|-------------|
| `per_iteration` | Per server | None | N × servers | `_evaluations.csv` |
| `overall` | Per iteration | Required | N × iterations | `_evaluations.csv` |
| `scenario` | Entire scenario | Required | 1 | `_scenario_summary.csv` |

---

## Aggregation Methods

Methods for combining multiple values into a single metric.

### Available Methods

| Method | Description | Best For |
|--------|-------------|----------|
| `avg` / `mean` | Average of all values | General baseline |
| `median` / `p50` | Middle value | Typical performance |
| `p90` | 90th percentile | Catching most issues |
| `p95` | 95th percentile | SLA compliance |
| `p99` | 99th percentile | Worst-case analysis |
| `min` | Minimum value | Ensuring no stragglers |
| `max` | Maximum value | Peak performance / limits |
| `std_dev` | Standard deviation | Consistency check |
| `variance` | Variance | Statistical spread |
| `sum` | Sum of values | Total throughput |
| `count` | Number of samples | Data validation |

### Usage Examples

**Average Download Speed:**
```json
{
  "metric": "download_speed",
  "aggregation": "avg",
  "operator": "gte",
  "value": 50,
  "evaluation_scope": "overall"
}
```

**95th Percentile (SLA):**
```json
{
  "metric": "download_speed",
  "aggregation": "p95",
  "operator": "gte",
  "value": 40,
  "evaluation_scope": "scenario"
}
```

**Minimum Performance (No Stragglers):**
```json
{
  "metric": "download_speed",
  "aggregation": "min",
  "operator": "gte",
  "value": 20,
  "evaluation_scope": "overall"
}
```

**Maximum Upload (Don't Exceed Limit):**
```json
{
  "metric": "upload_speed",
  "aggregation": "max",
  "operator": "lte",
  "value": 100,
  "evaluation_scope": "scenario"
}
```

### Percentile Interpretation

```
p50 (median): 50% of values are below this
p90: 90% of values are below this
p95: 95% of values are below this (common SLA threshold)
p99: 99% of values are below this (catch outliers)
```

---

## Operators

Comparison operators for evaluating expectations.

### Supported Operators

| Operator | Symbol | Description | Example |
|----------|--------|-------------|---------|
| `gte` | `>=` | Greater than or equal | `speed gte 50` |
| `lte` | `<=` | Less than or equal | `latency lte 100` |
| `gt` | `>` | Greater than | `bandwidth gt 10` |
| `lt` | `<` | Less than | `jitter lt 30` |
| `eq` | `==` | Equal to | `status eq 200` |
| `neq` | `!=` | Not equal to | `errors neq 0` |
| `between` | `x < y < z` | Inside range (exclusive) | `speed between [40, 60]` |

### Usage Examples

**Greater Than or Equal:**
```json
{
  "operator": "gte",
  "value": 50
}
// Passes if: actual >= 50
```

**Less Than or Equal:**
```json
{
  "operator": "lte",
  "value": 10
}
// Passes if: actual <= 10
```

**Between (Range):**
```json
{
  "operator": "between",
  "value": [40, 60]
}
// Passes if: 40 < actual < 60
// Note: Exclusive boundaries
```

### Common Patterns

**Download should be fast:**
```json
{
  "metric": "download_speed",
  "operator": "gte",
  "value": 50
}
```

**Upload should not exceed cap:**
```json
{
  "metric": "upload_speed",
  "operator": "lte",
  "value": 10
}
```

**Speed within acceptable range:**
```json
{
  "metric": "download_speed",
  "operator": "between",
  "value": [40, 100]
}
```

---

## Complete Examples

### Example 1: Simple Single Test

Test once against public servers, immediate start.

```json
{
  "global_settings": {
    "report_path": "./results/simple_test/",
    "log_level": "INFO"
  },
  "scenarios": [
    {
      "id": "quick_speed_test",
      "description": "Quick speed test against public servers",
      "protocol": "speed_test",
      "enabled": true,

      "schedule": {
        "mode": "once",
        "start_time": "immediate",
        "duration": 5
      },

      "parameters": {
        "private": [],
        "public": [
          "speedtest.shinternet.ch:5201",
          "iperf.online.net:5201"
        ],
        "uplink": "50",
        "downlink": "100"
      },

      "expectations": [
        {
          "metric": "download_speed",
          "operator": "gte",
          "value": 50,
          "unit": "mbps",
          "evaluation_scope": "per_iteration"
        }
      ]
    }
  ]
}
```

### Example 2: Comprehensive Testing

Multiple evaluation scopes with various aggregations.

```json
{
  "global_settings": {
    "report_path": "./results/comprehensive/",
    "log_level": "INFO"
  },
  "scenarios": [
    {
      "id": "full_network_test",
      "description": "Comprehensive network performance test",
      "protocol": "speed_test",
      "enabled": true,

      "schedule": {
        "mode": "recurring",
        "start_time": "+5m",
        "duration": 10,
        "recurring_interval": 30,
        "recurring_times": 3
      },

      "parameters": {
        "private": [
          "192.168.1.100:5201",
          "10.0.0.50:5201"
        ],
        "public": [
          "speedtest.shinternet.ch:5201",
          "iperf.online.net:5201"
        ],
        "uplink": "50",
        "downlink": "100"
      },

      "expectations": [
        {
          "_comment": "Each server must exceed 40 Mbps",
          "metric": "download_speed",
          "operator": "gte",
          "value": 40,
          "unit": "mbps",
          "evaluation_scope": "per_iteration"
        },
        {
          "_comment": "Average across servers per iteration >= 50 Mbps",
          "metric": "download_speed",
          "operator": "gte",
          "value": 50,
          "unit": "mbps",
          "aggregation": "avg",
          "evaluation_scope": "overall"
        },
        {
          "_comment": "95th percentile across iterations >= 45 Mbps",
          "metric": "download_speed",
          "operator": "gte",
          "value": 45,
          "unit": "mbps",
          "aggregation": "p95",
          "evaluation_scope": "scenario"
        },
        {
          "_comment": "No upload should exceed 60 Mbps",
          "metric": "upload_speed",
          "operator": "lte",
          "value": 60,
          "unit": "mbps",
          "evaluation_scope": "per_iteration"
        },
        {
          "_comment": "Average upload across entire scenario <= 50 Mbps",
          "metric": "upload_speed",
          "operator": "lte",
          "value": 50,
          "unit": "mbps",
          "aggregation": "avg",
          "evaluation_scope": "scenario"
        }
      ]
    }
  ]
}
```

### Example 3: All Aggregation Methods

Testing all available aggregation methods.

```json
{
  "scenarios": [
    {
      "id": "aggregation_showcase",
      "description": "Demonstrates all aggregation methods",
      "protocol": "speed_test",
      "enabled": true,

      "schedule": {
        "mode": "once",
        "start_time": "immediate",
        "duration": 5
      },

      "parameters": {
        "public": ["speedtest.shinternet.ch:5201"],
        "uplink": "10",
        "downlink": "100"
      },

      "expectations": [
        {
          "metric": "download_speed",
          "aggregation": "avg",
          "operator": "gte",
          "value": 50,
          "unit": "mbps",
          "evaluation_scope": "scenario"
        },
        {
          "metric": "download_speed",
          "aggregation": "median",
          "operator": "gte",
          "value": 45,
          "unit": "mbps",
          "evaluation_scope": "scenario"
        },
        {
          "metric": "download_speed",
          "aggregation": "p90",
          "operator": "gte",
          "value": 55,
          "unit": "mbps",
          "evaluation_scope": "scenario"
        },
        {
          "metric": "download_speed",
          "aggregation": "p95",
          "operator": "gte",
          "value": 60,
          "unit": "mbps",
          "evaluation_scope": "scenario"
        },
        {
          "metric": "download_speed",
          "aggregation": "p99",
          "operator": "gte",
          "value": 70,
          "unit": "mbps",
          "evaluation_scope": "scenario"
        },
        {
          "metric": "download_speed",
          "aggregation": "min",
          "operator": "gte",
          "value": 30,
          "unit": "mbps",
          "evaluation_scope": "scenario"
        },
        {
          "metric": "download_speed",
          "aggregation": "max",
          "operator": "lte",
          "value": 100,
          "unit": "mbps",
          "evaluation_scope": "scenario"
        }
      ]
    }
  ]
}
```

### Example 4: SLA Compliance Testing

Real-world SLA monitoring setup.

```json
{
  "scenarios": [
    {
      "id": "sla_monitoring",
      "description": "Monitor ISP SLA compliance",
      "protocol": "speed_test",
      "enabled": true,

      "schedule": {
        "mode": "recurring",
        "start_time": "immediate",
        "duration": 10,
        "recurring_interval": 60,
        "recurring_times": 24
      },

      "parameters": {
        "public": [
          "speedtest.shinternet.ch:5201",
          "iperf.online.net:5201",
          "bouygues.iperf.fr:5201"
        ],
        "uplink": "100",
        "downlink": "500"
      },

      "expectations": [
        {
          "_comment": "SLA: 95% of tests must exceed 400 Mbps download",
          "metric": "download_speed",
          "aggregation": "p95",
          "operator": "gte",
          "value": 400,
          "unit": "mbps",
          "evaluation_scope": "scenario"
        },
        {
          "_comment": "SLA: Average download >= 450 Mbps",
          "metric": "download_speed",
          "aggregation": "avg",
          "operator": "gte",
          "value": 450,
          "unit": "mbps",
          "evaluation_scope": "scenario"
        },
        {
          "_comment": "SLA: Minimum download >= 300 Mbps",
          "metric": "download_speed",
          "aggregation": "min",
          "operator": "gte",
          "value": 300,
          "unit": "mbps",
          "evaluation_scope": "scenario"
        },
        {
          "_comment": "SLA: 95% of uploads must exceed 80 Mbps",
          "metric": "upload_speed",
          "aggregation": "p95",
          "operator": "gte",
          "value": 80,
          "unit": "mbps",
          "evaluation_scope": "scenario"
        }
      ]
    }
  ]
}
```

---

## Configuration Validation

### Common Mistakes

**Missing Required Fields:**
```json
// ❌ WRONG - missing evaluation_scope
{
  "metric": "download_speed",
  "operator": "gte",
  "value": 50
}

// ✓ CORRECT
{
  "metric": "download_speed",
  "operator": "gte",
  "value": 50,
  "unit": "mbps",
  "evaluation_scope": "per_iteration"
}
```

**Missing Aggregation for Overall/Scenario:**
```json
// ❌ WRONG - aggregation required for overall scope
{
  "metric": "download_speed",
  "operator": "gte",
  "value": 50,
  "evaluation_scope": "overall"
}

// ✓ CORRECT
{
  "metric": "download_speed",
  "operator": "gte",
  "value": 50,
  "aggregation": "avg",
  "evaluation_scope": "overall"
}
```

**Invalid Server Format:**
```json
// ❌ WRONG
"public": "speedtest.shinternet.ch:5201"

// ✓ CORRECT (must be array)
"public": ["speedtest.shinternet.ch:5201"]
```

**Invalid Between Operator:**
```json
// ❌ WRONG - between needs array of 2 values
{
  "operator": "between",
  "value": 50
}

// ✓ CORRECT
{
  "operator": "between",
  "value": [40, 60]
}
```

---

## Environment Variables

Override database connection settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `speedtest` | Database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASSWORD` | `postgres` | Database password |

**Example:**
```bash
export DB_HOST=db-container
export DB_PORT=5432
python3 src/test_protocols/iperf/new_speed_test.py
```

---

## Best Practices

### 1. Start Simple
```json
// Begin with basic expectations
{
  "expectations": [
    {
      "metric": "download_speed",
      "operator": "gte",
      "value": 50,
      "unit": "mbps",
      "evaluation_scope": "per_iteration"
    }
  ]
}
```

### 2. Add Progressively
```json
// Add overall scope
{
  "metric": "download_speed",
  "aggregation": "avg",
  "operator": "gte",
  "value": 60,
  "evaluation_scope": "overall"
}
```

### 3. Monitor Long-Term
```json
// Add scenario scope for trends
{
  "metric": "download_speed",
  "aggregation": "p95",
  "operator": "gte",
  "value": 55,
  "evaluation_scope": "scenario"
}
```

### 4. Use Comments
```json
{
  "_comment": "SLA requirement: 95% above 50 Mbps",
  "metric": "download_speed",
  "aggregation": "p95",
  "operator": "gte",
  "value": 50
}
```

### 5. Test Incrementally

1. Start with 1 server, `mode: "once"`
2. Verify results in CSV files
3. Add more servers
4. Switch to `mode: "recurring"`
5. Add more expectations

---

## Troubleshooting

### No Results in Database

**Check:**
- Database connection (DB_HOST environment variable)
- PostgreSQL service is running
- Credentials are correct

### Tests Always Fail

**Check:**
- Servers are reachable (`ping` test)
- iperf3 is running on servers (`iperf3 -s` on server side)
- Bandwidth limits are realistic

### Wrong Aggregation Results

**Check:**
- Only `success` status results are included
- Failed tests are excluded from scenario aggregation
- Check `{scenario}_aggregation_metrics.csv` for all computed values

---

## Quick Reference

### Minimal Configuration

```json
{
  "global_settings": {
    "report_path": "./results/speed_test/",
    "log_level": "INFO"
  },
  "scenarios": [
    {
      "id": "test",
      "protocol": "speed_test",
      "enabled": true,
      "schedule": {
        "mode": "once",
        "start_time": "immediate",
        "duration": 5
      },
      "parameters": {
        "public": ["speedtest.shinternet.ch:5201"],
        "uplink": "10",
        "downlink": "100"
      },
      "expectations": [
        {
          "metric": "download_speed",
          "operator": "gte",
          "value": 10,
          "unit": "mbps",
          "evaluation_scope": "per_iteration"
        }
      ]
    }
  ]
}
```

### All Available Aggregations

- avg / mean
- median / p50
- p90, p95, p99
- min, max
- std_dev, variance
- sum, count

### All Available Operators

- gte (>=), lte (<=)
- gt (>), lt (<)
- eq (==), neq (!=)
- between

### All Evaluation Scopes

- per_iteration (each server)
- overall (per iteration aggregate)
- scenario (all iterations aggregate)

---

This completes the configuration guide. For system architecture details, see [SpeedTest.md](SpeedTest.md).
