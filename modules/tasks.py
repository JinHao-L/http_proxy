import socket
import ssl
from typing import List, Tuple
from threading import Thread

from modules.exceptions import HTTPException
from modules.packets import RequestPacket, ResponsePacket, ErrorResponsePacket
from modules.telemetry import TelemetryStore
from modules.logger import log, error_trace
from modules.extensions import PacketTransformer

BUFFER_SIZE = 65536

class ProxyTask(Thread):
  def __init__(self, addr: Tuple[str, int], client: socket.socket, store: TelemetryStore, extensions: List[PacketTransformer]):
    Thread.__init__(self)
    # self.log("[*] New connection from %s:%s" % self.addr)
    self.addr = addr
    self.telemetry = store
    self.extensions = extensions

    self.client = client
    self.server = None
    self.request = None
    self.response = None

  def run(self):
    try:
      # Handle incoming request
      try: 
        data = b''
        while data.find(b'\r\n\r\n') == -1:
          data += self.client.recv(BUFFER_SIZE)

        self.request, err = self.parse_packet(self.client, data, RequestPacket)
      except socket.timeout:
        self.response = ErrorResponsePacket(408, 'Request Timeout')
        self.send_response()
        return

      if (err):
        self.response = ErrorResponsePacket(err.code, err.message)
        self.send_response()
        return

      self.log("[-->]", self.request.protocol_line().decode())

      for mapper in self.extensions:
        self.request = mapper.incoming(self.request)

      # Identify host and port to connect
      host, port = self.request.get_host_n_port()

      if self.request.should_forward:
        try:
          self.server = self.connect(host, port)
        except socket.gaierror:
          self.response = ErrorResponsePacket(404, 'Not Found')
          self.send_response()
          return
        except socket.herror:
          self.response = ErrorResponsePacket(404, 'Not Found')
          self.send_response()
          return
        
        self.server.send(self.request.encode())

        # Handle incoming response
        try: 
          data = b''
          while data.find(b'\r\n\r\n') == -1:
            data += self.server.recv(BUFFER_SIZE)

          self.response, err = self.parse_packet(self.server, data, ResponsePacket)
        except socket.timeout:
          self.response = ErrorResponsePacket(504, 'Gateway Timeout') # Server timeout
          self.send_response()
          return

        if (err):
          error_trace()
          self.response = ErrorResponsePacket(502, 'Bad Gateway') # Server sent bad request
          self.send_response()
          return
      else:
        self.response = ErrorResponsePacket(418, "I'm a teapot") # Don't want to handle this request

      for mapper in self.extensions:
        self.response = mapper.outgoing(self.response)

      self.send_response()

    except HTTPException as e:
      error_trace()
      self.response = ErrorResponsePacket(e.code, e.message)
      self.send_response()
    except Exception:
      # Unknown exception
      error_trace()
      self.response = ErrorResponsePacket(500, 'Internal Server Error')
      self.send_response()
    finally:
      self.terminate()

  def connect(self, host, port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.settimeout(30) # timeout if no response
    server.connect((host, port))

    if(port == 443):
      context = ssl.create_default_context()
      server = context.wrap_socket(server, server_hostname=host)

    return server

  def send_response(self):
    if self.response:
      self.client.send(self.response.encode())
      self.log("[<--]", self.response.protocol_line().decode())

    if self.request and self.response:
      # Telemetry update
      origin = self.request.headers.get(b'Referer') or self.request.url
      self.telemetry.update(origin.decode(), self.response.payload_size())


  def parse_packet(self, conn, data, pkt_cls_type):
    head, body = data.split(b'\r\n\r\n', 1)

    try:
      packet = pkt_cls_type(head)

      # Get related content body
      if (b'Content-Length' in packet.headers):
        try:
          body_len = int(packet.headers[b'Content-Length'])
        except ValueError:
          error_trace()
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
            error_trace()
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
    log("%s:%s  -:" % (self.addr[0], self.addr[1]), *message)

  def terminate(self):
    # self.log("[*] Close connection from %s:%s" % self.addr)
    self.client.close()
    if (self.server):
      self.server.close()
