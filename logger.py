import sys

def log(*msg):
  if ("-v" in sys.argv):
    print(*msg)