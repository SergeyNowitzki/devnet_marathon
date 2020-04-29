# -*- coding: utf-8 -*-
import os
import re
import logging
import yaml
import time
import getpass
import subprocess
from datetime import datetime
from netmiko import ConnectHandler, NetMikoAuthenticationException
from concurrent.futures import ThreadPoolExecutor
from itertools import repeat
from pprint import pprint

CONFIG_FILE_PATH = 'config_backup/'

now = datetime.now()
today = f"{str(now.year)}-{str(now.month)}-{str(now.day)}_{str(now.hour)}-{str(now.minute)}"

logging.getLogger('paramiko').setLevel(logging.WARNING)
logging.basicConfig(
    format = '%(threadName)s %(name)s %(levelname)s: %(message)s',
    level=logging.INFO)

def send_show_command(device_dict, command):
    start_msg = '===> {} Connection: {}'
    received_msg = '<=== {} Received:   {}'
    ip = device_dict['ip']
    logging.info(start_msg.format(datetime.now().time(), ip))
    regex = r"(?P<host>\S+)[#>]"
    try:
        with ConnectHandler(**device_dict) as ssh:
            ssh.enable()
            match = re.search(regex, ssh.find_prompt())
            hostname = match.group('host')
            result_command = ssh.send_command(command)
            logging.info(received_msg.format(datetime.now().time(), ip))
        return result_command, hostname
    except NetMikoAuthenticationException as err:
        logging.warning(err)

def config_backup(devices, limit=3):
    command = 'show running-config'
    result = multi_threading(send_show_command, devices, command)
    for output, hostname in result:
        folder = CONFIG_FILE_PATH + hostname
        file = f"{hostname}_{today}.ios"
        abs_path = folder + '/' + file
        if not os.path.exists(folder):
            os.mkdir(folder)
        with open(abs_path, 'w') as f:
            print('Saving config ' + hostname)
            f.write(output)
            print('OK!')

def check_cdp(devices, limit=3):
    cdp_status_command = 'show cdp neighbors'
    result = multi_threading(send_show_command, devices, cdp_status_command)
    result_list = []
    for output, hostname in result:
        if '% CDP is not enabled' in output:
            cdp = 'CDP is OFF'
            print(f"CDP is OFF on the device {hostname}")
            neighbors = 0
            result_list.append({'device': hostname, 'cdp_status': cdp, 'neighbors': neighbors})
        else:
            cdp = 'CDP is ON'
            print(f"CDP is ON on the device {hostname}")
            regex_cdp_neighbors = (
            r"(?P<device>\S+)\s+"
            r"(?P<local_intf>\S+\s\d\/\d+).*?"
            r"(?P<remote_intf>\S+\s\d\/\d+)"
            )
            cdp_neighbors = []
            for line in output.split('\n'):
                match = re.search(regex_cdp_neighbors, line, re.DOTALL)
                if match:
                    cdp_neighbors.append(match.group('device'))
            neighbors = len(cdp_neighbors)
            result_list.append({'device': hostname, 'cdp_status': cdp, 'neighbors': neighbors})
    print(result_list)
    return result_list

def device_type(devices):
    version_command = "show version"
    regex = (r"^Cisco .* Software \((?P<software>\S+)\), Version (?P<version>\S+),.*"
             r"Cisco (?P<hardware>\S+) .+ processor"
            )
    result = multi_threading(send_show_command, devices, version_command)
    for output, hostname in result:
        match = re.search(regex, output, re.DOTALL)
        if match:
            if match.groupdict()['software'].endswith('npe'):
                match.groupdict()['encr'] = 'NPE'
            else:
                match.groupdict()['encr'] = 'PE'
            
            print(match.groupdict())
            return(match.groupdict())

def multi_threading(func, devices, command, limit=3):
    with ThreadPoolExecutor(max_workers=limit) as executor:
        result = executor.map(func, devices, repeat(command))
        return result


if __name__ == '__main__':
    password = getpass.getpass("Enter user password: ")
    secret = getpass.getpass("Enter enable password: ")
    with open('devices.yaml') as f:
        devices = yaml.safe_load(f)
        for device in devices:
            device['password'] = password
            device['secret'] = secret
    #config_backup(devices)
    #check_cdp(devices)
    device_type(devices)