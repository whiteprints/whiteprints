from rich.console import Console
from rich.table import Table

import time
import multiprocessing
import numpy as np
import threading
from collections import deque

from whiteprints.libqueue.queue_thread import SafeQueue
from whiteprints.libqueue.queue_protocol import ProcessSharedQueue

MESSAGE_COUNT = 10_000


class SafeQueueFeeder:
    __slots__ = ("_feeder_buffer", "_feeder_buffer_append", "_queue", "_feeder_thread",
                 "_feeder_not_empty", "_feeder_not_empty_notify", "semaphore",
                 "_get", "_release", "_acquire")

    def __init__(self, maxsize=0, hooks=None):
        SEM_VALUE_MAX = multiprocessing.synchronize.SEM_VALUE_MAX
        maxsize = min(max(maxsize, 0), SEM_VALUE_MAX) or SEM_VALUE_MAX
        self._queue = SafeQueue(shared_queue=ProcessSharedQueue(maxsize))
        self.semaphore = multiprocessing.get_context().BoundedSemaphore(maxsize)
        self._reset()

    def get(self):
        item = self._get()
        self._release()
        return item

    def _reset(self):
        self._feeder_thread = None
        self._feeder_not_empty = threading.Condition(threading.Lock())
        self._feeder_not_empty_notify = self._feeder_not_empty.notify
        self._get = self._queue.shared_queue.get
        self._release = self.semaphore.release
        self._acquire = self.semaphore.acquire

    def _init_feeder(self):
        self._feeder_buffer = deque()
        self._feeder_buffer_append = self._feeder_buffer.append
        self._feeder_thread = threading.Thread(target=self._feeder_loop,
                                               daemon=False)
        self._feeder_thread.start()

    def _feeder_loop(self):
        pop = self._feeder_buffer.popleft
        wait = self._feeder_not_empty.wait
        put = self._queue.shared_queue.put
        release = self.semaphore.release
        while True:
            with self._feeder_not_empty:
                while not self._feeder_buffer:
                    wait()

                while self._feeder_buffer:
                    if (item := pop()) is None:
                        release()
                        return

                    put(item)

    def put(self, item):
        if self._feeder_thread is None:
            with self._feeder_not_empty:
                if self._feeder_thread is None:
                        self._init_feeder()

        self._acquire()
        with self._feeder_not_empty:
            self._feeder_buffer_append(item)
            self._feeder_not_empty_notify()

    def close(self):
        self.put(None)

    def join_thread(self):
        if self._feeder_thread is not None:
            self._feeder_thread.join()

    def __getstate__(self):
        multiprocessing.context.assert_spawning(self)
        return {"_queue": self._queue, "semaphore": self.semaphore}

    def __setstate__(self, state):
        self._queue = state["_queue"]
        self.semaphore = state["semaphore"]
        self._reset()


def timed_writer(queue, count, out_q):
    total = []
    for i in range(count):
        time.sleep(0)
        start = time.perf_counter()
        queue.put(i)
        end = time.perf_counter()
        total.append(end - start)

    out_q.put(('write', np.median(total)))
    if isinstance(queue, (SafeQueueFeeder,)):
        queue.close()


def timed_reader(queue, count, out_q):
    total = []
    for _ in range(count):
        start = time.perf_counter()
        queue.get()
        end = time.perf_counter()
        total.append(end - start)

    out_q.put(('read', np.median(total)))
    if hasattr(queue, "close"):
        queue.close()
    if hasattr(queue, "join_thread"):
        queue.join_thread()


