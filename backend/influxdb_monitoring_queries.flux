// Requêtes de monitoring InfluxDB pour VIGILEOS
// Générées le 2025-06-04T12:36:34.249243

// Equipment Health
from(bucket: "vigileos-metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "equipment_metrics")
  |> filter(fn: (r) => r["_field"] == "cpu_usage" or r["_field"] == "memory_usage")
  |> group(columns: ["equipment_id"])
  |> mean()

// Network Performance
from(bucket: "vigileos-metrics")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "network_metrics")
  |> filter(fn: (r) => r["_field"] == "ping_response_time")
  |> aggregateWindow(every: 1h, fn: mean)

// Availability Report
from(bucket: "vigileos-metrics")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_measurement"] == "availability")
  |> filter(fn: (r) => r["_field"] == "is_online")
  |> group(columns: ["equipment_id"])
  |> mean()
  |> map(fn: (r) => ({ r with uptime_percentage: r._value * 100.0 }))

// Alert Frequency
from(bucket: "vigileos-metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "alerts")
  |> group(columns: ["equipment_id", "alert_type"])
  |> count()

