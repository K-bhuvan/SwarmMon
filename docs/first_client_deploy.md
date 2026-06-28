# First client deployment (field fleet)

Production path for a site like **Mike’s farm** (`mike-farm`). Schema and topic names: [fleet_ingest_standard.md](fleet_ingest_standard.md).

**Try locally first:** [README — Example: Mike’s farm](../README.md#example-mikes-farm)

## Production (farm NUC)

Real robots publish to `/swarmmon/fleet/status`. On the barn PC, run the gateway only:

```bash
SWARMMON_BACKEND_URL=https://api.yourdomain.com ./scripts/ros2_mike_fleet.sh
```

Onboard once from your laptop or CI:

```bash
SWARMMON_BACKEND_URL=https://api.yourdomain.com ./scripts/onboard_field_fleet.sh
```

Operator confirms alert email under **Settings → Alerts** on the dashboard.

## What costs money?

| Service | Pilot cost | Notes |
|---------|------------|--------|
| **Resend** | **Free** | 100 emails/day |
| **Hosting** | **Your choice** | NUC/laptop or small VPS |
| **SMS / Auth** | Skipped | Optional ingest API key only |

## API reference

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/fleet/onboard` | Create fleet + alert settings |
| POST | `/api/v1/fleet/ingest` | Fleet snapshot (used by ROS gateway) |
| GET | `/api/v1/fleet/robots/{fleet_id}` | Roster + live/offline status |
| PUT | `/api/v1/fleet/settings/{fleet_id}` | Alert email, offline minutes |

## Deployment checklist

1. Onboard fleet once (`./scripts/onboard_field_fleet.sh`)
2. Set alert email in dashboard → **Alerts**
3. Deploy **one** ROS gateway on the site PC
4. Robots publish to `/swarmmon/fleet/status`
5. Operator uses dashboard + email only

## Single-robot dev (not field fleet)

For `/scan` + `/odom` harness demos: [ros2_live.md](ros2_live.md)
