import asyncio

import pytest


def test_evaluator_task_queue_serializes_jobs_and_reports_position():
    from evaluator.services.task_queue import EvaluatorQueue

    async def scenario():
        queue = EvaluatorQueue(max_concurrent=1, max_pending=5)
        order = []
        second_messages = []
        first_started = asyncio.Event()
        release_first = asyncio.Event()
        second_started = asyncio.Event()

        async def first_job():
            async with queue.acquire(lambda _message: None):
                order.append("first-start")
                first_started.set()
                await release_first.wait()
                order.append("first-end")

        async def second_job():
            await first_started.wait()
            async with queue.acquire(second_messages.append):
                order.append("second-start")
                second_started.set()

        first_task = asyncio.create_task(first_job())
        await first_started.wait()
        second_task = asyncio.create_task(second_job())
        await asyncio.sleep(0.05)

        assert not second_started.is_set()
        assert queue.snapshot() == {
            "max_concurrent": 1,
            "running": 1,
            "pending": 1,
            "max_pending": 5,
        }
        assert any("position 1" in message.lower() for message in second_messages)

        release_first.set()
        await asyncio.gather(first_task, second_task)

        assert order == ["first-start", "first-end", "second-start"]
        assert queue.snapshot()["running"] == 0

    asyncio.run(scenario())


def test_evaluator_task_queue_rejects_when_pending_limit_is_full():
    from evaluator.services.task_queue import EvaluatorQueue, EvaluatorQueueFull

    async def scenario():
        queue = EvaluatorQueue(max_concurrent=1, max_pending=1)
        first_started = asyncio.Event()
        release_first = asyncio.Event()

        async def first_job():
            async with queue.acquire(lambda _message: None):
                first_started.set()
                await release_first.wait()

        first_task = asyncio.create_task(first_job())
        await first_started.wait()

        second_context = queue.acquire(lambda _message: None)
        second_task = asyncio.create_task(second_context.__aenter__())
        await asyncio.sleep(0.05)

        with pytest.raises(EvaluatorQueueFull):
            async with queue.acquire(lambda _message: None):
                pass

        release_first.set()
        await second_task
        await second_context.__aexit__(None, None, None)
        await first_task

    asyncio.run(scenario())


def test_evaluator_task_queue_removes_cancelled_pending_job():
    from evaluator.services.task_queue import EvaluatorQueue

    async def scenario():
        queue = EvaluatorQueue(max_concurrent=1, max_pending=5)
        first_started = asyncio.Event()
        release_first = asyncio.Event()

        async def first_job():
            async with queue.acquire(lambda _message: None):
                first_started.set()
                await release_first.wait()

        first_task = asyncio.create_task(first_job())
        await first_started.wait()

        pending_context = queue.acquire(lambda _message: None)
        pending_task = asyncio.create_task(pending_context.__aenter__())
        await asyncio.sleep(0.05)

        assert queue.snapshot()["pending"] == 1

        pending_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending_task
        await asyncio.sleep(0.01)

        assert queue.snapshot()["pending"] == 0

        release_first.set()
        await first_task

    asyncio.run(scenario())
