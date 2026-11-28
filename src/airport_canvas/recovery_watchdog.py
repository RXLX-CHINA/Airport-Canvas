"""Out-of-process ACP recovery. Only committed snapshots cross the pipe."""
import copy
import json
import os
from pathlib import Path
from queue import Empty, Queue
import subprocess
import sys
from threading import Condition, Thread
from time import monotonic


class RecoveryWatchdog:
    def __init__(self, target):
        self.target = target
        self.condition = Condition()
        self.pending = None
        self.heartbeat = monotonic()
        self.closed = False
        self.flush = False
        self.failed = False
        self.thread = Thread(target=self.run, name='ACP recovery sender')
        self.thread.start()

    def publish(self, data):
        snapshot = copy.deepcopy(data)
        with self.condition:
            self.pending = snapshot
            self.condition.notify()

    def beat(self, flush=False):
        with self.condition:
            self.heartbeat = monotonic()
            self.flush |= flush
            self.condition.notify()

    def stop(self):
        with self.condition:
            self.closed = True
            self.pending = None
            self.condition.notify()

    def run(self):
        process = None
        try:
            entry = [] if '__compiled__' in globals() else [str(Path(__file__).with_name('gui.py'))]
            process = subprocess.Popen(
                [sys.executable, *entry, '--recovery-watchdog', str(self.target)],
                stdin=subprocess.PIPE, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            previous = {}
            last_beat = None
            while True:
                with self.condition:
                    self.condition.wait_for(lambda: self.closed or self.pending is not None
                                            or self.heartbeat != last_beat or self.flush)
                    closed, snapshot, last_beat, flush = (
                        self.closed, self.pending, self.heartbeat, self.flush)
                    self.pending = None
                    self.flush = False
                message = {'heartbeat': last_beat, 'flush': flush, 'close': closed}
                if snapshot is not None:
                    message['changes'] = {k: v for k, v in snapshot.items()
                                          if k not in previous or previous[k] != v}
                    message['removed'] = list(previous.keys() - snapshot.keys())
                    previous = snapshot
                process.stdin.write(json.dumps(message, ensure_ascii=False,
                                                allow_nan=False).encode('utf-8') + b'\n')
                process.stdin.flush()
                if closed:
                    break
        except (OSError, ValueError):
            self.failed = True
        finally:
            if process is not None:
                try:
                    process.stdin.close()
                except OSError:
                    self.failed = True
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def watch(target, timeout=15):
    from PySide6.QtCore import QLockFile
    from airport_scene import MAX_PROJECT_BYTES
    target = Path(target)
    lock = QLockFile(str(target) + '.lock')
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        return 1
    messages = Queue()

    def read_messages():
        try:
            for line in sys.stdin.buffer:
                messages.put(json.loads(line))
        finally:
            messages.put(None)

    Thread(target=read_messages, daemon=True).start()
    data = {}
    heartbeat = monotonic()
    dirty = False

    def save():
        nonlocal dirty
        if not dirty:
            return
        temp = target.with_suffix('.tmp')
        try:
            payload = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
            if len(payload) > MAX_PROJECT_BYTES:
                return
            with temp.open('wb') as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            temp.replace(target)
            dirty = False
        except OSError:
            return
        finally:
            temp.unlink(missing_ok=True)

    try:
        while True:
            try:
                deadline = max(.25, heartbeat + timeout - monotonic()) if dirty else None
                message = messages.get(timeout=deadline)
            except Empty:
                if monotonic() - heartbeat >= timeout:
                    save()
                continue
            if message is None:
                save()
                return 0
            if message['close']:
                target.unlink(missing_ok=True)
                return 0
            dirty |= bool(message.get('changes') or message.get('removed'))
            data.update(message.get('changes', {}))
            for key in message.get('removed', ()):
                data.pop(key, None)
            heartbeat = message['heartbeat']
            if message['flush']:
                save()
    finally:
        lock.unlock()
