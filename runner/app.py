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
import hashlib
import json
import datetime

import system_info

parser = argparse.ArgumentParser(description='Run SDC tools')
parser.add_argument('--default_timeout', type=float, required=False, default=60, help='Default timeout in seconds to run for. Default is 60 (a minute)')
#parser.add_argument('--sleep_interval', type=float, required=False, default=0, help='Intervals to sleep for between runs')
#parser.add_argument('--cpu_count', type=float, required=False, default=1.0, help='Percentage of cores to use (1.0 = all 0.5 = half)')
parser.add_argument('--endpoint', type=str, default='http://localhost:5000', help='Connect to endpoint')
parser.add_argument('--silifuzz_corpus', type=str, default='tools/silifuzz/silifuzz.corpus.xz', help='Corpus for silifuzz')
args = parser.parse_args()

sio = socketio.Client()
sio_lock = threading.Lock()

silifuzz_dir = 'tools/silifuzz'

class Command:
    def __init__(self, command, update_timeout_func=None):
        self.command = command
        self.timeout = None
        self.update_timeout_func = update_timeout_func
        self.iteration = 0

    def set_timeout(self, timeout):
        self.timeout = timeout

    def update_command_with_timeout(self):
        if self.update_timeout_func:
            self.command = self.update_timeout_func(self.command, self.timeout)
        self.iteration += 1

class Sleep(object):
    def __init__(self, seconds, immediate=True):
        self.seconds = seconds
        self.event = threading.Event()
        if immediate:
            self.sleep()

    def sleep(self, seconds=None):
        if seconds is None:
            seconds = self.seconds
        self.event.clear()
        self.event.wait(timeout=seconds)

    def wake(self):
        self.event.set()

class State:
    def __init__(self):
        self.silifuzz_corpus = args.silifuzz_corpus
        
        # Don't touch frequency, temperature, crashes in source code
        self.base_cpu_check_command = ['stdbuf', '-oL', 'tools/cpu_check', '-g']
        self.base_dcdiag_command = ['stdbuf', '-oL', 'tools/dcdiag']
        self.base_silifuzz_command = ['stdbuf', '-oL', f'{silifuzz_dir}/orchestrator/silifuzz_orchestrator_main', f'--runner={silifuzz_dir}/runner/reading_runner_main_nolibc', f'{self.silifuzz_corpus}']
        def update_cpu_check_timeout(command, timeout):
            if timeout != None:
                command = [*self.base_cpu_check_command, f'-t{timeout}']
            else:
                command = self.base_cpu_check_command
            return command
        def update_dcdiag_timeout(command, timeout):
            return command
        def update_silifuzz_timeout(command, timeout):
            if timeout != None:
                command = [f'{silifuzz_dir}/orchestrator/silifuzz_orchestrator_main', f'--duration={timeout}s', f'--runner={silifuzz_dir}/runner/reading_runner_main_nolibc', f'{self.silifuzz_corpus}']
            else:
                command = self.base_silifuzz_command
            return command

        self.cpu_check_command = Command(self.base_cpu_check_command, update_cpu_check_timeout)
        self.dcdiag_command = Command(base_dcdiag_command, update_dcdiag_timeout) 
        self.silifuzz_command = Command(self.base_silifuzz_command, update_silifuzz_timeout)

        self.commands = [self.cpu_check_command, self.dcdiag_command, self.silifuzz_command]
        [c.set_timeout(args.default_timeout) for c in self.commands]
        self.command_index = random.randint(0, len(self.commands) - 1)
        self.last_executed_command = ''
        self.last_executed_command_time = 0
        self.iterations = 0
        self.timeout = 0
        self.process = None
        self.current_command = None
        self.current_process_killed = False
        self.run_time_of_day_start = None
        self.run_time_of_day_end = None
        self.sleep = None
    
    def get_command(self):
        return self.commands[self.command_index]

    def get_next_command(self):
        self.command_index += 1
        if self.command_index >= len(self.commands):
            self.command_index = 0
        command = self.get_command()
        command.update_command_with_timeout()
        self.iterations += 1
        self.last_executed_command = command.command
        self.timeout = command.timeout
        if self.timeout == None:
            self.timeout = 0
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

