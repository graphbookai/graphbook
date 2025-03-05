from typing import List, Dict, Tuple, Any, Optional
import queue
import multiprocessing as mp
import traceback
from .utils import MP_WORKER_TIMEOUT

MAX_RESULT_QUEUE_SIZE = 32


def do_load(
    work_queue: mp.Queue, result_queue: mp.Queue, load_fn: callable
) -> Tuple[bool, Any]:

    try:
        item, index, obj_id, params = work_queue.get(False)
    except queue.Empty:
        return True, None

    try:
        output = load_fn(item, **params)
        result = (output, index)
        to_return = (result, obj_id)
    except Exception as e:
        to_return = (None, obj_id)
        print(f"Worker Error loading {item}:")
        traceback.print_exc()
        return False, None

    try:
        result_queue.put(to_return, block=False)
    except queue.Full:
        return False, to_return
    return True, None


def do_dump(
    work_queue: mp.Queue, result_queue: mp.Queue, dump_fn: callable
) -> Tuple[bool, Any]:
    try:
        data, obj_id = work_queue.get(False)
    except queue.Empty:
        return True, None

    to_return = obj_id
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


PendingResult = Optional[Tuple[int, Any]]


def load_loop(
    rank: int,
    num_processes: int,
    load_queues: Dict[int, mp.Queue],
    load_result_queues: Dict[int, mp.Queue],
    consumer_load_fn: Dict[int, callable],
    pending_load_results: List[PendingResult],
    close_event: mp.Event,
    fail_event: mp.Event,
):
    consumer_ids = list(load_queues.keys())
    num_queues = len(consumer_ids)
    cycle = rank % num_queues

    while not close_event.is_set() and not fail_event.is_set():
        try:
            pending_item = pending_load_results[rank]
            if pending_item is not None:
                pending_for, pending_item = pending_item
                try:
                    load_result_queues[pending_for].put(
                        pending_item, block=True, timeout=MP_WORKER_TIMEOUT
                    )
                    pending_load_results[rank] = None
                except queue.Full:
                    pass
                except KeyError:
                    pass
            else:
                consumer_id = consumer_ids[cycle]
                succeeded, pending_item = do_load(
                    load_queues[consumer_id],
                    load_result_queues[consumer_id],
                    consumer_load_fn[consumer_id],
                )
                if not succeeded:
                    if pending_item is None:
                        fail_event.set()
                        return
                    else:
                        pending_load_results[rank] = (consumer_id, pending_item)
                cycle = (cycle + 1) % num_queues
        except KeyboardInterrupt:
            print(f"(Load): Exiting worker {rank}")
            break


def dump_loop(
    rank: int,
    num_processes: int,
    dump_queues: Dict[int, mp.Queue],
    dump_result_queues: Dict[int, mp.Queue],
    consumer_dump_fn: Dict[int, callable],
    pending_dump_results: List[PendingResult],
    close_event: mp.Event,
    fail_event: mp.Event,
):
    consumer_ids = list(dump_queues.keys())
    num_queues = len(consumer_ids)
    cycle = rank % num_queues
    while not close_event.is_set() and not fail_event.is_set():
        try:
            pending_item = pending_dump_results[rank]
            if pending_item is not None:
                pending_for, pending_item = pending_item
                try:
                    dump_result_queues[pending_for].put(
                        pending_item, block=True, timeout=MP_WORKER_TIMEOUT
                    )
                    pending_dump_results[rank] = None
                except queue.Full:
                    pass
                except KeyError:
                    pass
            else:
                consumer_id = consumer_ids[cycle]
                succeeded, pending_item = do_dump(
                    dump_queues[consumer_id],
                    dump_result_queues[consumer_id],
                    consumer_dump_fn[consumer_id],
                )
                if not succeeded:
                    if pending_item is None:
                        fail_event.set()
                        return
                    else:
                        pending_dump_results[rank] = (consumer_id, pending_item)
                cycle = (cycle + 1) % num_queues
        except KeyboardInterrupt:
            print(f"(Dump): Exiting worker {rank}")
            break


