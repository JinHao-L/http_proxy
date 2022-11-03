from urllib.parse import urlparse

from modules.packets import RequestPacket, ResponsePacket

class PacketTransformer():
  """
  Generic installable transformer for packets.
  Inherit and override the method to achieve varying transformation
  """
  def incoming(self, req: RequestPacket) -> RequestPacket:
    return req

  def outgoing(self, res: ResponsePacket) -> ResponsePacket:
    return res


class ImageChangeTransformer(PacketTransformer):
  def __init__(self, image):
    super().__init__()
    self.image = image
    url_seg = urlparse(image)
    if(url_seg.port in [443, 80]):
      self.host = url_seg.hostname
    else:
      self.host = url_seg.netloc

  def incoming(self, req: RequestPacket) -> RequestPacket:
    if (req.url.split(b'.')[-1] in [b'png', b'jpeg', b'jpg', b'ico', b'gif']):
      req.url = self.image.encode()
      req.headers[b'Host'] = self.host.encode()
    return req


class AttackTransformer(PacketTransformer):
  def __init__(self, content = ""):
    super().__init__()
    self.html = """
    <?xml version="1.0" encoding="iso-8859-1"?>
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <title>Hacked</title>
      </head>
      <body>
        <p>{0}</p>
      </body>
    </html>
    """.format(content)

  def incoming(self, req: RequestPacket) -> RequestPacket:
    req.should_forward = False
    return req

  def outgoing(self, res: ResponsePacket) -> ResponsePacket:
    # Transform res to an target output
    res.code = b'200'
    res.status = b'OK'
    res.set_content(self.html.encode())
    res.headers.pop(b'Content-Encoding', None)
    return res

