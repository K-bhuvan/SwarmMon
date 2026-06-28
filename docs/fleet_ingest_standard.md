# Fleet ingest standard (schema v1)

SwarmMon field fleets use **one ROS topic** and **one gateway per site**. Robots (or a site aggregator) publish fleet status; the gateway forwards it to the backend.

**Local demo:** [README](../README.md#example-mikes-farm) · **Production deploy:** [first_client_deploy.md](first_client_deploy.md)

## Architecture

```text
  drone-01 ──┐
  drone-02 ──┼──► /swarmmon/fleet/status ──► ONE ROS gateway ──► SwarmMon backend
  drone-N  ──┘         (std_msgs/String)              │
                                                      └── auto-registers robots
```

## Standard names

| Item | Convention | Example |
|------|------------|---------|
| Fleet ID | `{customer}-{site}` lowercase, hyphens | `mike-farm` |
| Robot ID | `{type}-{nn}` | `drone-01` |
| ROS fleet topic | `/swarmmon/fleet/status` | fixed |
| Message type | `std_msgs/msg/String` | JSON body |

## Fleet status message (schema v1)

```json
{
  "schema_version": 1,
  "fleet_id": "mike-farm",
  "timestamp": "2026-06-26T22:30:00Z",
  "robots": [
    {
      "robot_id": "drone-01",
      "label": "North field",
      "online": true,
      "battery_pct": 82
    }
  ]
}
```

Rules:

- `schema_version` must be `1`
- `fleet_id` matches the onboarded SwarmMon fleet (`scenario_run_id`)
- `timestamp` is ISO-8601 UTC
- Each `robot_id` is unique within the fleet
- Unknown robots are **auto-registered** on ingest

## HTTP ingest (optional)

Gateways use HTTP internally. You can also POST the same JSON directly:

```http
POST /api/v1/fleet/ingest
Content-Type: application/json
X-SwarmMon-Key: <optional ingest key>
```

Body: same JSON as the ROS message above.
