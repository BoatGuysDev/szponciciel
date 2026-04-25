import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from tqdm import tqdm

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = Path(os.environ.get("MEDIA_ROOT", _PROJECT_ROOT / "media"))

VIDEOS: dict[str, list[str]] = {
    "satisfying": [
        "https://cdn.revid.ai/backgrounds/satisfying/cone_low.mp4",
        "https://cdn.revid.ai/backgrounds/satisfying/crush_low.mp4",
        "https://cdn.revid.ai/backgrounds/satisfying/dominos_low.mp4",
        "https://cdn.revid.ai/backgrounds/satisfying/forks_low.mp4",
        "https://cdn.revid.ai/backgrounds/satisfying/fruits_low.mp4",
        "https://cdn.revid.ai/backgrounds/satisfying/horse_low.mp4",
        "https://cdn.revid.ai/backgrounds/satisfying/mag_low.mp4",
        "https://cdn.revid.ai/backgrounds/satisfying/marble_race_low.mp4",
        "https://cdn.revid.ai/backgrounds/satisfying/painting_low.mp4",
        "https://cdn.revid.ai/backgrounds/satisfying/pebbles_low.mp4",
        "https://cdn.revid.ai/backgrounds/satisfying/petals_low.mp4",
        "https://cdn.revid.ai/backgrounds/satisfying/pumkin_low.mp4",
        "https://cdn.revid.ai/backgrounds/satisfying/rainbow_low.mp4",
        "https://cdn.revid.ai/backgrounds/satisfying/sand_low.mp4",
        "https://cdn.revid.ai/backgrounds/satisfying/soap_low.mp4",
        "https://cdn.revid.ai/backgrounds/satisfying/sponge_low.mp4",
        "https://cdn.revid.ai/backgrounds/satisfying/straw_low.mp4",
    ],
    "ugc": [
        "https://cdn.revid.ai/backgrounds/ugc/1_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/10_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/11_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/12_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/13_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/14_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/15_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/16_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/17_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/18_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/19_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/2_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/20_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/21_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/22_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/23_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/24_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/25_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/3_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/4_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/5_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/6_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/7_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/8_low.mp4",
        "https://cdn.revid.ai/backgrounds/ugc/9_low.mp4",
    ],
    "subway_surfer": [
        "https://cdn.revid.ai/subway_surfers/china_surfer_low.mp4",
        "https://cdn.revid.ai/subway_surfers/green_surfer_low.mp4",
        "https://cdn.revid.ai/subway_surfers/jump_surfer_low.mp4",
        "https://cdn.revid.ai/subway_surfers/LOW_RES/1.mp4",
        "https://cdn.revid.ai/subway_surfers/LOW_RES/2.mp4",
        "https://cdn.revid.ai/subway_surfers/LOW_RES/3.mp4",
        "https://cdn.revid.ai/subway_surfers/LOW_RES/4.mp4",
        "https://cdn.revid.ai/subway_surfers/LOW_RES/5.mp4",
        "https://cdn.revid.ai/subway_surfers/LOW_RES/6.mp4",
        "https://cdn.revid.ai/subway_surfers/red-surfer_low.mp4",
        "https://cdn.revid.ai/subway_surfers/snow-surfer_low.mp4",
    ],
    "temple_run": [
        "https://cdn.revid.ai/backgrounds/tr/clip1_lowres.mp4",
        "https://cdn.revid.ai/backgrounds/tr/clip2_lowres.mp4",
        "https://cdn.revid.ai/backgrounds/tr/clip3_lowres.mp4",
        "https://cdn.revid.ai/backgrounds/tr/clip4_lowres.mp4",
        "https://cdn.revid.ai/backgrounds/tr/clip5_lowres.mp4",
        "https://cdn.revid.ai/backgrounds/tr/clip6_lowres.mp4",
        "https://cdn.revid.ai/backgrounds/tr/clip7_lowres.mp4",
        "https://cdn.revid.ai/backgrounds/tr/clip8_lowres.mp4",
    ],
    "minecraft": [
        "https://cdn.revid.ai/backgrounds/minecraft/color_low.mp4",
        "https://cdn.revid.ai/backgrounds/minecraft/island_low.mp4",
        "https://cdn.revid.ai/backgrounds/minecraft/orbit_low.mp4",
        "https://cdn.revid.ai/backgrounds/minecraft/skyscraper_low.mp4",
        "https://cdn.revid.ai/backgrounds/minecraft/water_low.mp4",
        "https://cdn.revid.ai/minecraft/bg-1-low.mp4",
        "https://cdn.revid.ai/minecraft/bg-2-low.mp4",
        "https://cdn.revid.ai/minecraft/bg-3-low.mp4",
        "https://cdn.revid.ai/minecraft/bg-4-low.mp4",
        "https://cdn.revid.ai/minecraft/bg-5-low.mp4",
    ],
    "fortnite": [
        "https://cdn.revid.ai/backgrounds/fortnite/video_lowres_1.mp4",
        "https://cdn.revid.ai/backgrounds/fortnite/video_lowres_2.mp4",
        "https://cdn.revid.ai/backgrounds/fortnite/video_lowres_3.mp4",
        "https://cdn.revid.ai/backgrounds/fortnite/video_lowres_4.mp4",
        "https://cdn.revid.ai/backgrounds/fortnite/video_lowres_5.mp4",
    ],
    "trackmania": [
        "https://cdn.revid.ai/backgrounds/trackmania/video_lowres_1.mp4",
        "https://cdn.revid.ai/backgrounds/trackmania/video_lowres_2.mp4",
        "https://cdn.revid.ai/backgrounds/trackmania/video_lowres_3.mp4",
        "https://cdn.revid.ai/backgrounds/trackmania/video_lowres_4.mp4",
        "https://cdn.revid.ai/backgrounds/trackmania/video_lowres_5.mp4",
    ],
    "galaxy": [
        "https://cdn.revid.ai/backgrounds/space/video_lowres_1.mp4",
        "https://cdn.revid.ai/backgrounds/space/video_lowres_2.mp4",
        "https://cdn.revid.ai/backgrounds/space/video_lowres_3.mp4",
        "https://cdn.revid.ai/backgrounds/space/video_lowres_4.mp4",
        "https://cdn.revid.ai/backgrounds/space/video_lowres_5.mp4",
    ],
}


