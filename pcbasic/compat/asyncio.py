from collections.abc import AsyncIterable


async def aiter_or_iter(iterable):
    if isinstance(iterable, AsyncIterable):
        async for item in iterable:
            yield item
    else:
        for item in iterable:
            yield item


async def azip(*iterables):
    iterators = [aiter_or_iter(it) for it in iterables]
    while True:
        try:
            results = []
            for it in iterators:
                try:
                    results.append(await anext(it))
                except (StopAsyncIteration, StopIteration):
                    return  # Stop if any iterator is exhausted
            yield tuple(results)
        except StopAsyncIteration:
            return
