import os,sys
def main_mitm(args):
    from mitmproxy.tools.main import mitmdump
    current_dir = os.path.dirname(os.path.realpath(__file__))    
    args = [*sys.argv[1:], '-s', '"%s"' % os.path.join(os.path.dirname(os.path.dirname(current_dir)),'mitmproxy_sekai_api.py')]
    print('running mitmdump with args:', *args)
    mitmdump(args=args)
