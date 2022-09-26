import eventlet
#eventlet.monkey_patch(all=True, os=False, select=False, socket=False, thread=False, time=False)
eventlet.monkey_patch()

import json
import threading
import sys
import select
import base64
import argparse
import cmd2
import subprocess
import os

import socketio
from tqdm import tqdm

parser = argparse.ArgumentParser(description='Run SDC tools for server')
parser.add_argument('--endpoint', type=str, default=':5000', help='Connect to endpoint')
parser.add_argument('--generate_silifuzz_corpus', type=bool, default=True, help='Generate silifuzz corpus')
parser.add_argument('--generate_silifuzz_corpus_threads', type=int, default=os.cpu_count(), help='Num of generate silifuzz corpus threads')
args = parser.parse_args()
endpoint = args.endpoint

sio = socketio.Server()
app = socketio.WSGIApp(sio)

sids = set()
ip_to_sid = {}
sid_to_ip = {}
sid_to_progress = {}
mac_to_sid = {}
sid_to_mac = {}

class State:
    def __init__(self):
        self.cpu_check_timeout = 60 * 15
        self.dcdiag_timeout = 60 * 15
        self.silifuzz_timeout = 60 * 60 * 1

state = State()

@sio.event
def connect(sid, environ):
    print(f'[{sid}] Connect from {environ["REMOTE_ADDR"]}')
    sio.save_session(sid, environ)

    address = environ['REMOTE_ADDR']
    sids.add(sid)
    ip_to_sid[address] = sid
    sid_to_ip[sid] = address

    # Set the timeout first
    j = {
        'cpu_check': state.cpu_check_timeout,
        'dcdiag': state.dcdiag_timeout,
        'silifuzz': state.silifuzz_timeout,
    }
    sio.emit('update_timeout_request', j)

@sio.event
def disconnect(sid):
    ip = sid_to_ip[sid]
    mac = sid_to_mac.get(sid)
    print(f'[{sid}] Disconnect from {ip} {mac}')

    sids.remove(sid)
    if ip in ip_to_sid:
        del ip_to_sid[ip]
    del sid_to_ip[sid]

    if mac in mac_to_sid:
        del mac_to_sid[mac]
    if mac:
        del sid_to_mac[sid]

@sio.event
def send_system_info(sid, data):
    system_info = data['system_info']
    mac = system_info['System Information']['Mac-Address']
    mac_to_sid[mac] = sid
    sid_to_mac[sid] = mac
    
    

write_lock = threading.Lock()

@sio.event
def command_completed(sid, data):
    status = data['status']
    data_str = json.dumps(data, indent=2)
    #print(data_str)
    with write_lock:
        with open('results.txt', 'a+') as f:
            f.write(data_str + '\n')

    '''
    if status != 'success' and status != 'timeout':
        data_str = json.dumps(data, indent=2)
        #print(data_str)
        with open('results.txt', 'a+') as f:
            f.write(data_str + '\n')
    '''
    #print('message ', data_str)

@sio.event
def run_command_response(sid, data):
    if data['status'] == 'success':
        print('\n')
        print(f'[{sid}] Run command response success: ')
        print('=' * 40)
        print(data['stdout'])
        print('=' * 40)
    else:
        print(f'[{sid}] Run command response error: ')
        print('=' * 40)
        print(data)
        print('=' * 40)

@sio.event
def transfer_to_response(sid, data):
    print('\n')
    if data['status'] == 'success':
        print(f'[{sid}] Transfer command response success: ', data['filename'])
    else:
        print(f'[{sid}] Transfer command response error: ',  data['filename'], data['error'])

@sio.event
def transfer_from_response(sid, data):
    print('\n')
    if data['status'] == 'success':
        print(f'[{sid}] Transfer command response success: ', data['filename'])
        filename = data['filename']
        b64_data = data['b64_data']
        data = base64.b64decode(b64_data)
        with open('transfer_data', 'wb+') as f:
            f.write(data)
    else:
        print(f'[{sid}] Transfer command response error: ',  data['filename'], data['error'])

@sio.event
def query_progress_response(sid, data):
    current = data['current']
    final = data['final']
    sid_to_progress[sid] = data

@sio.event
def update_corpus_response(sid, data):
    if data['status'] == 'success':
        print(f'[{sid}] Updated corpus response successfully')
    elif data['status'] == 'error':
        print(f'[{sid}] Updated corpus response error {data["error"]}')

@sio.event
def update_timeout_response(sid, data):
    if data['status'] == 'success':
        print(f'[{sid}] Updated timeout response successfully')
    elif data['status'] == 'error':
        print(f'[{sid}] Updated timeout response error {data["error"]}')

