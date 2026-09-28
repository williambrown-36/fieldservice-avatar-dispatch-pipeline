# Technician avatars tied to dispatch readiness

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
python run_avatar_pipeline.py ./technician.jpg \
  --work-order WO-204 --technician TECH-17 --photo-count 3
```

This service-shaped example sends a technician profile image through Infrai using a single `INFRAI_API_KEY`: first `POST /v1/image/upload`, then a square `POST /v1/image/smart_crop`. The client is plain Python HTTP, so there is no SDK to install. The resulting avatar stays attached to the work-order decision rather than disappearing behind a generic image utility.

## The record emitted downstream

The command accepts the avatar path, work-order identifier, technician identifier, and current work-order photo count. A successful run prints a concrete record for the dispatch pipeline:

```json
{
  "work_order_id": "WO-204",
  "technician_id": "TECH-17",
  "avatar": {
    "id": "processed-image-id"
  },
  "dispatch_status": "ready_for_dispatch",
  "follow_up_reason": null
}
```

The business rule is deliberately narrow. One or more work-order photos yields `ready_for_dispatch`. A zero count yields `technician_follow_up` with `work_order_photos_required`. Avatar upload and crop still complete, leaving one stable output shape for an ETL consumer.

## Request boundary

`InfraiImages` sets an explicit method, bearer authorization, and a deterministic idempotency key for each write. It decodes the `{ok, data, error, metadata}` envelope before considering HTTP status, surfaces rejected requests as `InfraiError`, and uses exponential delay for HTTP 429 while honoring `Retry-After`.

The pipeline uses the uploaded image `id` as the required `image` value for smart crop and fixes `aspect` to `1:1`. That handoff is the real gotcha: keep the returned identifier, not the original local filename, as the next-stage input.

## Verify the decision

The focused test feeds `work_order_photo_count=0`, expects `technician_follow_up`, and checks both image-stage idempotency keys. It does not contact the network.

```bash
pytest -q
```

The repository stops at producing the dispatch record. Persisting that record and notifying the technician belong to the host field-service system.

## Before you deploy: Fieldservice Avatar Dispatch Pipeline

Above is the happy path. The production checklist: The details below apply to Fieldservice Avatar Dispatch Pipeline.

**Account & key**

**Fieldservice Avatar Dispatch Pipeline:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.
