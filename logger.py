import sys
import traceback

def log(*msg):
  if ("-v" in sys.argv):
    print(*msg)

def error_trace():
  if ("-v" in sys.argv):
    traceback.print_exc()