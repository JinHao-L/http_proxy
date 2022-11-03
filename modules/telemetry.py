import socket
import ssl
from threading import Thread, Lock, Event
from datetime import datetime
from typing import Dict

from modules.logger import log

class TeleRecord():
  def __init__(self, origin):
    self.lock = Lock()
    self.origin = origin
    self.telemetry = 0
    self.last_updated = datetime.now().timestamp()

  def add_telemetry(self, size):
    with self.lock:
      self.telemetry += size
      self.last_updated = datetime.now().timestamp()

  def is_idle(self):
    return not self.lock.locked() and self.last_updated + 30 < datetime.now().timestamp()

  def __str__(self):
    return f"{self.origin}, {self.telemetry}"


class TelemetryStore():
  def __init__(self):
    self.store: Dict[TeleRecord] = dict()
    self.db_lock = Lock()

  def update(self, origin, size=0):
    with self.db_lock:
      record = self.store.get(origin)
      if not record:
        record = TeleRecord(origin)
        self.store[origin] = record

    if size:
      record.add_telemetry(size)

  def close(self):
    # Force release lock
    if (self.db_lock.locked()):
      self.db_lock.release()

    with self.db_lock:
      for record in self.store.values():
        record.lock.acquire()
        if record.telemetry:
          print(record)

  def routine(self):
    """Clean up inactive telemetry"""
    for record in list(self.store.values()):
      if record.is_idle():
        with record.lock:
          with self.db_lock:
            del self.store[record.origin]
          if record.telemetry:
            print(record)
  
  def __str__(self):
    return "\n".join([str(x) for x in self.store.values()])


class TelemetryTask(Thread):
  def __init__(self, telemetry, freq=1):
    Thread.__init__(self)
    self.freq = freq
    self.stopped = Event()
    self.telemetry = telemetry

  def run(self):
    while not self.stopped.wait(self.freq):
      self.telemetry.routine()

  def stop(self):
    self.stopped.set()
    self.telemetry.close()