def run_parallel_timed(queue, readers, writers, total_messages):
    per_writer = total_messages // max(writers, 1)
    per_reader = total_messages // max(readers, 1)

    out_q = multiprocessing.Queue()
    processes = []

    for i in range(writers):
        p = multiprocessing.Process(target=timed_writer, args=(queue, per_writer, out_q), name=f"W_{i}")
        processes.append(p)

    for i in range(readers):
        p = multiprocessing.Process(target=timed_reader, args=(queue, per_reader, out_q), name=f"R_{i}")
        processes.append(p)

    for p in processes:
        p.start()

    for p in processes[:writers]:
        p.join()

    write_times = []
    read_times = []

    for _ in range(readers + writers):
        role, duration = out_q.get()
        if role == 'write':
            write_times.append(duration)
        else:
            read_times.append(duration)

    out_q.close()
    out_q.join_thread()

    for p in processes[writers:]:
        p.join()

    return (
        sum(write_times) / len(write_times) if write_times else 0,
        sum(read_times) / len(read_times) if read_times else 0,
        per_reader,
        per_writer,
    )


def benchmark():
    test_patterns = [(1, 1), (100, 1), (1, 100), (100, 100)]
    queue_sizes = [1, 10, 100, 1000, 0]
    results = []

    for size in queue_sizes:
        maxsize_label = size if size != 0 else "unbounded"

        for readers, writers in test_patterns:
            pattern_label = f"{readers}R/{writers}W"
            print(f"Running: size={maxsize_label}, pattern={pattern_label}")

            safe_q = SafeQueue(shared_queue=ProcessSharedQueue(maxsize=size))
            safe_write, safe_read, per_reader, per_writer = run_parallel_timed(safe_q, readers, writers, MESSAGE_COUNT)

            mp_q = multiprocessing.Queue(maxsize=size)
            mp_write, mp_read, per_reader, per_writer = run_parallel_timed(mp_q, readers, writers, MESSAGE_COUNT)

            feeder_q = SafeQueueFeeder(maxsize=size)
            feeder_write, feeder_read, per_reader, per_writer = run_parallel_timed(feeder_q, readers, writers, MESSAGE_COUNT)

            results.append({
                "Queue Size": maxsize_label,
                "Pattern": pattern_label,
                "Safe Write (s)": safe_write,
                "Safe Read (s)": safe_read,
                "Safe Write Ratio": safe_write / mp_write if mp_write else float('inf'),
                "Safe Read Ratio": safe_read / mp_read if mp_read else float('inf'),
                "Feeder Write (s)": feeder_write,
                "Feeder Read (s)": feeder_read,
                "Feeder Write Ratio": feeder_write / mp_write if mp_write else float('inf'),
                "Feeder Read Ratio": feeder_read / mp_read if mp_read else float('inf'),
                "MP Write (s)": mp_write,
                "MP Read (s)": mp_read,
                "MP Messages Written": per_writer,
                "MP Messages Read": per_reader,
            })

    return results


def format_results(results):
    console = Console()
    table = Table(title="Queue Benchmark Results", show_lines=True)

    # Top-level columns
    table.add_column("Queue Size")
    table.add_column("Pattern")
    for label in ["SafeQueue", "FeederSafeQueue"]:
        table.add_column(f"{label} Write")
        table.add_column(f"{label} Read")
        table.add_column(f"{label} W Ratio")
        table.add_column(f"{label} R Ratio")

    table.add_column("MP Write (s)")
    table.add_column("MP Read (s)")
    table.add_column("MP Msgs / writer")
    table.add_column("MP Msgs / reader")

    for row in results:
        table.add_row(
            str(row["Queue Size"]),
            row["Pattern"],
            f"{row['Safe Write (s)']:.4E}", f"{row['Safe Read (s)']:.4E}",
            f"{row['Safe Write Ratio']:.2f}", f"{row['Safe Read Ratio']:.2f}",
            f"{row['Feeder Write (s)']:.4E}", f"{row['Feeder Read (s)']:.4E}",
            f"{row['Feeder Write Ratio']:.2f}", f"{row['Feeder Read Ratio']:.2f}",
            f"{row['MP Write (s)']:.4E}", f"{row['MP Read (s)']:.4E}",
            str(row["MP Messages Written"]), str(row["MP Messages Read"]),
        )

    console.print(table)


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    results = benchmark()
    format_results(results)
