import traceback

from threading import Thread, Event
from exceptions import HTTPException
from packets import RequestPacket, ResponsePacket, ErrorResponsePacket
from connections import ThreadSafeConnections
from logger import log

class ProxyTask(Thread):
  def __init__(self, addr, client, connections, filters):
    Thread.__init__(self)
    self.addr = addr
    self.client = client
    self.connections = connections
    self.filters = filters

  def run(self):
    self.log("[*] New connection from %s:%s" % self.addr)
    data = b''
    while (True):
      data += self.client.recv(65535)
      if len(data) == 0 or data.find(b'\r\n\r\n') != -1:
        break

    try:
      request, data, err = self.parse_packet(self.client, data, RequestPacket)

      try:
        # error handled all together at the bottom segment
        if (err):
          raise err
    
        # Identify domain and port to connect
        host, port = request.get_host_n_port()
        origin = request.headers[b'Host'].decode()

        try:
          server = self.connections.start(origin, host, port)
          server.send(request.encode())
        except:
          # recreate the socket and try reconnect
          try:
            server = self.connections.restart(origin, host, port)
            server.send(request.encode())
          except:
            traceback.print_exc()
            raise HTTPException(404, 'Not Found')
        
        self.log("[-->]" + request.protocol_line().decode())
      
        data = b''
        response = None

        data = server.recv(65535)
        while data.find(b'\r\n\r\n') == -1:
          data += server.recv(65535)

        response, data, err = self.parse_packet(server, data, ResponsePacket)
        if (err):
          traceback.print_exc()
          raise err

        self.client.send(response.encode())
        self.log("[<--]" + response.protocol_line().decode())

        # By default connection kept open
        if (b'close' in [request.headers.get(b'Connection'), response and response.headers.get(b'Connection')]):
          self.connections.close(origin, host, port, response.get_content_length())
        else:
          self.connections.release(origin, host, port, response.get_content_length())

      except HTTPException as e:
        res = ErrorResponsePacket(e.code, e.message)
        self.log(f"{e.code} {e.message}")
        self.client.send(str(res).encode())
      except Exception as e:
        # Unknown exception
        traceback.print_exc()
        res = ErrorResponsePacket(500, 'Internal Server Error')
        self.log('500 Internal Server Error')
        self.client.send(str(res).encode())
    finally:
      self.log("[*] Close connection from %s:%s" % self.addr)
      self.client.close()

  def parse_packet(self, conn, data, pkt_cls_type):
    head, next_data = data.split(b'\r\n\r\n', 1)

    try:
      packet = pkt_cls_type(head)

      # Get related content body
      body_len = packet.get_content_length()
      
      if len(next_data) < body_len:
        while(len(next_data) < body_len):
          next_data += conn.recv(body_len - len(next_data))
        packet.set_content(next_data)
        next_data = b''
      else:
        packet.set_content(next_data[:body_len])
        next_data = next_data[body_len:]
      
      # Validate packet
      packet.validate()

      return packet, next_data, None

    except HTTPException as e:
      return None, next_data, e

  def log(self, *message):
    log("%s:%s -:" % (self.addr[0], self.addr[1]), *message)

  def terminate(self):
    self.client.close()


class TelemetryTask(Thread):
  def __init__(self, connections):
    Thread.__init__(self)
    self.stopped = Event()
    self.connections = connections

  def run(self):
    while not self.stopped.wait(1):
      self.connections.routine()

  def stop(self):
    self.stopped.set()

