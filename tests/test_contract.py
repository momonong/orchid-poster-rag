import asyncio
import importlib.util

import pytest


def test_citation_guard_rejects_foreign_and_missing_ids():
    assert importlib.util.find_spec("orchid") is not None, "RAG package must exist"
    from orchid.generation import validate_answer
    assert validate_answer('研究結果 [P01]', {"P01"})
    assert not validate_answer('研究結果 [P99]', {"P01"})
    assert not validate_answer('沒有出處的研究結果', {"P01"})


def test_chunk_limit_preserves_all_words():
    assert importlib.util.find_spec("orchid") is not None, "RAG package must exist"
    from orchid.corpus import split_text
    text = ' '.join(f'word{i}' for i in range(1300))
    chunks = split_text(text, lambda value: len(value.split()), 480, 'passage: Title ')
    assert len(chunks) > 2
    assert all(len(('passage: Title ' + c).split()) <= 480 for c in chunks)
    assert ' '.join(chunks) == text


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_release_generation():
    assert importlib.util.find_spec("orchid") is not None, "RAG package must exist"
    from orchid.generation import Busy, GenerationQueue
    queue = GenerationQueue(max_pending=1, wait_seconds=0.05)
    released = asyncio.Event()
    entered = asyncio.Event()
    async def slow():
        entered.set()
        await released.wait()
        return 'done'
    first = asyncio.create_task(queue.run(slow))
    await entered.wait()
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert queue.active == 1
    with pytest.raises(Busy):
        await queue.run(slow)
    assert queue.active == 1
    released.set()
    await asyncio.sleep(0.02)
    assert queue.active == 0
