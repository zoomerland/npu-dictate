"""Background availability checks for settings; workers never touch widgets."""
import threading
import time


class ModelAvailabilityRefresh:
    def __init__(self, publish, scanner, *, interval=5.0, clock=time.monotonic):
        self.publish, self.scanner, self.interval, self.clock = publish, scanner, interval, clock
        self.generation = 0
        self.active = self.pending = False
        self.running = None
        self.snapshot = None
        self.next_start = 0.0

    def open(self):
        self.close()
        self.active = self.pending = True
        self.snapshot = None
        self.next_start = 0.0
        self.tick()

    def close(self):
        self.generation += 1
        self.active = self.pending = False
        self.snapshot = None
        if self.running:
            self.running[1].set()

    def request(self):
        if self.active:
            self.pending = True

    def tick(self):
        if not self.active or not self.pending or self.running or self.clock() < self.next_start:
            return False
        generation, cancel = self.generation, threading.Event()
        self.running = (generation, cancel)
        self.pending = False
        self.next_start = self.clock() + self.interval
        scanner, publish = self.scanner, self.publish

        def work():
            try:
                result = scanner(cancel)
            except Exception:
                result = None
            publish(("model_availability", generation, result))

        try:
            threading.Thread(target=work, name="settings-model-availability", daemon=True).start()
        except RuntimeError:
            self.running = None
            self.snapshot = {}
            return True
        return False

    def complete(self, generation, result):
        if not self.running or generation != self.running[0]:
            return False
        _, cancel = self.running
        self.running = None
        if not self.active or generation != self.generation or cancel.is_set():
            return False
        self.snapshot = dict(result) if result is not None else {}
        return True
