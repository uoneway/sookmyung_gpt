from datetime import time

from src import logger


class Timer:
    def __init__(self, name: str = ""):
        self.name = name

    def __enter__(self):
        self.start_time = time.time()

    def __exit__(self, exc_type, exc_value, traceback):
        elapsed_time = round(time.time() - self.start_time, 4)
        logger.info(f"[Elapsed time] {self.name}: {elapsed_time} seconds")


def timer_decorator(msg: str = ""):
    def inner_decorator(func):
        def wrapper(*args, **kwargs):
            logger.info(f"[{msg}] Start")

            start_time = time.time()
            result = func(*args, **kwargs)
            elapsed_time = round(time.time() - start_time, 4)
            if msg:
                logger.info(f"[{msg}] Elapsed time: {elapsed_time} seconds")
            else:
                logger.info(f"[Elapsed time] {func.__name__}: {elapsed_time} seconds")
            return result

        return wrapper

    return inner_decorator


def async_timer_decorator(msg: str = ""):
    def inner_decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            result = await func(*args, **kwargs)
            elapsed_time = round(time.time() - start_time, 4)
            if msg:
                logger.info(f"[Elapsed time] {msg}: {elapsed_time} seconds")
            else:
                logger.info(f"[Elapsed time] {func.__name__}: {elapsed_time} seconds")
            return result

        return wrapper

    return inner_decorator


def get_elapsed_time(from_time):
    return round(time.time() - from_time, 4)
