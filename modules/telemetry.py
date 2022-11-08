import socket
from threading import Thread, Lock, Event
from datetime import datetime
from typing import Dict

from modules.logger import log

class TeleRecord():
  def __init__(self, origin):
    self.lock = Lock()
    self.origin = origin
    self.telemetry = 0
    self.num_active_conn = 0

  def add_active_conn(self, size):
    with self.lock:
      self.num_active_conn += size

  def add_telemetry(self, size):
    with self.lock:
      self.telemetry += size

  def is_idle(self):
    return not self.lock.locked() and self.num_active_conn == 0

  def __str__(self):
    return f"{self.origin}, {self.telemetry}"


class TelemetryStore():
  def __init__(self):
    self.store: Dict[TeleRecord] = dict()
    self.db_lock = Lock()

  def start(self, origin):
    with self.db_lock:
      record = self.store.get(origin)
      if not record:
        record = TeleRecord(origin)
        self.store[origin] = record

    record.add_active_conn(1)

  def update(self, origin, size=0):
    if not size:
      return

    record = self.store.get(origin)
    if not record: 
      return
    self.store.get(origin).add_telemetry(size)

  def close(self, origin):
    record = self.store.get(origin)
    if not record: 
      return

    record.add_active_conn(-1)

    if record.is_idle():
      with record.lock:
        with self.db_lock:
          del self.store[origin]
        if record.telemetry:
          print(record)

  def close_all(self):
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

