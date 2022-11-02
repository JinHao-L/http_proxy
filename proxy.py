#!/usr/bin/python3
import sys
import socket
from typing import List

from connections import ThreadSafeConnections
from tasks import ProxyTask, TelemetryTask
from logger import log
from extensions import *

def main(argv):
  if (len(argv) < 3):
    print('usage: proxy.py <port> <image-flag> <attack-flag>')
    print('[*] Error: Insufficient argument')
    sys.exit(2)

  try:
    port = int(argv[0])
      
    # Install extensions
    extensions: List[PacketTransformer] = []
    if (int(argv[1])):
      extensions.append(ImageChangeTransformer("https://www.comp.nus.edu.sg/~chanmc/change.jpg"))
    if (int(argv[2])):
      extensions.append(AttackTransformer("You are being attacked"))

  except Exception:
    print('usage: proxy.py <port> <image-flag> <attack-flag>')
    print('<port> <image-flag> <attack-flag> must be valid integers')
    sys.exit(2)

  # Start proxy listener
  try:
    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy.bind(('', port))
    proxy.listen()
    log("[*] Proxy listening on port [ %s ]" % port)
  except Exception as e:
    log("[*] Error: Failed to initialise socket")
    print(e)
    sys.exit(2)

  # Create shared storage
  connections = ThreadSafeConnections()
  threads: List[ProxyTask] = []

  # Create telemetry task which runs every second
  telemetry = TelemetryTask(connections, 1)
  telemetry.daemon = True
  telemetry.start()

  # Start new proxy task for each proxy request
  while True:
    try:
      client, addr = proxy.accept()
      task = ProxyTask(addr, client, connections, extensions)
      task.daemon = True
      threads.append(task)
      task.start()

    except KeyboardInterrupt:
      log("\n[*] Stopping proxy...")
      proxy.close()
      log('[*] Terminating telemtry routine task...')
      telemetry.stop()
      log("[*] Closing open proxy ports...")
      for task in threads:
        task.terminate()
      log("[*] Closing open HTTP connections...")
      connections.close_all()
      log("[*] Graceful Shutdown")
      sys.exit(1)

if __name__ == "__main__":
   main(sys.argv[1:])