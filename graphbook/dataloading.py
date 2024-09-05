from typing import List, Dict, Tuple
import queue
import torch
from torch import Tensor
import torch.multiprocessing as mp
import traceback
from .utils import MP_WORKER_TIMEOUT
import time

torch.set_num_threads(1)
MAX_RESULT_QUEUE_SIZE = 32


def do_load(
    work_queue: mp.Queue, result_queue: mp.Queue, consumer_load_fn: dict
) -> Tuple[bool, any]:
    try:
        item, index, note_id, consumer_id = work_queue.get(False)
    except queue.Empty:
        return True, None

    load_fn = consumer_load_fn.get(consumer_id)
    if load_fn is None:
        return True, None
    try:
        result_tensor = load_fn(item)
        result = (result_tensor, index)
        to_return = (result, note_id)
    except Exception as e:
        to_return = (None, note_id)
        print(f"Worker Error loading {item}:")
        traceback.print_exc()
        return False, None

    try:
        result_queue.put(to_return, block=False)
    except queue.Full:
        return False, to_return
    return True, None


def do_dump(
    work_queue: mp.Queue, result_queue: mp.Queue, consumer_dump_fn: dict
) -> Tuple[bool, any]:
    try:
        data, note_id, consumer_id = work_queue.get(False)
    except queue.Empty:
        return True, None

    dump_fn = consumer_dump_fn.get(consumer_id)
    if dump_fn is None:
        return True, None
    to_return = note_id
    try:
        dump_fn(*data)
    except Exception as e:
        print(f"Worker Error on dumping {data}:")
        traceback.print_exc()
        return False, None

    try:
        result_queue.put(to_return, block=False)
    except queue.Full:
        return False, to_return
    return True, None


def load_loop(
    rank: int,
    num_processes: int,
    load_queues: Dict[int, mp.Queue],
    load_result_queues: Dict[int, mp.Queue],
    consumer_load_fn: Dict[int, callable],
    close_event: mp.Event,
    fail_event: mp.Event,
):
    consumer_ids = list(load_queues.keys())
    num_queues = len(consumer_ids)
    cycle = rank % num_queues
    pending_item = None
    try:
        while True:
            if pending_item is not None:
                try:
                    load_result_queues[consumer_id].put(
                        pending_item, block=True, timeout=MP_WORKER_TIMEOUT
                    )
                    pending_item = None
                except queue.Full:
                    pass
            else:
                if close_event.is_set():
                    return
                consumer_id = consumer_ids[cycle]
                succeeded, pending_item = do_load(
                    load_queues[consumer_id],
                    load_result_queues[consumer_id],
                    consumer_load_fn,
                )
                if not succeeded:
                    if pending_item is None:
                        fail_event.set()
                        return
                cycle = (cycle + 1) % num_queues
    except KeyboardInterrupt:
        pass


def dump_loop(
    rank: int,
    num_processes: int,
    dump_queues: Dict[int, mp.Queue],
    dump_result_queues: Dict[int, mp.Queue],
    consumer_dump_fn: Dict[int, callable],
    close_event: mp.Event,
    fail_event: mp.Event,
):
    consumer_ids = list(dump_queues.keys())
    num_queues = len(consumer_ids)
    cycle = rank % num_queues
    pending_item = None
    try:
        while True:
            if pending_item is not None:
                try:
                    dump_result_queues[consumer_id].put(
                        pending_item, block=True, timeout=MP_WORKER_TIMEOUT
                    )
                    pending_item = None
                except queue.Full:
                    pass
            else:
                if close_event.is_set():
                    return
                consumer_id = consumer_ids[cycle]
                succeeded = do_dump(
                    dump_queues[consumer_id],
                    dump_result_queues[consumer_id],
                    consumer_dump_fn,
                )
                if not succeeded:
                    fail_event.set()
                    return
                cycle = (cycle + 1) % num_queues
    except KeyboardInterrupt:
        pass


