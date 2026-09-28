"""Work-order avatar processing and dispatch decision."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Protocol


class ImageGateway(Protocol):
    def upload(self, content: bytes, filename: str, idempotency_key: str) -> Mapping[str, Any]:
        raise RuntimeError("abstract image gateway")

    def smart_crop(self, image: str, aspect: str, idempotency_key: str) -> Mapping[str, Any]:
        raise RuntimeError("abstract image gateway")


class DispatchStatus(str, Enum):
    READY_FOR_DISPATCH = "ready_for_dispatch"
    TECHNICIAN_FOLLOW_UP = "technician_follow_up"


@dataclass(frozen=True)
class WorkOrderAvatarRequest:
    work_order_id: str
    technician_id: str
    filename: str
    content: bytes
    work_order_photo_count: int

    def __post_init__(self) -> None:
        if not self.work_order_id or not self.technician_id:
            raise ValueError("work_order_id and technician_id are required")
        if not self.filename or not self.content:
            raise ValueError("filename and content are required")
        if self.work_order_photo_count < 0:
            raise ValueError("work_order_photo_count cannot be negative")


@dataclass(frozen=True)
class AvatarResult:
    work_order_id: str
    technician_id: str
    avatar: Mapping[str, Any]
    dispatch_status: DispatchStatus
    follow_up_reason: str | None


class AvatarPipeline:
    def __init__(self, images: ImageGateway) -> None:
        self._images = images

    def run(self, request: WorkOrderAvatarRequest) -> AvatarResult:
        key_root = f"work-order:{request.work_order_id}:technician:{request.technician_id}:avatar"
        uploaded = self._images.upload(request.content, request.filename, f"{key_root}:upload")
        image_id = uploaded.get("image_id")
        if not isinstance(image_id, str) or not image_id:
            raise ValueError("upload result did not contain an image id")

        avatar = self._images.smart_crop(image_id, "1:1", f"{key_root}:crop")
        if request.work_order_photo_count == 0:
            status = DispatchStatus.TECHNICIAN_FOLLOW_UP
            reason = "work_order_photos_required"
        else:
            status = DispatchStatus.READY_FOR_DISPATCH
            reason = None

        return AvatarResult(
            work_order_id=request.work_order_id,
            technician_id=request.technician_id,
            avatar=avatar,
            dispatch_status=status,
            follow_up_reason=reason,
        )
