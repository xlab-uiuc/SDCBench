import eventlet
#eventlet.monkey_patch(all=True, os=False, select=False, socket=False, thread=False, time=False)
eventlet.monkey_patch()

import socketio
import json
import threading
import sys
import select
import base64
from tqdm import tqdm

sio = socketio.Server()
app = socketio.WSGIApp(sio, static_files={
    '/': {'content_type': 'text/html', 'filename': 'index.html'}
})

sids = set()
ip_to_sid = {}
sid_to_ip = {}
sid_to_progress = {}
mac_to_sid = {}
sid_to_mac = {}

@sio.event
def connect(sid, environ):
    print(f'[{sid}] Connect from {environ["REMOTE_ADDR"]}')
    sio.save_session(sid, environ)

    address = environ['REMOTE_ADDR']
    sids.add(sid)
    ip_to_sid[address] = sid
    sid_to_ip[sid] = address

@sio.event
def disconnect(sid):
    ip = sid_to_ip[sid]
    mac = sid_to_mac[sid]
    print(f'[{sid}] Disconnect from {ip} {mac}')

    sids.remove(sid)
    del ip_to_sid[ip]
    del sid_to_ip[sid]

    del mac_to_sid[mac]
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

def get_input():
    def raw_input(message):
        sys.stdout.write(message)

        select.select([sys.stdin], [], [])
        return sys.stdin.readline()
    while True:
        l = raw_input('Input: ')
        l = l.rstrip()
        args = l.split(' ')
        if len(args) >= 1:
            if args[0] == 'command':
                sio.emit('run_command_request', args[1:])
                #for sid in sids:
                #    print('uhh')
                #    sio.emit('run_command_request', {'aa': 'abc'}, to=sid)
            if len(args) > 2:
                if args[0] == 'command_specific':
                    mac = args[1]
                    sid = mac_to_sid.get(mac)
                    if sid:
                        sio.emit('run_command_request', args[2:], to=sid)
                    else:
                        print(f'sid for mac {mac} does not exist')
            if len(args) > 1:
                if args[0] == 'transfer_to':
                    filename = args[1]
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
            if len(args) > 2:
                if args[0] == 'transfer_from':
                    remote_address = args[1]
                    sid = ip_to_sid.get(remote_address)
                    if sid:
                        filename = args[2]
                        sio.emit('transfer_from_request', {'filename': filename}, to=sid)
                    else:
                        print(f'sid for address {remote_address} does not exist')
            if args[0] == 'progress' or args[0] == 'p':
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

                
if __name__ == '__main__':
    t = threading.Thread(target=get_input)
    t.start()
    #eventlet.spawn(func=get_input)
    #eventlet.spawn_after(func=get_input, seconds=1)
    eventlet.wsgi.server(eventlet.listen(('', 5000)), app)
