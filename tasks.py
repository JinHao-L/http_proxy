import traceback
import socket

from threading import Thread, Event
from exceptions import HTTPException
from packets import RequestPacket, ResponsePacket, ErrorResponsePacket
from connections import ThreadSafeConnections
from logger import log

BUFFER_SIZE = 65536

class ProxyTask(Thread):
  def __init__(self, addr, client, connections, filters):
    Thread.__init__(self)
    self.addr = addr
    self.client = client
    self.connections = connections
    self.filters = filters

  def run(self):
    self.log("[*] New connection from %s:%s" % self.addr)
    try:
      data = self.client.recv(BUFFER_SIZE)
      if not data:
        return
      while (data.find(b'\r\n\r\n') == -1):
        data += self.client.recv(BUFFER_SIZE)

      request, err = self.parse_packet(self.client, data, RequestPacket)

      # error handled all together at the bottom segment
      if (err):
        self.handleError(err)
        return

      self.log("[-->]", request.protocol_line().decode())
  
      # Identify domain and port to connect
      host, port = request.get_host_n_port()
      origin = request.headers[b'Host'].decode()

      try:
        server = self.connections.start(origin, host, port)
      except socket.gaierror:
        traceback.print_exc()
        self.handleError(HTTPException(404, 'Not Found'))
        return
      except socket.herror:
        traceback.print_exc()
        self.handleError(HTTPException(404, 'Not Found'))
        return
      
      try:
        server.send(request.encode())
      except socket.error:
        traceback.print_exc()
        # recreate the socket and try reconnect
        try:
          server = self.connections.restart(origin, host, port)
          server.send(request.encode())
        except socket.error:
          traceback.print_exc()
          self.handleError(err)
          return
    
      data = b''
      while data.find(b'\r\n\r\n') == -1:
        data += server.recv(BUFFER_SIZE)

      response, err = self.parse_packet(server, data, ResponsePacket)

      # By default connection kept open
      if (b'close' in [request.headers.get(b'Connection'), response and response.headers.get(b'Connection')]):
        self.connections.close(origin, host, port, len(response.body))
      else:
        self.connections.release(origin, host, port, len(response.body))

      if (err):
        traceback.print_exc()
        self.handleError(err)
        return

      self.client.send(response.encode())
      self.log("[<--]", response.protocol_line().decode())

    except HTTPException as e:
      traceback.print_exc()
      self.handleError(e)
    except socket.timeout:
      traceback.print_exc()
      self.handleError(HTTPException(504, 'Gateway Timeout'))
    except KeyboardInterrupt:
      traceback.print_exc()
      pass
    except Exception:
      # Unknown exception
      traceback.print_exc()
      self.handleError(HTTPException(500, 'Internal Server Error'))
    finally:
      self.log("[*] Close connection from %s:%s" % self.addr)
      self.client.close()

  def handleError(self, http_err):
      self.log(http_err)
      res = ErrorResponsePacket(http_err.code, http_err.message)
      self.client.send(res.encode())

  def parse_packet(self, conn, data, pkt_cls_type):
    head, body = data.split(b'\r\n\r\n', 1)

    try:
      packet = pkt_cls_type(head)

      # Get related content body
      if (b'Content-Length' in packet.headers):
        try:
          body_len = int(packet.headers[b'Content-Length'])
        except ValueError:
          traceback.print_exc()
          raise HTTPException(400, 'Bad Request')

        while(len(body) < body_len):
          body += conn.recv(body_len - len(body))
        packet.set_content(body[:body_len])

      elif (b'Transfer-Encoding' in packet.headers and b'chunked' in [x.strip() for x in packet.headers[b'Transfer-Encoding'].split(b',')]):
        while (b'\r\n' not in body):
          body += conn.recv(BUFFER_SIZE)
        chunk_len, body = body.split(b'\r\n', 1)

        full_body = b''
        while (chunk_len != b'0'):
          try:
            chunk_len = int(chunk_len.decode(errors='ignore'), 16)
          except ValueError():
            traceback.print_exc()
            raise HTTPException(400, 'Bad Request')

          while(len(body) < chunk_len):
            body += conn.recv(chunk_len - len(body))
          
          full_body += body[:chunk_len]
          body = body[chunk_len:]

          if (len(body) < 2):
            body += conn.recv(BUFFER_SIZE)
          body = body[2:] # Remove \r\n

          while (b'\r\n' not in body):
            body += conn.recv(BUFFER_SIZE)
          chunk_len, body = body.split(b'\r\n', 1)

        packet.set_content(full_body)

      # Validate packet
      packet.validate()

      return packet, None

    except HTTPException as e:
      return None, e

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

