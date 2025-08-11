import timeit
import queue
from whiteprints.libqueue.queue_condition_thread_com import ThreadConditionCommunication
from whiteprints.libqueue.queue_condition import ConditionQueue

#  BOUNDED = 1_000_000
BOUNDED = 0
q1 = queue.Queue(BOUNDED)

def bench_put_stdlib():
    for _ in range(1000):
        q1.put(42)

def bench_get_stdlib():
    for _ in range(1000):
        q1.get()

q2 = ConditionQueue(
    com=ThreadConditionCommunication(BOUNDED or None),
)

def bench_put_whiteprints():
    for _ in range(1000):
        q2.put(42)

def bench_get_whiteprints():
    for _ in range(1000):
        q2.get()


N = 1000
stdlib_time_put = timeit.timeit(bench_put_stdlib, number=N)
stdlib_time_get = timeit.timeit(bench_get_stdlib, number=N)
whiteprints_time_put = timeit.timeit(bench_put_whiteprints, number=N)
whiteprints_time_get = timeit.timeit(bench_get_whiteprints, number=N)

print(f"stdlib.Queue.put:        {stdlib_time_put:.4f} sec")
print(f"ConditionQueue.put:      {whiteprints_time_put:.4f} sec")
print(f"Put ratio (stdlib / whiteprints): {stdlib_time_put / whiteprints_time_put:.2f}x")

print(f"stdlib.Queue.get:        {stdlib_time_get:.4f} sec")
print(f"ConditionQueue.get:      {whiteprints_time_get:.4f} sec")
print(f"Get ratio (stdlib / whiteprints): {stdlib_time_get / whiteprints_time_get:.2f}x")