class Dataloader:
    def __init__(self, num_workers: int = 1, spawn_method: bool = False):
        self.num_workers = num_workers
        self.context = mp
        if spawn_method:
            print(
                "Using spawn method is not recommended because it is more error prone. Try to avoid it as much as possible."
            )
            self.context = mp.get_context("spawn")
        self.manager = self.context.Manager()
        self._load_queues: Dict[int, mp.Queue] = self.manager.dict()
        self._dump_queues: Dict[int, mp.Queue] = self.manager.dict()
        self._load_result_queues: Dict[int, mp.Queue] = self.manager.dict()
        self._dump_result_queues: Dict[int, mp.Queue] = self.manager.dict()
        self._consumer_load_fn = {}
        self._consumer_dump_fn = {}
        self._pending_load_results: List[PendingResult] = self.manager.list(
            [None for _ in range(num_workers)]
        )
        self._pending_dump_results: List[PendingResult] = self.manager.list(
            [None for _ in range(num_workers)]
        )

        self._workers: List[mp.Process] = []
        self._loaders: List[mp.Process] = []
        self._dumpers: List[mp.Process] = []
        self._worker_queue_cycle = 0
        self._close_event: mp.Event = self.context.Event()
        self._fail_event: mp.Event = self.context.Event()

    def _start_workers(self):
        if len(self._workers) > 0:
            return
        self._fail_event.clear()
        self._close_event.clear()
        for i in range(self.num_workers):
            load_process = self.context.Process(
                target=load_loop,
                args=(
                    i,
                    self.num_workers,
                    self._load_queues,
                    self._load_result_queues,
                    self._consumer_load_fn,
                    self._pending_load_results,
                    self._close_event,
                    self._fail_event,
                ),
            )
            load_process.daemon = True
            load_process.start()
            dump_process = self.context.Process(
                target=dump_loop,
                args=(
                    i,
                    self.num_workers,
                    self._dump_queues,
                    self._dump_result_queues,
                    self._consumer_dump_fn,
                    self._pending_dump_results,
                    self._close_event,
                    self._fail_event,
                ),
            )
            dump_process.daemon = True
            dump_process.start()
            self._loaders.append(load_process)
            self._dumpers.append(dump_process)
            self._workers.extend([load_process, dump_process])

    def start(
        self,
        consumer_ids: List[int],
        consumer_load_fn: List[callable],
        consumer_dump_fn: List[callable],
    ):
        self._stop_workers()
        if len(consumer_ids) == 0:
            return
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
            self._load_queues[id] = self.manager.Queue()
            self._dump_queues[id] = self.manager.Queue()
            self._load_result_queues[id] = self.manager.Queue(
                maxsize=MAX_RESULT_QUEUE_SIZE
            )
            self._dump_result_queues[id] = self.manager.Queue(
                maxsize=MAX_RESULT_QUEUE_SIZE
            )
            self._consumer_load_fn[id] = c[id][0]
            self._consumer_dump_fn[id] = c[id][1]

        for id in old_ids:
            del self._load_queues[id]
            del self._dump_queues[id]
            del self._load_result_queues[id]
            del self._dump_result_queues[id]
            del self._consumer_load_fn[id]
            del self._consumer_dump_fn[id]

        self._start_workers()

    def stop(self):
        self._stop_workers()

    def _stop_workers(self):
        if len(self._workers) == 0:
            return
        try:
            self._close_event.set()
            for w in self._workers:
                w.join(timeout=MP_WORKER_TIMEOUT + 10)
        finally:
            for w in self._workers:
                if w.is_alive():
                    print("Must now terminate worker")
                    w.terminate()
            self._workers = []
            self._dumpers = []
            self._loaders = []

    def shutdown(self):
        self._stop_workers()
        self.clear()

    def get_all_sizes(self):
        sz = {
            "load": [q.qsize() for q in self._load_queues.values()],
            "dump": [q.qsize() for q in self._dump_queues.values()],
            "load_result": [q.qsize() for q in self._load_result_queues.values()],
            "dump_result": [q.qsize() for q in self._dump_result_queues.values()],
        }
        return sz

    def clear(self, consumer_id: Optional[int] = None):
        def clear_queue(q: mp.Queue):
            while not q.empty():
                try:
                    q.get(False)
                except:
                    return

        if consumer_id is None:
            try:
                for q in self._load_queues.values():
                    clear_queue(q)
                for q in self._dump_queues.values():
                    clear_queue(q)
                for q in self._load_result_queues.values():
                    clear_queue(q)
                for q in self._dump_result_queues.values():
                    clear_queue(q)
            except FileNotFoundError:
                pass
            self._load_queues = {}
            self._dump_queues = {}
            self._load_result_queues = {}
            self._dump_result_queues = {}
            self._consumer_load_fn = {}
            self._consumer_dump_fn = {}
            for i in range(self.num_workers):
                self._pending_load_results[i] = None
                self._pending_dump_results[i] = None
        else:
            try:
                if consumer_id in self._load_queues:
                    clear_queue(self._load_queues[consumer_id])
                if consumer_id in self._dump_queues:
                    clear_queue(self._dump_queues[consumer_id])
                if consumer_id in self._load_result_queues:
                    clear_queue(self._load_result_queues[consumer_id])
                if consumer_id in self._dump_result_queues:
                    clear_queue(self._dump_result_queues[consumer_id])
                if consumer_id in self._consumer_load_fn:
                    del self._consumer_load_fn[consumer_id]
                if consumer_id in self._consumer_dump_fn:
                    del self._consumer_dump_fn[consumer_id]
            except FileNotFoundError:
                pass

    def put_load(
        self, items: list, load_fn_params: dict, obj_id: int, consumer_id: int
    ):
        for i, item in enumerate(items):
            self._load_queues[consumer_id].put(
                (item, i, obj_id, load_fn_params), block=False
            )

    def get_load(self, consumer_id):
        if consumer_id not in self._load_result_queues:
            return None
        try:
            try:
                result, obj_id = self._load_result_queues[consumer_id].get(False)
            except FileNotFoundError:
                return None
            if result is None:
                return None, obj_id
            out, index = result
            return (out, index), obj_id
        except queue.Empty:
            return None

    def put_dump(
        self,
        data: Any,
        obj_id: int,
        consumer_id: int,
    ):
        self._dump_queues[consumer_id].put((data, obj_id), block=False)

    def get_dump(self, consumer_id):
        if consumer_id not in self._dump_result_queues:
            return None
        try:
            try:
                obj_id = self._dump_result_queues[consumer_id].get(False)
            except FileNotFoundError:
                return None
            return obj_id
        except queue.Empty:
            return None

    def is_failed(self):
        return self._fail_event.is_set()

    def clear_failed(self):
        self._fail_event.clear()
