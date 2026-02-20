#!/usr/bin/env python3
"""
Generate videos using Alibaba Cloud DashScope (通义万相视频生成)

Usage:
    python3 generate_video.py --prompt "描述内容" --img_url "图片URL" --out video.mp4

Environment variable:
    DASHSCOPE_API_KEY - Your DashScope API key
"""

import argparse
import os
import sys
import time

try:
    import dashscope
    from dashscope import VideoSynthesis
except ImportError:
    print("Error: dashscope package not installed")
    print("Run: pip install dashscope")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Generate videos using Alibaba Cloud DashScope"
    )
    parser.add_argument(
        "--prompt", "-p",
        required=True,
        help="Text prompt for video generation"
    )
    parser.add_argument(
        "--img_url", "-i",
        help="Input image URL for image-to-video generation"
    )
    parser.add_argument(
        "--out", "-o",
        default="output.mp4",
        help="Output file path (default: output.mp4)"
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=5,
        help="Video duration in seconds (default: 5)"
    )
    parser.add_argument(
        "--model", "-m",
        default="wan2.6-i2v-flash",
        choices=["wan2.6-i2v-flash", "wan2.6-i2v", "wan2.5-i2v-preview", "wan2.2-i2v-plus"],
        help="Model to use (default: wan2.6-i2v-flash)"
    )

    args = parser.parse_args()

    # Get API key
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        print("Error: DASHSCOPE_API_KEY environment variable not set")
        sys.exit(1)

    dashscope.api_key = api_key

    print(f"Generating video with DashScope...")
    print(f"Model: {args.model}")
    print(f"Prompt: {args.prompt}")
    print(f"Duration: {args.duration}s")
    if args.img_url:
        print(f"Image URL: {args.img_url[:50]}...")
    print()

    # Submit video generation task
    try:
        result = VideoSynthesis.call(
            model=args.model,
            prompt=args.prompt,
            img_url=args.img_url,
            duration=args.duration
        )
    except Exception as e:
        print(f"Error submitting task: {e}")
        sys.exit(1)

    if result.status_code != 200:
        print(f"Error: {result.code} - {result.message}")
        sys.exit(1)

    task_id = result.output.task_id
    print(f"Task ID: {task_id}")
    print(f"Status: {result.output.task_status}")

    # Wait for completion
    if result.output.task_status in ["PENDING", "RUNNING"]:
        print("Waiting for video generation...")
        max_attempts = 60
        for attempt in range(1, max_attempts + 1):
            time.sleep(5)
            status = VideoSynthesis.fetch(task=task_id)
            print(f"  Attempt {attempt}/{max_attempts}: {status.output.task_status}")

            if status.output.task_status == "SUCCEEDED":
                video_url = status.output.video_url
                print()
                print("Video generated successfully!")
                print(f"VIDEO_URL: {video_url}")
                print()
                print(f"Downloading to {args.out}...")

                # Download video
                import requests
                resp = requests.get(video_url)
                with open(args.out, "wb") as f:
                    f.write(resp.content)

                print(f"Saved to: {args.out}")
                print()
                print("MEDIA_URL:", video_url)
                return

            elif status.output.task_status == "FAILED":
                print(f"Error: Video generation failed")
                if hasattr(status.output, 'message'):
                    print(f"Message: {status.output.message}")
                sys.exit(1)

        print("Error: Timeout waiting for video generation")
        sys.exit(1)

    elif result.output.task_status == "SUCCEEDED":
        video_url = result.output.video_url
        print()
        print("Video generated successfully!")
        print(f"VIDEO_URL: {video_url}")
        print()
        print("MEDIA_URL:", video_url)

        # Download video
        if args.out:
            import requests
            print(f"Downloading to {args.out}...")
            resp = requests.get(video_url)
            with open(args.out, "wb") as f:
                f.write(resp.content)
            print(f"Saved to: {args.out}")

    else:
        print(f"Unexpected status: {result.output.task_status}")
        sys.exit(1)


if __name__ == "__main__":
    main()
