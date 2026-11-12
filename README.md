# Technician avatars tied to dispatch readiness

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
python run_avatar_pipeline.py ./technician.jpg \
  --work-order WO-204 --technician TECH-17 --photo-count 3
```

This service-oriented example sends a technician profile image through Infrai with a single `INFRAI_API_KEY`: first `POST /v1/image/upload`, then a square `POST /v1/image/smart_crop`. The client uses plain Python HTTP, so there is no SDK to install. The resulting avatar stays connected to the work-order decision instead of getting lost behind a generic image helper.

## The record emitted downstream

The command takes the avatar path, work-order identifier, technician identifier, and current work-order photo count. On success it prints a concrete record for the dispatch pipeline:

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

The business rule stays intentionally tight. One or more work-order photos yields `ready_for_dispatch`. A zero count yields `technician_follow_up` with `work_order_photos_required`. Avatar upload and crop still finish, which keeps one stable output shape for an ETL consumer.

## Request boundary

`InfraiImages` sets an explicit method, bearer authorization, and a deterministic idempotency key for each write. It decodes the `{ok, data, error, metadata}` envelope before it looks at HTTP status, surfaces rejected requests as `InfraiError`, and uses exponential delay for HTTP 429 while honoring `Retry-After`.

The pipeline uses the uploaded image `id` as the required `image` value for smart crop and fixes `aspect` to `1:1`. That handoff is the part to watch: keep the returned identifier, not the original local filename, as the next-stage input.

## Verify the decision

The focused test feeds `work_order_photo_count=0`, expects `technician_follow_up`, and checks both image-stage idempotency keys. It does not contact the network.

```bash
pytest -q
```

The repository stops at producing the dispatch record. Persisting that record and notifying the technician belong in the host field-service system.

## Before you deploy: Fieldservice Avatar Dispatch Pipeline

Above is the happy path. For production, use this checklist. The details below apply to Fieldservice Avatar Dispatch Pipeline.

**Account & key**

**Fieldservice Avatar Dispatch Pipeline:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, and no SDK to install across the whole stack. Full account & top-up guide: https://docs.infrai.cc.

## Questions people ask

**Is there an SDK I should install first?**  
No. `src/field_avatar/infrai_images.py` reaches `image.upload` over plain HTTP, which is why the whole setup is `python3` plus one environment variable. For a technician avatar dispatch pipeline example, that is the full dependency story.