import requests
import os

from zernio import Zernio, ZernioAPIError
from langchain.tools import tool

client = Zernio()


@tool
def upload_tiktok_video(filename: str, caption: str, account_id: str) -> str:
    """
    Upload a video file and a caption to TikTok social platform via Zernio API.
    """

    try:
        presigned_result = client.media.get_media_presigned_url(
            filename=filename, content_type="video/mp4"
        )
    except ZernioAPIError as e:
        return f"Failed to get presigned URL: {e}"

    upload_url = presigned_result["uploadUrl"]
    public_url = presigned_result["publicUrl"]

    with open(filename, "rb") as f:
        try:
            requests.put(
                upload_url, data=f.read(), headers={"Content-Type": "video/mp4"}
            )
        except requests.HTTPError as e:
            return f"Failed to upload video: {e}"

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
    from dotenv import load_dotenv

    load_dotenv()

    filename = "result_optimized.mp4"
    caption = "Check out my new video!"
    account_id = os.getenv("GROUN_TRUTH_MEDIA_ACCOUNT_ID")

    result = upload_tiktok_video(filename, caption, account_id)
    print(result)
