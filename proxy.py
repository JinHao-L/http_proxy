#!/usr/bin/python3
import sys
import socket
from logger import log

from connections import ThreadSafeConnections
from tasks import ProxyTask, TelemetryTask

def main(argv):
  if (len(argv) < 3):
    print('usage: proxy.py <port> <image-flag> <attack-flag>')
    print('[*] Error: Insufficient argument')
    sys.exit(2)

  try:
    port = int(argv[0])
  except Exception:
    print('usage: proxy.py <port> <image-flag> <attack-flag>')
    print('[*] Error: invalid port: [ %s ]' % argv[0])
    sys.exit(2)

  filters = []
  image_sub_flag = argv[1] == 1
  attack_flag = argv[1] == 1

  try:
    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy.bind(('', port))
    proxy.listen()
    log("[*] Proxy listening on port [ %s ]" % port)
  except Exception as e:
    log("[*] Error: Failed to initialise socket")
    print(e)
    sys.exit(2)

  connections = ThreadSafeConnections()
  threads = []
  
  telemetry = TelemetryTask(connections)
  telemetry.daemon = True
  telemetry.start()

  while True:
    try:
      client, addr = proxy.accept()
      task = ProxyTask(addr, client, connections, filters)
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