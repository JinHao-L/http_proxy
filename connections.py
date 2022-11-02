from threading import Thread, Lock
from datetime import datetime
from logger import log
import socket

class ConnectionRecord():
  def __init__(self, conn, origin):
    self.lock = Lock()
    self.conn = conn
    self.origin = origin
    self.telemetry = 0
    self.last_access = datetime.now().timestamp()
    log("Shared     : [*] Opening HTTP connection to %s" % self.origin)

  def update_access(self):
    self.last_access = datetime.now().timestamp()

  def is_conn_active(self):
    return self.lock.locked() or self.last_access + 30 > datetime.now().timestamp()

  def clean_up(self):
    if (self.lock.locked()):
      self.lock.release()
    log("Shared     : [*] Closing HTTP connection to %s" % self.origin)
    self.conn.close()


class ThreadSafeConnections():
  def __init__(self):
    self.record = dict()
    self.lock = Lock()

  def start(self, origin, host, port):
    self.lock.acquire()
    if origin in self.record:
      self.lock.release()
      self.record[origin].lock.acquire()
      self.record[origin].update_access()
      return self.record[origin].conn

    server = self.connect(host, port)
    self.record[origin] = ConnectionRecord(server, origin)
    self.lock.release()

    self.record[origin].lock.acquire()
    self.record[origin].update_access()
    return self.record[origin].conn

  def restart(self, origin, host, port):
    server = self.connect(host, port)

    with self.lock:
      rec = self.record[origin]
      rec.conn.close()
      rec.conn = server
    return server

  def connect(self, host, port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.settimeout(30) # timeout if no response
    server.connect((host, port))
    return server

  def release(self, origin, telemetry = 0):
    with self.lock:
      if (origin in self.record):
        self.record[origin].lock.release()
        self.record[origin].update_access()
        self.record[origin].telemetry += telemetry

  def close(self, origin, telemetry = 0):
    with self.lock:
      rec = self.record.pop(origin)
    
    # Print telemetry data
    print(f'{origin}, {rec.telemetry + telemetry}')
    rec.clean_up()

  def close_all(self):
    # Force release lock
    if (self.lock.locked()):
      self.lock.release()
    
    with self.lock:
      while(len(self.record) > 0):
        origin, rec = self.record.popitem()

        # Print telemetry data
        if (rec.telemetry): 
          print(f'{origin}, {rec.telemetry}')
        rec.clean_up()

  def routine(self):
    """Clean up inactive connections"""
    for origin in list(self.record.keys()):
      rec = self.record[origin]
      if not rec.is_conn_active():
        rec.lock.acquire()
        with self.lock:
          del self.record[origin]
        if (rec.telemetry): 
          print(f'{origin}, {rec.telemetry}')
        rec.clean_up()
