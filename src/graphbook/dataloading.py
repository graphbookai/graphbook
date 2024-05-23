from typing import List
import queue
import torch.multiprocessing as mp

MP_WORKER_TIMEOUT = 5.0
MAX_RESULT_QUEUE_SIZE = 32

def do_load(work_queue: mp.Queue, finished_items: list, consumer_queues: dict):
    if len(finished_items) > 0:
        try:
            data, consumer_id = finished_items[0]
            consumer_queues[consumer_id].put(data, block=False)
            finished_items.pop(0)
        except queue.Full:
            pass

    if len(finished_items) >= MAX_RESULT_QUEUE_SIZE:
        return
   
    # Process data
    try:
        item, index, record_id, load_fn, consumer_id = work_queue.get(False)
    except queue.Empty:
        return
    try:
        result_tensor = load_fn(item)
        result = (result_tensor, index)
        to_return = ((result, record_id), consumer_id)
    except Exception as e:
        to_return = ((None, record_id), consumer_id)
        print(f"Could not process input {item}. The following exception was raised: {e}")

    finished_items.append(to_return)

def do_dump(work_queue: mp.Queue, output_dir: str, consumer_queues: dict, uid: int) -> bool:
    try:
        data, item_key, record_id, dump_fn, consumer_id = work_queue.get(False)
    except queue.Empty:
        return False
    # Process data
    try:
        output_fn = dump_fn(data, output_dir, uid)
        consumer_queues[consumer_id].put((record_id, (item_key, output_fn)), block=False)
    except Exception as e:
        print(f"Could not dump input {data}. The following exception was raised: {e}")
        consumer_queues[consumer_id].put((record_id, None), block=False)
    return True

def worker_loop(rank: int,
                num_processes: int,
                data_queue: mp.Queue,
                dump_queue: mp.Queue,
                consumer_load_queues: dict,
                consumer_dump_queues: dict,
                dump_dir: str,
                close_event: mp.Event):
    finished_items = []
    dump_ctr = rank
    while not close_event.is_set():
        do_load(data_queue, finished_items, consumer_load_queues)
        did_receive_work = do_dump(dump_queue, dump_dir, consumer_dump_queues, dump_ctr)
        if did_receive_work:
            dump_ctr += num_processes

class Dataloader:
    def __init__(self, dump_dir: str, num_workers: int = 1):
        self.dump_dir = dump_dir
        self.num_workers = num_workers
        self.context = mp.get_context("spawn")
        self._is_setup = False

    def setup(self, consumer_ids: List[int]):
        if self._is_setup:
            print("Cannot setup dataloader twice.")
            return
        self.context = mp.get_context("spawn")
        self.consumer_load_queues = {c: self.context.Queue(maxsize=MAX_RESULT_QUEUE_SIZE) for c in consumer_ids}
        self.consumer_dump_queues = {c: self.context.Queue() for c in consumer_ids}
        self._workers: List[mp.Process] = []
        self._data_queues: List[mp.Queue] = []
        self._dump_queues: List[mp.Queue] = []
        self._close_event: mp.Event = self.context.Event()
        for i in range(self.num_workers):
            data_queue = self.context.Queue()
            dump_queue = self.context.Queue()
            data_queue.cancel_join_thread()
            w = self.context.Process(
                target=worker_loop,
                args=(i,
                      self.num_workers,
                      data_queue,
                      dump_queue,
                      self.consumer_load_queues,
                      self.consumer_dump_queues,
                      self.dump_dir,
                      self._close_event)
            )
            w.daemon = True
            w.start()
            self._data_queues.append(data_queue)
            self._dump_queues.append(dump_queue)
            self._workers.append(w)
        self.worker_queue_cycle = 0
        self._is_setup = True

    def shutdown(self):
        if not self._is_setup:
            return
        try:
            self._close_event.set()
            for w in self._workers:
                w.join(timeout=MP_WORKER_TIMEOUT)
            for q in self._data_queues:
                q.cancel_join_thread()
                q.close()
            for q in self._dump_queues:
                q.cancel_join_thread()
                q.close()
        finally:
            for w in self._workers:
                if w.is_alive():
                    w.terminate()
            self._is_setup = False

    def put_load(self, items: list, record_id: int, load_fn: callable, consumer_id: int) -> bool:
        try:
            for i, item in enumerate(items):
                self._data_queues[self.worker_queue_cycle].put((item, i, record_id, load_fn, consumer_id), block=False)
        except queue.Full:
            return False
        finally:
            self.worker_queue_cycle = (self.worker_queue_cycle + 1) % self.num_workers
        return True
    
    def get_load(self, consumer_id):
        if consumer_id not in self.consumer_load_queues:
            return None
        try:
            result, record_id = self.consumer_load_queues[consumer_id].get(False)
            if result is None:
                return None, record_id
            t, index = result
            t_clone = t.clone()
            del t
            return (t_clone, index), record_id
        except queue.Empty:
            return None

    def put_dump(self, data: any, item_key: str, record_id: int, dump_fn: callable, consumer_id: int):
        self._dump_queues[self.worker_queue_cycle].put((data, item_key, record_id, dump_fn, consumer_id), block=False)
        self.worker_queue_cycle = (self.worker_queue_cycle + 1) % self.num_workers

    def get_dump(self, consumer_id):
        if consumer_id not in self.consumer_dump_queues:
            return None
        try:
            record_id = self.consumer_dump_queues[consumer_id].get(False)
            return record_id
        except queue.Empty:
            return None
