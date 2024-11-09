import socket
import json
import csv
import random
import time
import threading
from datetime import datetime

PORT_CMD = 7745
PORT_DATA = 7746
MODES = ["normal_traffic", "high_traffic", "udp_flood", "tcp_flood", "http_flood", "icmp_flood"]
CSV_FILE = "collected_data.csv"
EXP_CONNS = 2

# Fixed list of known resource metrics and syscalls
RESOURCE_METRICS = [
    "node_cpu_seconds_total", "node_filesystem_avail_bytes", "node_filesystem_size_bytes", 
    "node_disk_read_bytes_total", "node_disk_written_bytes_total", "node_network_receive_bytes_total", 
    "node_network_receive_drop_total", "node_network_receive_errs_total", "node_network_transmit_packets_total",
    "node_vmstat_pgmajfault", "node_memory_MemAvailable_bytes", "node_memory_MemTotal_bytes", 
    "node_forks_total", "node_intr_total", "node_load1", "node_load5", "node_load15", 
    "node_sockstat_TCP_alloc", "node_sockstat_TCP_inuse", "node_sockstat_TCP_mem", 
    "node_sockstat_TCP_mem_bytes", "node_sockstat_UDP_inuse", "node_sockstat_UDP_mem", 
    "node_sockstat_sockets_used", "node_netstat_Tcp_CurrEstab", "node_filefd_allocated"
]

SYSCALLS = [
    "mmap", "munmap", "accept", "brk", "bind", "connect", "chdir", "clone", "close", "kill",
    "listen", "mkdir", "open", "poll", "read", "rename", "recvfrom", "select", "socket",
    "sendto", "write"
]

HEADERS = ["timestamp", "mode", "hostname", *RESOURCE_METRICS, *SYSCALLS]

current_mode = MODES[0]
clients = []
mode_lock = threading.Lock()
client_lock = threading.Lock()

def save_to_csv(data):
    with open(CSV_FILE, mode='a', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=HEADERS)
        writer.writerow(data)

def notify_clients(new_mode):
    with client_lock:
        for client in clients:
            try:
                client.sendall(new_mode.encode())
            except BrokenPipeError:
                clients.remove(client)

def mode_switcher():
    global current_mode
    while True:
        with mode_lock:
            new_mode = random.choice(MODES)
            current_mode = new_mode
            notify_clients(new_mode)
        time.sleep(random.randint(5, 15))

def start_command_server():
    bot_count = 0
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("", PORT_CMD))
    server_socket.listen(5)
    while True:
        client_socket, client_address = server_socket.accept()
        client_socket.sendall(current_mode.encode())
        with client_lock:
            clients.append(client_socket)
        bot_count += 1
        if bot_count == EXP_CONNS:
            threading.Thread(target=mode_switcher, daemon=True).start()

def handle_data_connection(data_socket):
    global current_mode
    while True:
        try:
            data = data_socket.recv(4096).decode()
            if data:
                json_data = json.loads(data)
                entry = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "mode": current_mode,
                    "hostname": json_data.get("Hostname"),
                }

                resource_metrics = json_data.get("ResourceMetrics", {})
                for metric in RESOURCE_METRICS:
                    entry[metric] = resource_metrics.get(metric, 0.0)

                syscalls = json_data.get("Syscalls", {})
                for syscall in SYSCALLS:
                    entry[syscall] = syscalls.get(syscall, 0)

                save_to_csv(entry)
        
        except (json.JSONDecodeError, KeyError):
            continue

def start_data_server():
    data_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    data_server_socket.bind(("", PORT_DATA))
    data_server_socket.listen(5)
    while True:
        data_socket, data_address = data_server_socket.accept()
        threading.Thread(target=handle_data_connection, args=(data_socket,), daemon=True).start()

if __name__ == "__main__":
    with open(CSV_FILE, mode='w', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=HEADERS)
        writer.writeheader()

    threading.Thread(target=start_command_server, daemon=True).start()
    start_data_server()