class Shell(cmd2.Cmd):
    intro = 'Welcome to SDCBench server'
    prompt = '(SDCBench)'

    numbers = ['0', '1', '2', '3', '4']
    alphabet = ['a', 'b', 'c', 'd']

    parser = cmd2.Cmd2ArgumentParser()
    parser.add_argument("type", choices=['numbers', 'alphabet'])
    parser.add_argument("value")
    @cmd2.with_argparser(parser)
    def do_list(self, args):
        self.poutput(args.value)

    @cmd2.with_argument_list
    def do_command(self, args):
        sio.emit('run_command_request', args)

    @cmd2.with_argument_list
    def do_command_specific(self, args):
        if len(args) > 0:
            mac = args[0]
            sid = mac_to_sid.get(mac)
            if sid:
                sio.emit('run_command_request', args[1:], to=sid)
            else:
                print(f'sid for mac {mac} does not exist')

    parser = cmd2.Cmd2ArgumentParser()
    parser.add_argument('mac')
    parser.add_argument('filename')
    @cmd2.with_argparser(parser)
    def do_transfer_to(self, args):
        mac = args.mac
        filename = args.filename
        try:
            with open(filename, 'rb') as f:
                data = f.read()
                b64_data = base64.b64encode(data)
                j = {
                    'filename': filename,
                    'b64_data': b64_data
                }
                sio.emit('transfer_to_request', j)
        except Exception as e:
            print(e)
    
    parser = cmd2.Cmd2ArgumentParser()
    parser.add_argument('mac')
    parser.add_argument('filename')
    @cmd2.with_argparser(parser)
    def do_transfer_from(self, args):
        mac = args.mac
        filename = args.filename
        sid = mac_to_sid.get(mac)
        if sid:
            filename = args[1]
            sio.emit('transfer_from_request', {'filename': filename}, to=sid)
        else:
            print(f'sid for address {remote_address} does not exist')
    
    @cmd2.with_argument_list
    def do_p(self, args):
        # Get initial progress
        sid_to_t = {}
        def refresh_t():
            i = 0
            for sid, p in sid_to_progress.items():
                ip = sid_to_ip.get(sid)
                if ip is None:
                    continue
                mac = sid_to_mac.get(sid)
                if mac is None:
                    continue
                t = tqdm(range(int(p['final'])), desc=f'[{sid}] [{ip}] [{mac}] Iteration {p["iter"]}: {" ".join(p["command"])}', position=i, leave=False, bar_format='{desc:70}: {percentage:3.0f}%|{bar}{r_bar}')
                t.update(int(p['current']))
                sid_to_t[sid] = t
                i += 1
        refresh_t()
                
        while True:
            i, o, e = select.select([sys.stdin], [], [], 1)
            if i:
                l = sys.stdin.readline().strip()
                if l == 'q':
                    print('exited progress')
                    break

            sio.emit('query_progress_request', {})

            if len(sid_to_t) != len(sid_to_progress):
                refresh_t()

            for sid, t in sid_to_t.items():
                p = sid_to_progress.get(sid)
                if p:
                    ip = sid_to_ip.get(sid)
                    if ip is None:
                        continue
                    mac = sid_to_mac.get(sid)
                    if mac is None:
                        continue
                    current = int(p['current'])
                    final = int(p['final'])
                    t.update(current - t.n)
                    t.set_description(f'[{sid}] [{ip}] [{mac}] Iteration {p["iter"]}: {" ".join(p["command"])}')
                    t.clear()
                    t.refresh()
            
    parser = cmd2.Cmd2ArgumentParser()
    parser.add_argument('filename')
    @cmd2.with_argparser(parser)
    def do_update_corpus(self, args):
        filename = args.filename
        try:
            with open(filename, 'rb') as f:
                data = f.read()
                b64_data = base64.b64encode(data)
                j = {
                    'b64_data': b64_data
                }
                sio.emit('update_corpus_request', j)
        except Exception as e:
            print(e)
    
    parser = cmd2.Cmd2ArgumentParser()
    parser.add_argument('cpu_check_timeout', type=float)
    parser.add_argument('dcdiag_timeout', type=float)
    parser.add_argument('silifuzz_timeout', type=float)
    @cmd2.with_argparser(parser)
    def do_update_timeout(self, args):
        state.cpu_check_timeout = args.cpu_check_timeout
        state.dcdiag_timeout = args.dcdiag_timeout
        state.silifuzz_timeout = args.silifuzz_timeout
        try:
            j = {
                'cpu_check': state.cpu_check_timeout,
                'dcdiag': state.dcdiag_timeout,
                'silifuzz': state.silifuzz_timeout,
            }
            sio.emit('update_timeout_request', j)
        except Exception as e:
            print(e)

def generate_silifuzz_corpus_worker():
    while args.generate_silifuzz_corpus:
        silifuzz_corpus_path = 'tools/silifuzz.corpus'
        silifuzz_corpus_path_xz = f'{silifuzz_corpus_path}.xz'
        silifuzz_num_runs = 100000
        #silifuzz_num_runs = 1
        p = subprocess.Popen(f'python3 tools/silifuzz_tools/generate_silifuzz_corpus.py --num_runs={silifuzz_num_runs} --corpus_output={silifuzz_corpus_path} --j={args.generate_silifuzz_corpus_threads} --corpus_save_dir="../../saved_corpus"', shell=True, cwd=os.getcwd())
        p.communicate()
        try:
            with open(silifuzz_corpus_path_xz, 'rb') as f:
                data = f.read()
                b64_data = base64.b64encode(data)
                j = {
                    'b64_data': b64_data
                }
                sio.emit('update_corpus_request', j)
        except Exception as e:
            print(e)


def get_input():
    s = Shell()
    def raw_input(message):
        #sys.stdout.write(message)

        select.select([sys.stdin], [], [])
        return sys.stdin.readline()
    while True:
        s.preloop()
        l = raw_input('(SDCBench) ')
        l = l.rstrip()

        #l = s.tokens_for_completion(l, 0, 0, False)
        #print(l)
        s.runcmds_plus_hooks([l])
        s.postloop()
                
if __name__ == '__main__':
    t = threading.Thread(target=get_input)
    t.start()
    t = threading.Thread(target=generate_silifuzz_corpus_worker)
    t.start()
    host, port = endpoint.split(':')
    port = int(port)
    eventlet.wsgi.server(eventlet.listen((host, port)), app)
