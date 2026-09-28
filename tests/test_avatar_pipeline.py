import base64
import json
from typing import Any, Mapping
from unittest.mock import patch

from field_avatar import AvatarPipeline, DispatchStatus, WorkOrderAvatarRequest
from field_avatar.infrai_images import InfraiImages


class RecordedImages:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object, str]] = []

    def upload(self, content: bytes, filename: str, idempotency_key: str) -> Mapping[str, Any]:
        self.calls.append(("upload", filename, idempotency_key))
        return {"image_id": "image_204"}

    def smart_crop(self, image: str, aspect: str, idempotency_key: str) -> Mapping[str, Any]:
        self.calls.append(("smart_crop", (image, aspect), idempotency_key))
        return {"id": "avatar_204", "aspect": aspect}


def test_missing_work_order_photos_routes_technician_follow_up() -> None:
    images = RecordedImages()
    request = WorkOrderAvatarRequest(
        work_order_id="WO-204",
        technician_id="TECH-17",
        filename="maria.jpg",
        content=b"image bytes",
        work_order_photo_count=0,
    )

    result = AvatarPipeline(images).run(request)

    assert result.dispatch_status is DispatchStatus.TECHNICIAN_FOLLOW_UP
    assert result.follow_up_reason == "work_order_photos_required"
    assert result.avatar == {"id": "avatar_204", "aspect": "1:1"}
    assert images.calls == [
        ("upload", "maria.jpg", "work-order:WO-204:technician:TECH-17:avatar:upload"),
        ("smart_crop", ("image_204", "1:1"), "work-order:WO-204:technician:TECH-17:avatar:crop"),
    ]


def test_existing_work_order_photo_allows_dispatch() -> None:
    request = WorkOrderAvatarRequest(
        work_order_id="WO-205",
        technician_id="TECH-18",
        filename="lee.jpg",
        content=b"image bytes",
        work_order_photo_count=2,
    )

    result = AvatarPipeline(RecordedImages()).run(request)

    assert result.dispatch_status is DispatchStatus.READY_FOR_DISPATCH
    assert result.follow_up_reason is None


def test_image_requests_use_contract_json_fields() -> None:
    requests = []

    class Response:
        status = 200
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"ok":true,"data":{"image_id":"image_204"}}'

    def urlopen(request):
        requests.append(request)
        return Response()

    with patch("field_avatar.infrai_images.urlopen", side_effect=urlopen):
        images = InfraiImages("test-key")
        images.upload(b"image bytes", "maria.jpg", "upload-key")
        images.smart_crop("image_204", "1:1", "crop-key")

    assert all(request.get_header("Content-type") == "application/json" for request in requests)
    assert json.loads(requests[0].data) == {
        "file": base64.b64encode(b"image bytes").decode("ascii"),
        "filename": "maria.jpg",
        "idempotency_key": "upload-key",
    }
    assert json.loads(requests[1].data) == {
        "image": {"image_id": "image_204"},
        "aspect": "1:1",
        "idempotency_key": "crop-key",
    }
