from exceptions import HTTPException
from datetime import datetime
import traceback

class GenericPacket:
  def __init__(self, head, body = b''):
    try:
      # Get first line
      self.protocol, header_str = head.split(b'\r\n', 1)

      # Get header key-val pairs
      self.headers = {}
      for line in  header_str.split(b'\r\n'):
        key, val = line.split(b': ')
        self.headers[key] = val
      
      self.body = body
    except Exception:
      traceback.print_exc()
      raise HTTPException(500, 'Internal Server Error')

  def set_content(self, body):
    self.body = body

    # Does not support chunked encoding
    # Only use content-length
    te = self.headers.get(b'Transfer-Encoding')
    if (te):
      te_values = [x.strip() for x in filter(lambda x: x.strip() != b'chunked', te.split(b","))]
      if (len(te_values) > 0):
        self.headers[b'Transfer-Encoding'] = b', '.join(te_values)
      else:
        del self.headers[b'Transfer-Encoding']
    self.headers[b'Content-Length'] = str(len(body)).encode()

  def validate(self):
    return True

  def protocol_line(self):
    return self.protocol

  def encode(self):
    payload = self.protocol_line() + b'\r\n'
    payload += b'\r\n'.join([k + b': ' + self.headers[k] for k in self.headers])
    payload += b'\r\n\r\n' + self.body
    return payload
  
  def __str__(self):
    return str(self.encode())


class RequestPacket(GenericPacket):
  def __init__(self, head, body = b''):
    try:
      super().__init__(head, body)
      self.method, self.url, self.ver = self.protocol.split(b' ')
    except Exception:
      traceback.print_exc()
      raise HTTPException(400, 'Bad Request')

  def validate(self):
    """Check request packet for any violations"""
    # Mismatched host
    if b'Host' not in self.headers or self.headers[b'Host'] not in self.url:
      raise HTTPException(400, 'Bad Request')

    # Unsupported version
    if self.ver not in [b'HTTP/1.1', b'HTTP/1.0']:
      raise HTTPException(505, 'HTTP Version Not Supported')

    # Unsupported method
    if self.method not in [b'HEAD', b'GET', b'PUT', b'POST', b'DELETE']:
      raise HTTPException(405, 'Method Not Allowed')
  
  def get_host_n_port(self):
    host = self.headers[b'Host'].decode()

    try:
      if (':' in host):
        pos = host.find(':')
        return (host[:pos], int(host[pos + 1:]))
    except Exception:
      traceback.print_exc()
      raise HTTPException(400, 'Bad Request') # no host header or invalid port

    return (host, 443) if self.url.startswith(b'https') else (host, 80)

  def protocol_line(self):
    return self.method + b' ' + self.url + b' ' + self.ver


class ResponsePacket(GenericPacket):
  def __init__(self, head, body = b''):
    try:
      super().__init__(head, body)
      self.ver, self.code, self.status = self.protocol.split(b' ', 2)
    except Exception:
      traceback.print_exc()
      raise HTTPException(500, 'Internal Server Error')

  def protocol_line(self):
    return self.ver + b' ' + self.code + b' ' + self.status


class ErrorResponsePacket:
  def __init__(self, code, message):
    self.code = code
    self.message = message

  def encode(self):
    html = f"""  
    <?xml version="1.0" encoding="iso-8859-1"?>
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <title>{self.code} - {self.message}</title>
      </head>
      <body>
        <h1>{self.code} - {self.message}</h1>
      </body>
    </html>
    """

    res = f'HTTP/1.1 {self.code} {self.message}\r\n'
    res += 'Content-Type: text/html\r\n'
    res += f'Content-Length: {len(html)}\r\n'
    res += 'Connection: close\r\n'
    res += f'Date: {datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")}\r\n\r\n'
    res += html

    return res.encode()

