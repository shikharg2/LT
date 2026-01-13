# Load Test Utilities

## Cron Scheduler

The Cron Scheduler module allows you to schedule load tests at specific times using standard cron expressions.

### Features

- **Standard Cron Syntax**: Use familiar cron expressions to schedule tests
- **Multiple Concurrent Jobs**: Run different test scenarios on different schedules
- **Graceful Shutdown**: Handles interrupts cleanly without corrupting tests
- **Detailed Logging**: Tracks all scheduled executions with timestamps
- **Protocol Support**: Works with speed_test, voip_test, and other protocols
- **Status Monitoring**: View current schedule status and run history

### Installation

Install required dependencies:

```bash
pip install croniter
```

### Configuration

Add a cron schedule to your scenario in `configurations/main.json`:

```json
{
  "global_settings": {
    "report_path": "./results/speed_test/",
    "log_level": "INFO"
  },
  "scenarios": [
    {
      "id": "daily_speed_test",
      "description": "Run speed test every day at 9 AM",
      "protocol": "speed_test",
      "enabled": true,

      "schedule": {
        "mode": "cron",
        "cron_expression": "0 9 * * *",
        "timezone": "local"
      },

      "parameters": {
        "public": ["speedtest.shinternet.ch:5201"],
        "duration": 10,
        "uplink": "10",
        "downlink": "100"
      },

      "expectations": [
        {
          "metric": "download_speed",
          "operator": "gte",
          "value": 50,
          "unit": "mbps"
        }
      ]
    }
  ]
}
```

### Cron Expression Format

Cron expressions consist of 5 fields:

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday to Saturday)
│ │ │ │ │
│ │ │ │ │
* * * * *
```

### Common Examples

| Expression | Description |
|------------|-------------|
| `0 9 * * *` | Every day at 9:00 AM |
| `0 */2 * * *` | Every 2 hours |
| `0 0 * * 0` | Every Sunday at midnight |
| `30 8 * * 1-5` | Weekdays at 8:30 AM |
| `0 0 1 * *` | First day of every month at midnight |
| `*/15 * * * *` | Every 15 minutes |
| `0 12 * * 1,3,5` | Mon, Wed, Fri at noon |
| `0 0,12 * * *` | Twice daily (midnight and noon) |

### Usage

#### Start the Scheduler

Run the scheduler in the foreground:

```bash
python src/utils/cron_scheduler.py
```

With custom config:

```bash
python src/utils/cron_scheduler.py --config ./configurations/custom.json
```

#### Check Status

View current scheduler status:

```bash
python src/utils/cron_scheduler.py --status
```

#### Run as Background Service

Using nohup:

```bash
nohup python src/utils/cron_scheduler.py > scheduler.log 2>&1 &
```

Using screen:

```bash
screen -S loadtest-scheduler
python src/utils/cron_scheduler.py
# Press Ctrl+A then D to detach
```

Using systemd (recommended for production):

Create `/etc/systemd/system/loadtest-scheduler.service`:

```ini
[Unit]
Description=Load Test Cron Scheduler
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/shikhar/LoadTest
ExecStart=/home/shikhar/LoadTest/.venv/bin/python src/utils/cron_scheduler.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable loadtest-scheduler
sudo systemctl start loadtest-scheduler
sudo systemctl status loadtest-scheduler
```

### Complete Configuration Example

Here's a complete example with multiple scenarios on different schedules:

```json
{
  "global_settings": {
    "report_path": "./results/",
    "log_level": "INFO"
  },
  "scenarios": [
    {
      "id": "hourly_speed_check",
      "description": "Quick speed check every hour",
      "protocol": "speed_test",
      "enabled": true,

      "schedule": {
        "mode": "cron",
        "cron_expression": "0 * * * *",
        "timezone": "local"
      },

      "parameters": {
        "public": ["speedtest.shinternet.ch:5201"],
        "duration": 5,
        "uplink": "10",
        "downlink": "100"
      },

      "expectations": [
        {
          "metric": "download_speed",
          "operator": "gte",
          "value": 50,
          "unit": "mbps"
        }
      ]
    },
    {
      "id": "daily_comprehensive_test",
      "description": "Comprehensive test at 2 AM daily",
      "protocol": "speed_test",
      "enabled": true,

      "schedule": {
        "mode": "cron",
        "cron_expression": "0 2 * * *",
        "timezone": "local"
      },

      "parameters": {
        "private": ["192.168.1.1:5000"],
        "public": [
          "speedtest.shinternet.ch:5201",
          "iperf.online.net:5201"
        ],
        "duration": 30,
        "uplink": "10",
        "downlink": "100"
      },

      "expectations": [
        {
          "metric": "download_speed",
          "operator": "gte",
          "value": 80,
          "unit": "mbps"
        },
        {
          "metric": "upload_speed",
          "operator": "gte",
          "value": 8,
          "unit": "mbps"
        }
      ]
    },
    {
      "id": "weekday_business_hours_monitor",
      "description": "Monitor during business hours on weekdays",
      "protocol": "speed_test",
      "enabled": true,

      "schedule": {
        "mode": "cron",
        "cron_expression": "0 9-17 * * 1-5",
        "timezone": "local"
      },

      "parameters": {
        "public": ["speedtest.shinternet.ch:5201"],
        "duration": 10,
        "uplink": "10",
        "downlink": "100"
      },

      "expectations": [
        {
          "metric": "download_speed",
          "operator": "gte",
          "value": 50,
          "unit": "mbps"
        }
      ]
    }
  ]
}
```

### Schedule Mode Options

The scheduler supports multiple schedule modes in the same configuration:

1. **`"mode": "cron"`** - Cron-based scheduling (this module)
2. **`"mode": "once"`** - Run once immediately
3. **`"mode": "recurring"`** - Run repeatedly with fixed intervals

### Logging

Logs are written to:
- Console (stdout)
- `./logs/scheduler.log` file

Log entries include:
- Timestamp of execution
- Scenario ID
- Success/failure status
- Next scheduled run time
- Run count

### Monitoring

Check scheduler status:

```bash
# View status
python src/utils/cron_scheduler.py --status

