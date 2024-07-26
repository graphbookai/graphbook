from typing import List
import queue
import torch.multiprocessing as mp
import traceback
from .utils import MP_WORKER_TIMEOUT

MAX_RESULT_QUEUE_SIZE = 32


def do_load(work_queue: mp.Queue, result_queue: mp.Queue) -> bool:
    if result_queue.full():
        return True

    try:
        item, index, record_id, load_fn, consumer_id = work_queue.get(False)
    except queue.Empty:
        return True

    try:
        result_tensor = load_fn(item)
        result = (result_tensor, index)
        to_return = ((result, record_id), consumer_id)
    except Exception as e:
        to_return = ((None, record_id), consumer_id)
        print(f"Worker Error loading {item}:")
        traceback.print_exc()
        return False

    result_queue.put(to_return, block=False)
    return True


def do_dump(work_queue: mp.Queue, result_queue: mp.Queue, output_dir: str) -> bool:
    if result_queue.full():
        return True

    try:
        data, item_key, record_id, dump_fn, consumer_id = work_queue.get(False)
    except queue.Empty:
        return True

    try:
        output_fn = dump_fn(data, output_dir)
        result = (item_key, output_fn)
        to_return = ((result, record_id), consumer_id)
    except Exception as e:
        to_return = ((None, record_id), consumer_id)
        print(f"Worker Error on dumping {data}:")
        traceback.print_exc()
        return False

    result_queue.put(to_return, block=False)
    return True


def worker_loop(
    rank: int,
    num_processes: int,
    load_queue: mp.Queue,
    dump_queue: mp.Queue,
    load_result_queue: mp.Queue,
    dump_result_queue: mp.Queue,
    dump_dir: str,
    close_event: mp.Event,
    fail_event: mp.Event,
):
    try:
        while True:
            # Load
            if close_event.is_set():
                return
            succeeded = do_load(load_queue, load_result_queue)
            if not succeeded:
                fail_event.set()
                return

            # Dump
            if close_event.is_set():
                return
            succeeded = do_dump(dump_queue, dump_result_queue, dump_dir)
            if not succeeded:
                fail_event.set()
                return
    except KeyboardInterrupt:
        pass


