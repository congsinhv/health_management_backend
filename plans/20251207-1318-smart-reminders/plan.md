# Smart Reminders - Implementation Plan

**Date**: 2025-12-07
**Status**: PLANNED
**Branch**: feat/smart-reminders
**Priority**: P1

---

## Overview

Push notification system for workout reminders with AI-generated exercise plans.

**Core Flow**:
1. User creates weekly schedule (fixed/flexible times)
2. AI generates personalized exercise plan via OpenAI
3. Cloud Scheduler triggers batch processing every 5min
4. Cloud Tasks schedule FCM notifications
5. User receives reminder 5min before workout

**Key Decisions**:
- Single reminder per workout (5min before start)
- One active plan per user (archive superseded)
- Automated exercise logging on notification send
- UTC storage, user timezone for display

---

## Architecture

```
User Request → FastAPI → ScheduleService → OpenAI (plan generation)
                                        ↓
                              ScheduleRepository → PostgreSQL
                                        ↓
Cloud Scheduler (*/5 * * * *) → NotificationService → Cloud Tasks
                                        ↓
Cloud Tasks → FCMService → Firebase → User Device
            ↓
      Log to PostgreSQL (user_exercise_logs)
```

---

## Database Tables

| Table | Purpose |
|-------|---------|
| `schedule_plans` | User weekly config + AI plan |
| `scheduled_notifications` | Notification queue with UTC times |
| `user_devices` | FCM tokens per device |
| `user_exercise_logs` | Track calories/minutes when notification sent |

---

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/schedules` | Create/update schedule |
| GET | `/api/v1/schedules` | Get active schedule |
| DELETE | `/api/v1/schedules` | Deactivate schedule |
| POST | `/api/v1/schedules/regenerate` | Regenerate AI plan |
| POST | `/api/v1/devices` | Register FCM token |
| DELETE | `/api/v1/devices/{token}` | Remove FCM token |
| POST | `/api/v1/notifications/process-batch` | Internal: batch processing |
| POST | `/api/v1/notifications/send` | Internal: send FCM |

---

## Phases

| Phase | Description | Estimate | Status |
|-------|-------------|----------|--------|
| 1 | Database Schema | 2h | DONE (2025-12-07)
| 2 | Repositories | 3h | DONE (2025-12-07)
| 3 | Services | 6h | DONE (2025-12-07)
| 4 | API Endpoints | 4h | DONE (2025-12-07)
| 5 | GCP Integration | 4h | DONE (2025-12-07)
| 6 | Testing | 4h | DONE (2025-12-07)

**Total**: ~23 hours

---

## Dependencies

```txt
google-cloud-tasks>=2.15.0
firebase-admin>=6.5.0
```

---

## Files

- [Phase 1: Database Schema](./phase-01-database-schema.md)
- [Phase 2: Repositories](./phase-02-repositories.md)
- [Phase 3: Services](./phase-03-services.md)
- [Phase 4: API Endpoints](./phase-04-api-endpoints.md)
- [Phase 5: GCP Integration](./phase-05-gcp-integration.md)
- [Phase 6: Testing](./phase-06-testing.md)

---

## Success Criteria

- [x] User can create/update weekly schedule
- [x] AI generates exercise plan matching user goals
- [x] Notifications sent 5min before workout
- [x] Multiple device support per user
- [x] Graceful handling of failed FCM tokens
- [x] 80%+ test coverage