class Dataloader:
    def __init__(self, num_workers: int = 1):
        self.num_workers = num_workers
        self._load_queues: Dict[int, mp.Queue] = {}
        self._dump_queues: Dict[int, mp.Queue] = {}
        self._load_result_queues: Dict[int, mp.Queue] = {}
        self._dump_result_queues: Dict[int, mp.Queue] = {}
        self._consumer_load_fn = {}
        self._consumer_dump_fn = {}
        self._workers: List[mp.Process] = []
        self._loaders: List[mp.Process] = []
        self._dumpers: List[mp.Process] = []
        self._worker_queue_cycle = 0
        self._close_event: mp.Event = mp.Event()
        self._fail_event: mp.Event = mp.Event()

    def _start_workers(self):
        self._fail_event.clear()
        self._close_event.clear()
        for i in range(self.num_workers):
            load_process = mp.Process(
                target=load_loop,
                args=(
                    i,
                    self.num_workers,
                    self._load_queues,
                    self._load_result_queues,
                    self._consumer_load_fn,
                    self._close_event,
                    self._fail_event,
                ),
            )
            load_process.daemon = True
            load_process.start()
            dump_process = mp.Process(
                target=dump_loop,
                args=(
                    i,
                    self.num_workers,
                    self._dump_queues,
                    self._dump_result_queues,
                    self._consumer_dump_fn,
                    self._close_event,
                    self._fail_event,
                ),
            )
            dump_process.daemon = True
            dump_process.start()
            self._loaders.append(load_process)
            self._dumpers.append(dump_process)
            self._workers.extend([load_process, dump_process])

    def setup(
        self,
        consumer_ids: List[int],
        consumer_load_fn: List[callable],
        consumer_dump_fn: List[callable],
    ):
        c = {}
        for id, load_fn, dump_fn in zip(
            consumer_ids, consumer_load_fn, consumer_dump_fn
        ):
            c[id] = (load_fn, dump_fn)
        consumer_ids = set(consumer_ids)
        curr_ids = set(self._consumer_load_fn.keys())
        new_ids = consumer_ids - curr_ids
        old_ids = curr_ids - consumer_ids

        for id in new_ids:
            self._load_queues[id] = mp.Queue()
            self._dump_queues[id] = mp.Queue()
            self._load_result_queues[id] = mp.Queue(maxsize=MAX_RESULT_QUEUE_SIZE)
            self._dump_result_queues[id] = mp.Queue(maxsize=MAX_RESULT_QUEUE_SIZE)
            self._consumer_load_fn[id] = c[id][0]
            self._consumer_dump_fn[id] = c[id][1]

        for id in old_ids:
            del self._load_queues[id]
            del self._dump_queues[id]
            del self._load_result_queues[id]
            del self._dump_result_queues[id]
            del self._consumer_load_fn[id]
            del self._consumer_dump_fn[id]

        if len(self._workers) > 0:
            self._stop_workers()
        self._start_workers()

    def _stop_workers(self):
        if len(self._workers) == 0:
            return
        try:
            self._close_event.set()
            for w in self._workers:
                w.join(timeout=MP_WORKER_TIMEOUT)
        finally:
            for w in self._workers:
                if w.is_alive():
                    w.terminate()
            self._workers = []
            self._dumpers = []
            self._loaders = []

    def shutdown(self):
        self._stop_workers()
        self._close_queues()

    def _close_queues(self):
        for q in self._load_queues.values():
            q.cancel_join_thread()
            q.close()
        for q in self._dump_queues.values():
            q.cancel_join_thread()
            q.close()
        for q in self._load_result_queues.values():
            q.cancel_join_thread()
            q.close()
        for q in self._dump_result_queues.values():
            q.cancel_join_thread()
            q.close()

    def get_all_sizes(self):
        sz = {
            "load": [q.qsize() for q in self._load_queues.values()],
            "dump": [q.qsize() for q in self._dump_queues.values()],
            "load_result": [q.qsize() for q in self._load_result_queues.values()],
            "dump_result": [q.qsize() for q in self._dump_result_queues.values()],
        }
        return sz

    def clear(self):
        def clear_queue(q):
            while not q.empty():
                try:
                    q.get(False)
                except queue.Empty:
                    print("Emptying an empty queue. Is the graph still executing?")
                    break

        for q in self._load_queues.values():
            clear_queue(q)
        for q in self._dump_queues.values():
            clear_queue(q)
        for q in self._load_result_queues.values():
            clear_queue(q)
        for q in self._dump_result_queues.values():
            clear_queue(q)
        self._fail_event.clear()

    def put_load(self, items: list, note_id: int, consumer_id: int):
        for i, item in enumerate(items):
            self._load_queues[consumer_id].put(
                (item, i, note_id, consumer_id), block=False
            )

    def get_load(self, consumer_id):
        if consumer_id not in self._load_result_queues:
            return None
        try:
            try:
                result, note_id = self._load_result_queues[consumer_id].get(False)
            except FileNotFoundError:
                return None
            if result is None:
                return None, note_id
            out, index = result
            # https://pytorch.org/docs/stable/multiprocessing.html#sharing-cuda-tensors
            if isinstance(out, Tensor):
                out_clone = out.clone()
                del out
                out = out_clone
            return (out, index), note_id
        except queue.Empty:
            return None

    def put_dump(
        self,
        data: any,
        note_id: int,
        consumer_id: int,
    ):
        self._dump_queues[consumer_id].put((data, note_id, consumer_id), block=False)

    def get_dump(self, consumer_id):
        if consumer_id not in self._dump_result_queues:
            return None
        try:
            try:
                note_id = self._dump_result_queues[consumer_id].get(False)
            except FileNotFoundError:
                return None
            return note_id
        except queue.Empty:
            return None

    def is_failed(self):
        return self._fail_event.is_set()

    def clear_failed(self):
        self._fail_event.clear()


workers = None


def setup_global_dl(dataloader: Dataloader):
    global workers
    workers = dataloader


def put_load(items: list, note_id: int, consumer_id: int):
    global workers
    workers.put_load(items, note_id, consumer_id)


def get_load(consumer_id):
    global workers
    return workers.get_load(consumer_id)


def put_dump(data: any, note_id: int, consumer_id: int):
    global workers
    workers.put_dump(data, note_id, consumer_id)


def get_dump(consumer_id):
    global workers
    return workers.get_dump(consumer_id)
