import socket
import ssl
from threading import Thread, Lock
from datetime import datetime
from typing import Dict

from logger import log

class ConnectionRecord():
  def __init__(self, conn, origin):
    self.lock = Lock()
    self.conn = conn
    self.origin = origin
    self.telemetry = 0
    self.last_access = datetime.now().timestamp()
    log("[**] Opening HTTP connection to %s" % self.origin)

  def update_access(self):
    self.last_access = datetime.now().timestamp()

  def is_conn_active(self):
    return self.lock.locked() or self.last_access + 30 > datetime.now().timestamp()

  def clean_up(self):
    if (self.lock.locked()):
      self.lock.release()
    if (self.telemetry):
      print(f'{self.origin}, {self.telemetry}')
    log("[**] Closing HTTP connection to %s" % self.origin)
    self.conn.close()


class ThreadSafeConnections():
  def __init__(self):
    self.record: Dict[ConnectionRecord] = dict()
    self.lock = Lock()

  def get_key(self, host_port):
    return "%s:%s" % host_port

  def start(self, origin, host_port):
    index = self.get_key(host_port)
    self.lock.acquire()
    if index in self.record:
      self.record[index].lock.acquire()
      self.lock.release()
      self.record[index].update_access()
      return self.record[index].conn

    server = self.connect(host_port)
    self.record[index] = ConnectionRecord(server, origin)
    self.record[index].lock.acquire()
    self.lock.release()
    self.record[index].update_access()
    return self.record[index].conn

  def restart(self, host_port):
    server = self.connect(host_port)

    index = self.get_key(host_port)
    with self.lock:
      rec = self.record[index]
      rec.conn.close()
      rec.conn = server
    return server

  def connect(self, host_port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.settimeout(30) # timeout if no response
    server.connect(host_port)

    if(host_port[1] == 443):
      context = ssl.create_default_context()
      server = context.wrap_socket(server, server_hostname=host_port[0])

    return server

  def release(self, host_port, telemetry = 0):
    index = self.get_key(host_port)
    if (index in self.record):
      self.record[index].update_access()
      self.record[index].telemetry += telemetry
      self.record[index].lock.release()

  def close(self, host_port, telemetry = 0):
    index = self.get_key(host_port)
    with self.lock:
      rec: ConnectionRecord = self.record.pop(index)
    
    # Make sure all existing requests are completed
    rec.lock.acquire()
    rec.telemetry += telemetry
    rec.clean_up()

  def close_all(self):
    # Force release lock
    if (self.lock.locked()):
      self.lock.release()
    
    with self.lock:
      while(len(self.record) > 0):
        origin, rec = self.record.popitem()
        rec.clean_up()

  def routine(self):
    """Clean up inactive connections"""
    for origin in list(self.record.keys()):
      rec = self.record[origin]
      if not rec.is_conn_active():
        # Only stop connection that are unused and idle
        rec.lock.acquire()
        with self.lock:
          del self.record[origin]
        rec.clean_up()
