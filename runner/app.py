from concurrent.futures import thread
import string
import frida
import subprocess
import sys
import argparse
import resource
import psutil
import os
import socketio
import random
import threading
import time
import io
import base64

import system_info

parser = argparse.ArgumentParser(description='Run SDC tools')
parser.add_argument('--timeout', type=float, required=False, default=0, help='Timeout in seconds to run for. Default is 0 (no timeout)')
#parser.add_argument('--sleep_interval', type=float, required=False, default=0, help='Intervals to sleep for between runs')
#parser.add_argument('--cpu_count', type=float, required=False, default=1.0, help='Percentage of cores to use (1.0 = all 0.5 = half)')
parser.add_argument('--endpoint', required=True, default='http://localhost:5000', help='Connect to endpoint')
args = parser.parse_args()

sio = socketio.Client()
sio_lock = threading.Lock()

class State:
    def __init__(self):
        self.cpu_check_command = 'tools/cpu_check'
        if args.timeout != 0:
            self.cpu_check_command = [self.cpu_check_command, f'-t{args.timeout - 1.5}']
        self.dcdiag_command = 'tools/dcdiag'
        self.commands = [self.cpu_check_command, self.dcdiag_command]
        self.command_index = random.randint(0, len(self.commands) - 1)
        self.last_executed_command = ''
        self.last_executed_command_time = 0
        self.iterations = 0
    
    def get_command(self):
        return self.commands[self.command_index]

    def get_next_command(self):
        self.command_index += 1
        if self.command_index >= len(self.commands):
            self.command_index = 0
        command = self.get_command()
        self.iterations += 1
        self.last_executed_command = command
        return command

state = State()

def preexec_fn():
    pid = os.getpid()
    ps = psutil.Process(pid)
    ps.nice(19)
    #resource.setrlimit(resource.RLIMIT_CPU, (1, 1))

def format_bytes(o):
    if o is None:
        return o
    o = o.decode('utf-8')
    o = o.replace("'", '"')
    return o

def run_command(command):
    p = None
    data = {}
    try:
        p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=args.timeout, preexec_fn=preexec_fn)
        data = {
            'status': 'success',
            'command': command,
            'stdout': format_bytes(p.stdout),
            'stderr': format_bytes(p.stderr),
            'code': p.returncode,
        }
    except subprocess.TimeoutExpired as e:
        data = {
            'status': 'timeout',
            'command': command,
            'stdout': format_bytes(e.stdout),
            'stderr': format_bytes(e.stderr),
        }
    except subprocess.CalledProcessError as e:
        data = {
            'status': 'called_process_error',
            'command': command,
            'stdout': format_bytes(e.stdout),
            'stderr': format_bytes(e.stderr),
            'code': e.returncode,
        }
    except Exception as e:
        data = {
            'status': 'general_exception',
            'command': command,
            'exception': str(e),
        }
    return data

def send_sio_message(key, value):
    while True:
        try:
            with sio_lock:
                sio.emit(key, value)
                break
        except Exception as e:
            print('trying to send data to sio, but has exception', e)
            time.sleep(1.0)
            continue


def run_loop():
    while True:
        command = state.get_next_command()
        state.last_executed_command_time = time.monotonic()
        data = run_command(command)
        if command == state.dcdiag_command and data['status'] == 'called_process_error':
            # illegal instruction error, old cpu
            if data['code'] == -4:
                # remove from testing
                state.commands.remove(state.dcdiag_command)
                state.command_index = 0
        data['system_info'] = system_info.get_system_info()
        send_sio_message('command_completed', data)

t = threading.Thread(target=run_loop, args=())
t.start()
#sio.start_background_task(target=run_loop)

@sio.event
def connect():
    print('connection established')
    send_sio_message('send_system_info', {'system_info': system_info.get_system_info()})

@sio.event
def disconnect():
    print('disconnected from server')

@sio.event
def run_command_request(data):
    print('Got run command', data)
    result = run_command(data)
    send_sio_message('run_command_response', result)

@sio.event
def transfer_to_request(data):
    try:
        filename = data['filename']
        b64_data = data['b64_data']
        data = base64.b64decode(b64_data)
        with open(filename, 'wb+') as f:
            f.write(data)
        send_sio_message('transfer_to_response', {
            'status': 'success',
            'filename': filename 
        })
    except Exception as e:
        send_sio_message('transfer_to_response', {
            'status': 'failure',
            'filename': filename, 
            'error': str(e)
        })

@sio.event
def transfer_from_request(data):
    try:
        filename = data['filename']
        try:
            with open(filename, 'rb') as f:
                data = f.read()
                b64_data = base64.b64encode(data)
                j = {
                    'status': 'success',
                    'filename': filename,
                    'b64_data': b64_data
                }
                sio.emit('transfer_from_response', j)
        except Exception as e:
            print(e)
    except Exception as e:
        send_sio_message('transfer_from_response', {
            'status': 'failure',
            'filename': filename, 
            'error': str(e)
        })

@sio.event
def query_progress_request(data):
    time_diff = time.monotonic() - state.last_executed_command_time
    j = {
        'iter': state.iterations,
        'command': state.last_executed_command,
        'current': time_diff,
        'final': args.timeout
    }
    send_sio_message('query_progress_response', j)


while True:
    try:
        sio.connect(args.endpoint)
        sio.wait()
    except Exception as e:
        continue

#soft, hard = resource.getrlimit(resource.RLIMIT_CPU)
#print(soft, hard)

#print(system_info.get_system_info())
#run_command('tools/dcdiag')
#run_command('tools/cpu_check')
