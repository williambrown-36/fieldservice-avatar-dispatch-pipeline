"""Run the work-order avatar pipeline from the command line."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from field_avatar import AvatarPipeline, WorkOrderAvatarRequest
from field_avatar.infrai_images import InfraiImages


def main() -> None:
    parser = argparse.ArgumentParser(description="Process a technician avatar for a work order")
    parser.add_argument("avatar", type=Path)
    parser.add_argument("--work-order", required=True)
    parser.add_argument("--technician", required=True)
    parser.add_argument("--photo-count", required=True, type=int)
    args = parser.parse_args()

    api_key = os.environ["INFRAI_API_KEY"]
    request = WorkOrderAvatarRequest(
        work_order_id=args.work_order,
        technician_id=args.technician,
        filename=args.avatar.name,
        content=args.avatar.read_bytes(),
        work_order_photo_count=args.photo_count,
    )
    result = AvatarPipeline(InfraiImages(api_key)).run(request)
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