class Dataloader:
    def __init__(self, dump_dir: str, fail_event: mp.Event, num_workers: int = 1):
        self.dump_dir = dump_dir
        self.fail_event = fail_event
        self.num_workers = num_workers
        self.context = mp.get_context("spawn")
        self.consumer_load_queues = {}
        self.consumer_dump_queues = {}
        self.total_consumer_size = 0
        self._start_workers()

    def _start_workers(self):
        self._workers: List[mp.Process] = []
        self._worker_queue_cycle = 0
        self._load_queues: List[mp.Queue] = []
        self._dump_queues: List[mp.Queue] = []
        self._load_result_queues: List[mp.Queue] = []
        self._dump_result_queues: List[mp.Queue] = []
        self._close_event: mp.Event = self.context.Event()
        for i in range(self.num_workers):
            load_queue = self.context.Queue()
            dump_queue = self.context.Queue()
            load_result_queue = self.context.Queue(maxsize=MAX_RESULT_QUEUE_SIZE)
            dump_result_queue = self.context.Queue(maxsize=MAX_RESULT_QUEUE_SIZE)
            load_queue.cancel_join_thread()
            dump_queue.cancel_join_thread()
            w = self.context.Process(
                target=worker_loop,
                args=(
                    i,
                    self.num_workers,
                    load_queue,
                    dump_queue,
                    load_result_queue,
                    dump_result_queue,
                    self.dump_dir,
                    self._close_event,
                    self.fail_event,
                ),
            )
            w.daemon = True
            w.start()
            self._load_queues.append(load_queue)
            self._dump_queues.append(dump_queue)
            self._load_result_queues.append(load_result_queue)
            self._dump_result_queues.append(dump_result_queue)
            self._workers.append(w)

    def setup(self, consumer_ids: List[int]):
        for c in consumer_ids:
            if c not in self.consumer_load_queues:
                self.consumer_load_queues[c] = queue.Queue()
            if c not in self.consumer_dump_queues:
                self.consumer_dump_queues[c] = queue.Queue()
        unused_ids = set(self.consumer_load_queues.keys()) - set(consumer_ids)
        for c in unused_ids:
            self.total_consumer_size -= self.consumer_load_queues[c].qsize()
            del self.consumer_load_queues[c]
        unused_ids = set(self.consumer_dump_queues.keys()) - set(consumer_ids)
        for c in unused_ids:
            self.total_consumer_size -= self.consumer_dump_queues[c].qsize()
            del self.consumer_dump_queues[c]

    def shutdown(self):
        if len(self._workers) == 0:
            return
        try:
            self._close_event.set()
            for q in self._load_queues:
                q.cancel_join_thread()
                q.close()
            for q in self._dump_queues:
                q.cancel_join_thread()
                q.close()
            for w in self._workers:
                w.join(timeout=MP_WORKER_TIMEOUT)
        finally:
            for w in self._workers:
                if w.is_alive():
                    w.terminate()

    def _handle_queues(self):
        for queues, consumers in zip(
            [self._load_result_queues, self._dump_result_queues],
            [self.consumer_load_queues, self.consumer_dump_queues],
        ):
            for q in queues:
                while (
                    not q.empty() and self.total_consumer_size < MAX_RESULT_QUEUE_SIZE
                ):
                    result, consumer_id = q.get(False)
                    if consumer_id not in consumers:
                        continue
                    consumers[consumer_id].put(result, block=False)
                    self.total_consumer_size += 1

    def get_all_sizes(self):
        return {
            "load": [q.qsize() for q in self._load_queues],
            "dump": [q.qsize() for q in self._dump_queues],
            "load_result": [q.qsize() for q in self._load_result_queues],
            "dump_result": [q.qsize() for q in self._dump_result_queues],
            "total_consumer_size": self.total_consumer_size,
        }

    def clear(self):
        def clear_queue(q):
            while not q.empty():
                try:
                    q.get(False)
                except queue.Empty:
                    print("Emptying an empty queue. Is the graph still executing?")
                    break

        for q in self._load_queues:
            clear_queue(q)
        for q in self._dump_queues:
            clear_queue(q)
        for q in self._load_result_queues:
            clear_queue(q)
        for q in self._dump_result_queues:
            clear_queue(q)
        for q in self.consumer_load_queues:
            clear_queue(q)
        for q in self.consumer_dump_queues:
            clear_queue(q)
        self.total_consumer_size = 0

    def put_load(
        self, items: list, record_id: int, load_fn: callable, consumer_id: int
    ):
        for i, item in enumerate(items):
            self._load_queues[self._worker_queue_cycle].put(
                (item, i, record_id, load_fn, consumer_id), block=False
            )
            self._worker_queue_cycle = (self._worker_queue_cycle + 1) % self.num_workers

    def get_load(self, consumer_id):
        self._handle_queues()
        if consumer_id not in self.consumer_load_queues:
            return None
        try:
            result, record_id = self.consumer_load_queues[consumer_id].get(False)
            self.total_consumer_size -= 1
            if result is None:
                return None, record_id
            t, index = result
            t_clone = t.clone()
            del t
            return (t_clone, index), record_id
        except queue.Empty:
            return None

    def put_dump(
        self,
        data: any,
        item_key: str,
        record_id: int,
        dump_fn: callable,
        consumer_id: int,
    ):
        self._dump_queues[self._worker_queue_cycle].put(
            (data, item_key, record_id, dump_fn, consumer_id), block=False
        )
        self._worker_queue_cycle = (self._worker_queue_cycle + 1) % self.num_workers

    def get_dump(self, consumer_id):
        self._handle_queues()
        if consumer_id not in self.consumer_dump_queues:
            return None
        try:
            record_id = self.consumer_dump_queues[consumer_id].get(False)
            self.total_consumer_size -= 1
            return record_id
        except queue.Empty:
            return None

class DataDumper:
    def __init__(self):
        pass

    def dump(self, data: any, path: str):
        raise NotImplementedError()
