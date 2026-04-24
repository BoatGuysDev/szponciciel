import requests
import os
from pathlib import Path

from dotenv import load_dotenv
from zernio import Zernio, ZernioAPIError
from langchain.tools import tool

load_dotenv()
client = Zernio()


@tool
def upload_tiktok_video(filename: str, caption: str, account_id: str) -> str:
    """
    Post a video to TikTok.

    Args:
        filename: Local path to the video file (must be .mp4)
        caption: Text caption for the post
        account_id: TikTok account ID to post to
    """

    try:
        presigned_result = client.media.get_media_presigned_url(
            filename=filename, content_type="video/mp4"
        )
    except ZernioAPIError as e:
        return f"Failed to get presigned URL: {e}"

    upload_url = presigned_result["uploadUrl"]
    public_url = presigned_result["publicUrl"]

    path = Path(filename)
    if not path.exists():
        return f"File not found: {filename}"

    with path.open("rb") as f:
        upload_video_response = requests.put(
            upload_url, data=f.read(), headers={"Content-Type": "video/mp4"}
        )

    if not upload_video_response.ok:
        return f"Failed to upload video: {upload_video_response.text}"

    try:
        result = client.posts.create(
            content=caption,
            media_items=[{"url": public_url, "type": "video"}],
            platforms=[{"platform": "tiktok", "accountId": account_id}],
            publish_now=True,
        )
    except ZernioAPIError as e:
        return f"Failed to create post: {e}"

    return f"Video uploaded successfully! Post ID: {result.post.field_id}"


if __name__ == "__main__":
    filename = "path/to/your/video.mp4"
    caption = "Caption"
    account_id = os.getenv("GROUND_TRUTH_MEDIA_ACCOUNT_ID")

    result = upload_tiktok_video(filename, caption, account_id)
    print(result)
