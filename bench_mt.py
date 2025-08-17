import threading
import time
import queue
import timeit
from whiteprints.libqueue.queue_condition import ConditionQueue

TOTAL_MESSAGES = 1_000_000  # Total number of messages for each test run

from collections import Counter

write_count = Counter()
read_count = Counter()
count_lock = threading.Lock()


def benchmark_queue(QueueType, queue_name, num_readers, num_writers, bound):
    num_messages_per_writer = TOTAL_MESSAGES // num_writers
    num_messages_per_reader = TOTAL_MESSAGES // num_readers

    if QueueType == "stdlib":
        q = queue.Queue(bound)
    elif QueueType == "whiteprints":
        q = ConditionQueue(bound or None)
    else:
        raise ValueError("Unknown queue type")

    start_barrier = threading.Barrier(num_readers + num_writers)
    done_event = threading.Event()

    if QueueType == "stdlib":

        def writer():
            start_barrier.wait()
            for i in range(num_messages_per_writer):
                q.put(42)

        def reader():
            start_barrier.wait()
            for i in range(num_messages_per_reader):
                val = q.get()

    elif QueueType == "whiteprints":

        def writer():
            with q.producer():
                start_barrier.wait()
                for i in range(num_messages_per_writer):
                    q.put(42)

        def reader():
            cm = q.receiver()
            with cm:
                start_barrier.wait()
                for i in range(num_messages_per_reader):
                    val = q.get()
    else:
        raise ValueError("Unknown queue type")

    threads = []
    for _ in range(num_writers):
        threads.append(threading.Thread(target=writer, daemon=False))
    for _ in range(num_readers):
        threads.append(threading.Thread(target=reader, daemon=False))

    start = time.perf_counter()
    for t in threads:
        t.start()

    for t in threads:
        t.join()

    end = time.perf_counter()

    duration = end - start
    print(
        f"{queue_name:15s} | {num_readers:3d}R/{num_writers:3d}W | "
        f"{TOTAL_MESSAGES:,} msgs | {duration:.4f} sec"
    )
    return duration


def run_all_benchmarks():
    patterns = [
        (1, 1),
        (100, 100),
        (100, 1),
        (1, 100),
    ]

    print(f"{'Queue Type':15s} | Pattern    | Messages    | Time")
    print("-" * 60)

    #  for bound in [0, 1, 1000, 1_000_000]:
    for bound in [1, 10, 100, 1_000, 10_000, 0]:
        print(f"Bound: {bound or 'UNBOUNDED'}")
        for name in ("whiteprints", "stdlib"):
            for readers, writers in patterns:
                benchmark_queue(name, name, readers, writers, bound)


if __name__ == "__main__":
    run_all_benchmarks()
