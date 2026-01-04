#!/usr/bin/env python3
"""
Timeline auto-generation scheduler for Ink & Memory.

Generates daily timeline images for users at midnight (Beijing time by default).
Runs concurrently for all users with activity on the previous day.
"""

import os
import time

os.environ.setdefault('TZ', 'UTC')
if hasattr(time, 'tzset'):
    time.tzset()

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import database
from server import generate_daily_picture


async def generate_for_user(user_id: int, text: str, date: str, timezone: str) -> dict:
    """
    Generate timeline image for a single user (async wrapper).

    Args:
        user_id: User ID
        text: Text content from user's sessions on that date
        date: Date string (YYYY-MM-DD)

    Returns:
        dict with success status and metadata
    """
    try:
        # Call the existing PolyCLI session function (runs in thread pool)
        print(f"🎨 User {user_id}: Generating image for {date} ({len(text)} chars)")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: generate_daily_picture(
                user_id=user_id,
                target_date=date,
                timezone=timezone,
                notes_override=text,
                skip_if_exists=True,
                dry_run=False,
            )
        )

        if result and 'image_base64' in result:
            # Save to database with explicit date
            database.save_daily_picture(
                user_id=user_id,
                date=date,
                image_base64=result['image_base64'],
                thumbnail_base64=result.get('thumbnail_base64'),
                prompt=result.get('prompt')
            )
            print(f"✅ User {user_id}: Successfully generated and saved image for {date}")
            return {"success": True, "user_id": user_id, "date": date}
        else:
            print(f"❌ User {user_id}: Generation failed - no image returned")
            return {"success": False, "error": "No image returned", "user_id": user_id, "date": date}

    except Exception as e:
        print(f"❌ User {user_id}: Error generating image for {date}: {e}")
        return {"success": False, "error": str(e), "user_id": user_id, "date": date}


async def generate_timeline_images_for_date(target_date: str, timezone: str = 'Asia/Shanghai', max_concurrent: int = 5):
    """
    Generate timeline images for all users with activity on target_date.

    Args:
        target_date: Date string (YYYY-MM-DD) in local timezone
        timezone: Timezone name (default: Asia/Shanghai for Beijing)
        max_concurrent: Maximum concurrent generations (rate limiting)

    Returns:
        dict with statistics: total, success, failed, skipped
    """
    print(f"\n{'='*60}")
    print(f"📅 Timeline Auto-Generation Started")
    print(f"   Date: {target_date} ({timezone})")
    print(f"   Max concurrent: {max_concurrent}")
    print(f"{'='*60}\n")

    try:
        # Step 1: Get users with activity on this date
        user_ids = database.get_users_with_activity_on_date(target_date, timezone)
        print(f"📊 Found {len(user_ids)} users with activity on {target_date}")

        if not user_ids:
            print("ℹ️  No users with activity, exiting")
            return {"total": 0, "success": 0, "failed": 0, "skipped": 0}

        # Step 2: Extract text for each user
        tasks = []
        for user_id in user_ids:
            try:
                text = database.extract_text_from_sessions_on_date(user_id, target_date, timezone)
                if text.strip():
                    # Create async task with semaphore for rate limiting
                    task = generate_for_user(user_id, text, target_date, timezone)
                    tasks.append(task)
                else:
                    print(f"⏭️  User {user_id}: No text content, skipping")
            except Exception as e:
                print(f"❌ User {user_id}: Error extracting text: {e}")
                continue

        print(f"🚀 Starting generation for {len(tasks)} users (batched: {max_concurrent} concurrent)")

        # Step 3: Run with rate limiting (semaphore)
        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_generate(task):
            async with semaphore:
                return await task

        results = await asyncio.gather(*[bounded_generate(task) for task in tasks], return_exceptions=True)

        # Step 4: Summarize results
        success_count = sum(1 for r in results if isinstance(r, dict) and r.get('success') and not r.get('skipped'))
        failed_count = sum(1 for r in results if isinstance(r, dict) and not r.get('success'))
        skipped_count = sum(1 for r in results if isinstance(r, dict) and r.get('skipped'))
        exception_count = sum(1 for r in results if isinstance(r, Exception))

        print(f"\n{'='*60}")
        print(f"✅ Timeline Auto-Generation Completed")
        print(f"   Total: {len(tasks)}")
        print(f"   Success: {success_count}")
        print(f"   Skipped: {skipped_count}")
        print(f"   Failed: {failed_count + exception_count}")
        print(f"{'='*60}\n")

        return {
            "total": len(tasks),
            "success": success_count,
            "failed": failed_count + exception_count,
            "skipped": skipped_count
        }

    except Exception as e:
        print(f"❌ Timeline auto-generation failed: {e}")
        import traceback
        traceback.print_exc()
        return {"total": 0, "success": 0, "failed": 0, "skipped": 0, "error": str(e)}


def get_previous_day(timezone: str = 'Asia/Shanghai') -> str:
    """
    Get previous day's date in YYYY-MM-DD format (local timezone).

    Args:
        timezone: Timezone name

    Returns:
        Date string in YYYY-MM-DD format
    """
    tz = ZoneInfo(timezone)
    now = datetime.now(tz)
    yesterday = now - timedelta(days=1)
    return yesterday.strftime('%Y-%m-%d')


# @@@ Scheduler job function (called by APScheduler)
async def daily_generation_job(timezone: str = 'Asia/Shanghai'):
    """
    Daily job to generate timeline images for yesterday.

    Called at midnight in the specified timezone.
    """
    target_date = get_previous_day(timezone)
    await generate_timeline_images_for_date(target_date, timezone)