# View logs
tail -f logs/scheduler.log

# View test results
ls -lh results/
```

### Tips

1. **Test Your Cron Expression**: Use online tools like [crontab.guru](https://crontab.guru) to validate expressions
2. **Start Small**: Begin with a simple schedule and verify it works before adding complex scenarios
3. **Monitor Resources**: Long-running tests can consume bandwidth and system resources
4. **Set Expectations**: Configure appropriate expectations for automated alerting
5. **Review Logs**: Regularly check `logs/scheduler.log` for any issues

### Troubleshooting

**Scheduler not starting:**
```bash
# Check if croniter is installed
pip list | grep croniter

# Verify configuration syntax
python -m json.tool configurations/main.json
```

**Tests not running at expected time:**
- Verify cron expression using online tools
- Check system timezone matches configuration
- Review logs for error messages

**Jobs running but failing:**
- Check individual test protocol logs
- Verify server endpoints are reachable
- Ensure proper permissions for result directories

### Integration with Other Tools

The scheduler can be integrated with:
- **Alerting**: Send notifications on test failures
- **Dashboards**: Export metrics to Grafana/Prometheus
- **CI/CD**: Trigger on deployment events
- **Monitoring**: Integrate with existing monitoring systems

### Advanced Usage

#### Programmatic Control

```python
from src.utils.cron_scheduler import CronScheduler

# Create scheduler
scheduler = CronScheduler(config_path='./configurations/main.json')

# Get status
status = scheduler.get_status()
print(f"Running: {status['running']}")
print(f"Total jobs: {status['total_jobs']}")

# Start scheduler in background
import threading
scheduler_thread = threading.Thread(target=scheduler.start, daemon=True)
scheduler_thread.start()

# Later: stop scheduler
scheduler.stop()
```

#### Custom Test Protocols

To add support for new test protocols, modify the `run_test()` method in `cron_scheduler.py` to handle your protocol type.

### Support

For issues or questions:
1. Check the logs in `./logs/scheduler.log`
2. Verify configuration syntax
3. Test cron expressions using online validators
4. Review example configurations above
