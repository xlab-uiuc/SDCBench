import bs4
import subprocess
from multiprocessing import Pool
#from concurrent.futures import ThreadPoolExecutor as Pool
import argparse

from pathlib import Path
import asyncio, asyncssh, sys

parser = argparse.ArgumentParser(description='Run docker image on cloudlab machines from xml config of cluster')
parser.add_argument('--config_file', type=str, help='XML config containing description for cloudlab machine (Copy paste under Manifest when viewing the experiment)', default='config.xml')
parser.add_argument('--identity_file', type=str, help='SSH identity file to access cloudlab machine', default='cloudlab.pem')
parser.add_argument('--identity_file_password', type=str, help='SSH password for file to access cloudlab machine', default='')
parser.add_argument('--docker_image', type=str, help='Docker image to upload to cloudlab machine', default='runner.tar')
parser.add_argument('--timeout', type=int, help='Passed to docker image (timeout)', default=10000)
parser.add_argument('--endpoint', type=str, help='Passed to docker image (timeout)', default='http://localhost:8888')
parser.add_argument('--show_progress', type=bool, help='Show progress of uploading docker image', default=True)
args = parser.parse_args()

config_file = args.config_file
identity_file = args.identity_file
identity_file_password = args.identity_file_password
docker_image = Path(args.docker_image)

timeout = args.timeout
#endpoint = 'http://pepega.cs.illinois.edu:5000'
endpoint = args.endpoint
docker_image_name = docker_image.name
docker_image_name_stem = docker_image.stem

if __name__ == '__main__':
    with open(config_file, 'r') as f:
        xml = f.read()
        soup = bs4.BeautifulSoup(xml, 'lxml')
        
        async def run_on_node(conn):
            async def run_command(command):
                print(f'[{conn._host}] Running {command}...')
                result = await conn.run(command, check=True)
                print(f'[{conn._host}] Finished running {command}...')
                return result.stdout

            stdout = await run_command(r'sudo apt update -y')
            stdout = await run_command(r'sudo apt install -y docker.io')
            print(f'[{conn._host}] Copying {docker_image}...')
            def progress_handler(src_path, dst_path, bytes_uploaded, bytes_total):
                print(f'[{conn._host}] Copying {docker_image}... {(bytes_uploaded / bytes_total) * 100:.2f}%')
            if args.show_progress:
                await asyncssh.scp(str(docker_image), (conn, docker_image_name), progress_handler=progress_handler)
            else:
                await asyncssh.scp(str(docker_image), (conn, docker_image_name))
            #async with conn.start_sftp_client() as sftp:
            #    await sftp.put(docker_image, docker_image, progress_handler=progress_handler)
            print(f'[{conn._host}] Finished copying {docker_image}...')
            stdout = await run_command(f'sudo docker load < {docker_image_name}')
            stdout = await run_command(f'sudo docker ps')
            for r in stdout.split('\n'):
                if r is None:
                    continue
                items = r.split(' ')
                if items[0] == 'CONTAINER':
                    continue
                else:
                    if len(items) > 5:
                        container_id = items[0]
                        await run_command(f'sudo docker kill {container_id}')
            #run_remote_command_see_output(f'sudo docker run -e SDC_TIMEOUT={timeout} -e SDC_ENDPOINT={endpoint} {docker_image_name}')
            stdout = await run_command(f'sudo docker run -d -e SDC_TIMEOUT={timeout} -e SDC_ENDPOINT={endpoint} {docker_image_name_stem}')
            return True
        
        interfaces = list(soup.find_all('login'))
        def get_ssh_endpoint(interface):
            ssh_endpoint = f'{interface["username"]}@{interface["hostname"]}'
            return ssh_endpoint
        ssh_endpoints = [get_ssh_endpoint(interface) for interface in interfaces]
        def get_username_hostname(interface):
            username = interface['username']
            hostname = interface['hostname']
            return username, hostname
        username_hostname = [get_username_hostname(interface) for interface in interfaces]
        p_key = asyncssh.read_private_key(identity_file, identity_file_password)

        async def run_client(username_hostname) -> asyncssh.SSHCompletedProcess:
            username = username_hostname[0]
            hostname = username_hostname[1]
            async with asyncssh.connect(host=hostname, username=username, port=22, client_keys=[p_key], known_hosts=None) as conn:
                r = await run_on_node(conn)
                return r 

        async def run_multiple_clients() -> None:
            # Put your lists of hosts here
            tasks = (run_client(u) for u in username_hostname)
            #tasks = (run_client(u) for u in username_hostname[:1])
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results, 1):
                if isinstance(result, Exception):
                    print('Task %d failed: %s' % (i, str(result)))
                else:
                    print(f'Task {i} Success')
        
        asyncio.run(run_multiple_clients())

