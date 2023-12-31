import sys, os
from mitmproxy.tools.main import mitmdump

def __main__():
    current_dir = os.path.dirname(os.path.realpath(__file__))    
    args = [*sys.argv[1:], '-s', '"%s"' % os.path.join(current_dir,'mitm.py')]
    print('running mitmdump with args:', *args)
    mitmdump(args=args)

if __name__ == "__main__":
    __main__()
    sys.exit(0)
