from typing import List, Dict
import queue
import torch.multiprocessing as mp
import traceback
from .utils import MP_WORKER_TIMEOUT

MAX_RESULT_QUEUE_SIZE = 32


def do_load(
    work_queue: mp.Queue, result_queue: mp.Queue, consumer_load_fn: dict
) -> bool:
    if result_queue.full():
        return True

    try:
        item, index, note_id, consumer_id = work_queue.get(False)
    except queue.Empty:
        return True

    load_fn = consumer_load_fn[consumer_id]
    try:
        result_tensor = load_fn(item)
        result = (result_tensor, index)
        to_return = ((result, note_id), consumer_id)
    except Exception as e:
        to_return = ((None, note_id), consumer_id)
        print(f"Worker Error loading {item}:")
        traceback.print_exc()
        return False

    result_queue.put(to_return, block=False)
    return True


def do_dump(
    work_queue: mp.Queue, result_queue: mp.Queue, consumer_dump_fn: dict
) -> bool:
    if result_queue.full():
        return True

    try:
        data, note_id, consumer_id = work_queue.get(False)
    except queue.Empty:
        return True

    dump_fn = consumer_dump_fn[consumer_id]
    to_return = (note_id, consumer_id)
    try:
        dump_fn(data)
    except Exception as e:
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
    consumer_load_fn: dict,
    consumer_dump_fn: dict,
    close_event: mp.Event,
    fail_event: mp.Event,
):
    try:
        while True:
            # Load
            if close_event.is_set():
                return
            succeeded = do_load(load_queue, load_result_queue, consumer_load_fn)
            if not succeeded:
                fail_event.set()
                return

            # Dump
            if close_event.is_set():
                return
            succeeded = do_dump(dump_queue, dump_result_queue, consumer_dump_fn)
            if not succeeded:
                fail_event.set()
                return
    except KeyboardInterrupt:
        pass

class Dataloader:
    def __init__(self, num_workers: int = 1):
        self.num_workers = num_workers
        self.context = mp.get_context("spawn")
        self.consumer_load_queues: Dict[int, mp.Queue] = {}
        self.consumer_dump_queues: Dict[int, mp.Queue] = {}
        manager = self.context.Manager()
        self.consumer_load_fn = manager.dict()
        self.consumer_dump_fn = manager.dict()
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
        self._fail_event: mp.Event = self.context.Event()
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
                    self.consumer_load_fn,
                    self.consumer_dump_fn,
                    self._close_event,
                    self._fail_event,
                ),
            )
            w.daemon = True
            w.start()
            self._load_queues.append(load_queue)
            self._dump_queues.append(dump_queue)
            self._load_result_queues.append(load_result_queue)
            self._dump_result_queues.append(dump_result_queue)
            self._workers.append(w)

    def setup(
        self,
        consumer_ids: List[int],
        consumer_load_fn: List[callable],
        consumer_dump_fn: List[callable],
    ):
        d = {}
        for id, load_fn, dump_fn in zip(consumer_ids, consumer_load_fn, consumer_dump_fn):
            d[id] = (load_fn, dump_fn)
        consumer_ids = set(consumer_ids)
        curr_ids = set(self.consumer_load_fn.keys())
        print(consumer_ids, curr_ids)
        new_ids = consumer_ids - curr_ids
        old_ids = curr_ids - consumer_ids
        print(new_ids)
        print(old_ids)

        for id in new_ids:
            self.consumer_load_queues[id] = self.context.Queue()
            self.consumer_dump_queues[id] = self.context.Queue()
            self.consumer_load_fn[id] = d[id][0]
            self.consumer_dump_fn[id] = d[id][1]
        print("A")

        for id in old_ids:
            self.total_consumer_size -= self.consumer_load_queues[id].qsize()
            self.total_consumer_size -= self.consumer_dump_queues[id].qsize()
            del self.consumer_load_queues[id]
            del self.consumer_dump_queues[id]
            del self.consumer_load_fn[id]
            del self.consumer_dump_fn[id]
        print("B")

    def shutdown(self):
        if len(self._workers) == 0:
            return
        try:
            self._close_event.set()
            self._close_queues()
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
                    
    def _close_queues(self):
        for q in self._load_queues:
            q.cancel_join_thread()
            q.close()
        for q in self._dump_queues:
            q.cancel_join_thread()
            q.close()
        for q in self._load_result_queues:
            q.cancel_join_thread()
            q.close()
        for q in self._dump_result_queues:
            q.cancel_join_thread()
            q.close()
        for q in self.consumer_load_queues.values():
            q.cancel_join_thread()
            q.close()
        for q in self.consumer_dump_queues.values():
            q.cancel_join_thread()
            q.close()

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
        for q in self.consumer_load_queues.values():
            clear_queue(q)
        for q in self.consumer_dump_queues.values():
            clear_queue(q)
        self.total_consumer_size = 0

    def put_load(
        self, items: list, note_id: int, consumer_id: int
    ):
        for i, item in enumerate(items):
            self._load_queues[self._worker_queue_cycle].put(
                (item, i, note_id, consumer_id), block=False
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
        note_id: int,
        consumer_id: int,
    ):
        self._dump_queues[self._worker_queue_cycle].put(
            (data, note_id, consumer_id), block=False
        )
        self._worker_queue_cycle = (self._worker_queue_cycle + 1) % self.num_workers

    def get_dump(self, consumer_id):
        self._handle_queues()
        if consumer_id not in self.consumer_dump_queues:
            return None
        try:
            note_id = self.consumer_dump_queues[consumer_id].get(False)
            self.total_consumer_size -= 1
            return note_id
        except queue.Empty:
            return None
        
    def is_failed(self):
        return self._fail_event.is_set()
