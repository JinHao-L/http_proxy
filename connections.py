from threading import Thread, Lock
from datetime import datetime
from logger import log
import socket

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
    self.record[origin] = ConnectionRecord(server)
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
    log("Shared: [*] Opening HTTP connection to %s:%s" % (host, port))
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.connect((host, port))
    return server

  def release(self, origin, host, port, telemetry = 0):
    with self.lock:
      if (origin in self.record):
        self.record[origin].lock.release()
        self.record[origin].update_access()
        self.record[origin].telemetry += telemetry

  def close(self, origin, host, port, telemetry = 0):
    log("Shared: [*] Closing HTTP connection to %s:%s" % (host, port))
    with self.lock:
      rec = self.record.pop(origin)
    
    # Print telemetry data
    print(f'{origin}, {rec.telemetry + telemetry}')
    rec.clean_up()

  def close_all(self):
    if (self.lock.locked()):
      self.lock.release()
    with self.lock:
      while(len(self.record) > 0):
        origin, rec = self.record.popitem()
        log("[*] Closing HTTP connection to %s" % origin)

        # Print telemetry data
        if (rec.telemetry): 
          print(f'{origin}, {rec.telemetry}')
        rec.clean_up()

  def routine(self):
    for origin in list(self.record.keys()):
      rec = self.record[origin]
      if rec.is_conn_inactive():
        rec.lock.acquire()
        with self.lock:
          del self.record[origin]
        if (rec.telemetry): 
          print(f'{origin}, {rec.telemetry}')
        rec.clean_up()


class ConnectionRecord():
  def __init__(self, conn):
    self.lock = Lock()
    self.conn = conn
    self.telemetry = 0
    self.last_access = datetime.now().timestamp()

  def update_access(self):
    self.last_access = datetime.now().timestamp()

  def is_conn_inactive(self):
    return not self.lock.locked() and self.last_access + 30 < datetime.now().timestamp()

  def clean_up(self):
    if (self.lock.locked()):
      self.lock.release()
    self.conn.close()

