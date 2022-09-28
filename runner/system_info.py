#modified from https://stackoverflow.com/questions/3103178/how-to-get-the-system-info-with-python

import json
from tkinter.messagebox import RETRY
import psutil
import platform
from datetime import datetime
import cpuinfo
import socket
import uuid
import re
from collections import defaultdict


def get_size(bytes, suffix="B"):
    """
    Scale bytes to its proper format
    e.g:
        1253656 => '1.20MB'
        1253656678 => '1.17GB'
    """
    factor = 1024
    for unit in ["", "K", "M", "G", "T", "P"]:
        if bytes < factor:
            return f"{bytes:.2f}{unit}{suffix}\n"
        bytes /= factor

def get_system_info():
    info = defaultdict(dict)
    system_information = info['System Information']
    uname = platform.uname()
    system_information['System'] = f"{uname.system}"
    system_information['Node Name'] = f"{uname.node}"
    system_information['Release'] = f"{uname.release}"
    system_information['Version'] = f"{uname.version}"
    system_information['Machine'] = f"{uname.machine}"
    system_information['Processor'] = f"{uname.processor}"
    system_information['Processor'] = f"{cpuinfo.get_cpu_info()['brand_raw']}"
    system_information['Ip-Address'] = f"{socket.gethostbyname(socket.gethostname())}"
    system_information['Mac-Address'] = f"{':'.join(re.findall('..', '%012x' % uuid.getnode()))}"

    system_information['cpuinfo'] = json.loads(cpuinfo.get_cpu_info_json())

    with open('/etc/machine-id', 'r') as f:
        data = f.read().rstrip()
        system_information['machine-id'] = data

    # Boot Time
    boot_time_timestamp = psutil.boot_time()
    bt = datetime.fromtimestamp(boot_time_timestamp)
    info['Boot Time'] = f"{bt.year}/{bt.month}/{bt.day} {bt.hour}:{bt.minute}:{bt.second}"


    # print CPU information
    cpu_info = info['CPU Info']
    # number of cores
    cpu_info['Physical cores'] = psutil.cpu_count(logical=False)
    cpu_info['Total cores'] = psutil.cpu_count(logical=True)
    # CPU frequencies
    cpufreq = psutil.cpu_freq()
    cpu_info['Max Frequency'] = cpufreq.max
    cpu_info['Min Frequency'] = cpufreq.min
    cpu_info['Current Frequency'] = cpufreq.current
    # CPU usage
    cpu_info['CPU Usage Per Core'] = {}
    cpu_usage_per_core = cpu_info['CPU Usage Per Core']
    for i, percentage in enumerate(psutil.cpu_percent(percpu=True, interval=1)):
        cpu_usage_per_core[f'Core {i}'] = f"{percentage}%"
    cpu_info['Total CPU Usage'] = f"{psutil.cpu_percent()}%"


    # Memory Information
    memory_info = info['Memory Information']
    # get the memory details
    svmem = psutil.virtual_memory()
    memory_info['Total'] = f"{get_size(svmem.total)}"
    memory_info['Available'] = f"{get_size(svmem.available)}"
    memory_info['Used'] = f"{get_size(svmem.used)}"
    memory_info['Percentage'] = f"{svmem.percent}%"



    swap_info = info['Swap Information']
    # get the swap memory details (if exists)
    swap = psutil.swap_memory()
    swap_info['Total'] = f"{get_size(swap.total)}"
    swap_info['Free'] = f"{get_size(swap.free)}"
    swap_info['Used'] = f"{get_size(swap.used)}"
    swap_info['Percentage'] = f"{swap.percent}%"



    # Disk Information
    disk_info = info['Disk Information']
    disk_info['Partitions and Usage'] = {}
    parition_info = disk_info['Partitions and Usage']
    # get all disk partitions
    partitions = psutil.disk_partitions()
    for partition in partitions:
        parition_info['Device'] = f"{partition.device}"
        parition_info['Mountpoint'] = f"{partition.mountpoint}"
        parition_info['File system type'] = f"{partition.fstype}"
        try:
            partition_usage = psutil.disk_usage(partition.mountpoint)
        except PermissionError:
            # this can be catched due to the disk that
            # isn't ready
            continue
        parition_info['Total Size'] = f"{get_size(partition_usage.total)}"
        parition_info['Used'] = f"{get_size(partition_usage.used)}"
        parition_info['Free'] = f"{get_size(partition_usage.free)}"
        parition_info['Percentage'] = f"{partition_usage.percent}%"
    # get IO statistics since boot
    disk_io = psutil.disk_io_counters()
    disk_info['Total read'] = f"{get_size(disk_io.read_bytes)}"
    disk_info['Total write'] = f"{get_size(disk_io.write_bytes)}"

    ## Network information
    network_info = info['Network Information']
    ## get all network interfaces (virtual and physical)
    if_addrs = psutil.net_if_addrs()
    for interface_name, interface_addresses in if_addrs.items():
        for address in interface_addresses:
            network_info['Interface'] = f"{interface_name}"
            if str(address.family) == 'AddressFamily.AF_INET':
                network_info['IP Address'] = f"{address.address}"
                network_info['Netmask'] = f"{address.netmask}"
                network_info['Broadcast IP'] = f"{address.broadcast}"
            elif str(address.family) == 'AddressFamily.AF_PACKET':
                network_info['MAC Address'] = f"{address.address}"
                network_info['Netmask'] = f"{address.netmask}"
                network_info['Broadcast MAC'] = f"{address.broadcast}"
    ##get IO statistics since boot
    net_io = psutil.net_io_counters()
    network_info['Total Bytes Sent'] = f"{get_size(net_io.bytes_sent)}"
    network_info['Total Bytes Received'] = f"{get_size(net_io.bytes_recv)}"

    return info


if __name__ == "__main__":
    get_system_info()