def download_file(url: str, dest: Path, session: requests.Session) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    try:
        with session.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            with (
                tmp.open("wb") as f,
                tqdm(
                    total=total or None,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    leave=False,
                ) as bar,
            ):
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    bar.update(len(chunk))
        tmp.rename(dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Download stock background videos")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    total_videos = sum(len(urls) for urls in VIDEOS.values())
    if not total_videos:
        print("No videos defined.")
        sys.exit(0)

    print(f"Videos:  {total_videos}")
    print(f"Output:  {OUTPUT}")
    print()

    skipped = fetched = failed = 0

    with requests.Session() as session:
        for category, urls in VIDEOS.items():
            for url in urls:
                dest = OUTPUT / category / Path(urlparse(url).path).name

                if dest.exists():
                    print(f"  skip  {dest.relative_to(OUTPUT)}  (already exists)")
                    skipped += 1
                    continue

                print(f"  fetch {dest.relative_to(OUTPUT)}")
                print(f"        {url}")

                if args.dry_run:
                    fetched += 1
                    continue

                try:
                    download_file(url, dest, session)
                    fetched += 1
                except Exception as exc:
                    print(f"  ERROR: {exc}", file=sys.stderr)
                    failed += 1

    print()
    label = "would fetch" if args.dry_run else "downloaded"
    print(f"Done — {label}: {fetched}, skipped: {skipped}, failed: {failed}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