def get_hash_file(filename):
    h = hashlib.sha256()
    with open(filename, 'rb') as file:
        while True:
            chunk = file.read(h.block_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def run_command(command):
    p = None
    data = {}
    state.current_command = command
    try:
        p = subprocess.Popen(command.command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=preexec_fn)
        state.process = p
        timeout = command.timeout
        if timeout is not None:
            timeout += 10.0
        stdout, stderr = p.communicate(timeout=timeout)
        data = {
            'status': 'success',
            'command': command.command,
            'stdout': format_bytes(stdout),
            'stderr': format_bytes(stderr),
            'code': p.returncode,
        }
    except subprocess.TimeoutExpired as e:
        state.process.kill()
        stdout, stderr = p.communicate()
        data = {
            'status': 'timeout',
            'command': command.command,
            'stdout': format_bytes(e.stdout),
            'stderr': format_bytes(e.stderr),
        }
    except subprocess.CalledProcessError as e:
        data = {
            'status': 'called_process_error',
            'command': command.command,
            'stdout': format_bytes(e.stdout),
            'stderr': format_bytes(e.stderr),
            'code': e.returncode,
        }
    except Exception as e:
        data = {
            'status': 'general_exception',
            'command': command.command,
            'exception': str(e),
        }
    if command == state.silifuzz_command:
        data['hash'] = get_hash_file(args.silifuzz_corpus)
    state.current_command = None
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
        while state.run_time_of_day_start is not None and state.run_time_of_day_end is not None:
            date = datetime.datetime.now()
            if date.hour >= state.run_time_of_day_start and date.hour < state.run_time_of_day_end:
                diff_in_seconds = (state.run_time_of_day_end - state.run_time_of_day_start) * 60 * 60
                print(f'Sleeping from {state.run_time_of_day_start} to {state.run_time_of_day_end}... Current {date.hour}')
                state.sleep = Sleep(diff_in_seconds, immediate=False)
                state.sleep.sleep()
            elif state.run_time_of_day_start > state.run_time_of_day_end:
                run_time_of_day_end = state.run_time_of_day_end + 24
                next_hour = date.hour + 24
                print(date.hour, state.run_time_of_day_start, run_time_of_day_end)
                if (date.hour >= state.run_time_of_day_start and date.hour < run_time_of_day_end) or \
                    (next_hour >= state.run_time_of_day_start and next_hour < run_time_of_day_end):
                    diff_in_seconds = (run_time_of_day_end - state.run_time_of_day_start) * 60 * 60
                    print(f'Sleeping from {state.run_time_of_day_start} to {state.run_time_of_day_end}... Current {date.hour}')
                    state.sleep = Sleep(diff_in_seconds, immediate=False)
                    state.sleep.sleep()
                else:
                    break
            else:
                break

        command = state.get_next_command()
        print(f'Current running: {command.command}')
        state.last_executed_command_time = time.time()
        start_date = datetime.datetime.now()
        data = run_command(command)
        end_date = datetime.datetime.now()
        execution_time = time.time() - state.last_executed_command_time
        # Manually killed process
        if state.current_process_killed:
            if data['status'] == 'success':
                if data['code'] == -9:
                    data['code'] = 0

        if command == state.dcdiag_command and data['status'] == 'called_process_error':
            # illegal instruction error, old cpu
            if data['code'] == -4:
                # remove from testing
                state.commands.remove(state.dcdiag_command)
                state.command_index = 0
        data['system_info'] = system_info.get_system_info()
        data['total_iteration'] = state.iterations
        data['execution_time'] = execution_time
        
        def format_date(date):
            return date.strftime('%Y-%m-%d %H:%M:%S')
        data['start_date'] = format_date(start_date)
        data['end_date'] = format_date(end_date)
        data['command_iteration'] = command.iteration

        print(f'Finished running: {command.command}')
        print(f'Returned : {json.dumps(data, indent=2)}')
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
    result = run_command(Command(data, None))
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
    time_diff = time.time() - state.last_executed_command_time
    j = {
        'iter': state.iterations,
        'command': state.last_executed_command,
        'current': time_diff,
        'final': state.timeout
    }
    send_sio_message('query_progress_response', j)

@sio.event
def update_corpus_request(data):
    b64_data = data['b64_data']
    corpus = base64.b64decode(b64_data)
    j = {
        'status': 'success',
    }
    try:
        # Stop if we are working on silifuzz
        '''
        if state.current_command == state.silifuzz_command:
            while state.process and not state.process.poll():
                state.current_process_killed = True
                state.process.kill()
                time.sleep(1)
        '''

        # Update the corpus file
        with open(args.silifuzz_corpus, 'wb') as f:
            f.write(corpus)
        j['hash'] = get_hash_file(args.silifuzz_corpus)
    except Exception as e:
        j = {
            'status': 'error',
            'error': str(e),
        }
    send_sio_message('update_corpus_response', j)

@sio.event
def update_run_time_of_day_request(data):
    old_run_time_of_day_start = state.run_time_of_day_start
    old_run_time_of_day_end = state.run_time_of_day_end
    state.run_time_of_day_start = data['start']
    state.run_time_of_day_end = data['end']
    print(f'Updated run time of day {state.run_time_of_day_start}..{state.run_time_of_day_end}')
    if state.sleep is not None:
        print(f'Waking up from existing sleep from {old_run_time_of_day_start}..{old_run_time_of_day_end}')
        state.sleep.wake()
    j = {
        'status': 'success'
    }
    send_sio_message('update_run_time_of_day_response', j)

@sio.event
def update_timeout_request(data):
    cpu_check_timeout = data['cpu_check']
    dcdiag_timeout = data['dcdiag']
    silifuzz_timeout = data['silifuzz']
    j = {
        'status': 'success'
    }
    try:
        for c in state.commands:
            if c == state.cpu_check_command:
                c.set_timeout(cpu_check_timeout)
            elif c == state.dcdiag_command:
                c.set_timeout(dcdiag_timeout)
            elif c == state.silifuzz_command:
                c.set_timeout(silifuzz_timeout)
        '''
        while state.process and not state.process.poll():
            state.current_process_killed = True
            state.process.kill()
            time.sleep(1)
        '''
    except Exception as e:
        j = {
            'status': 'error',
            'error': str(e),
        }
    send_sio_message('update_timeout_response', j)

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
