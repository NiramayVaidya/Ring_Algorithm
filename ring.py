import argparse
import sys
import time
import socket
import random
import pickle
from multiprocessing import Process, Manager

def setup_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--num-of-processes', '-numproc', type=int, required=True, \
        help='pass the required number of processes')
    return parser.parse_args()

def connect_skt(skt, ip_address_and_port):
  while True:
        try:
            skt.connect(ip_address_and_port)
            break
        except ConnectionRefusedError:
            pass

def bind_and_listen_skt(skt, ip_address_and_port):
    skt.bind(ip_address_and_port)
    skt.listen(2)

def setup_skt(ip_address_and_port, mode):
    skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if mode == 's':
        bind_and_listen_skt(skt, ip_address_and_port)
    elif mode == 'c':
        connect_skt(skt, ip_address_and_port)
    else:
        print('ERROR: Correct mode not provided while calling setup_skt(), should be s/c\n', end='', flush=True, file=debug_file)
        sys.exit(0)
    return skt

def run_proc(priority, shared_vars, ip_address, port, neighbor_ip_address, neighbor_port, lock):
    print('DEBUG: priority ' + str(priority) + ' has port ' + str(port) + '\n', end='', flush=True, file=debug_file)
    failed = False
    accepted = False
    coordinator = True
    count = 0
    next_neighbor_failed_process = False
    previous_neighbor_failed_process = False
    s_skt = setup_skt(('', port), 's')
    print('DEBUG: s_skt set by priority ' + str(priority) + ' to ' + str(port) + '\n', end='', flush=True, file=debug_file)
    c_skt = setup_skt((neighbor_ip_address[0], neighbor_port[0]), 'c')
    print('DEBUG: c_skt set by priority ' + str(priority) + ' to ' + str(neighbor_port[0]) + '\n', end='', flush=True, \
        file=debug_file)
    while True:
        if shared_vars['coordinator_id'] == priority and coordinator:
            print('coordinator:' + str(priority) + '\n', end='', flush=True, file=output_file)
            coordinator = False
        time.sleep(priority / 10)
        if shared_vars['coordinator_id'] == -1:
            print('DEBUG: coordinator_id set to -1 by priority ' + str(priority) + '\n', end='', flush=True, file=debug_file)
            shared_vars['coordinator_id'] = 0
            shared_priority_list = []
            shared_priority_list.append(priority)
            print('DEBUG: shared_priority_list is set to ' + str(shared_priority_list) + ' by priority ' + str(priority) + '\n', \
                end='', flush=True, file=debug_file)
            if (neighbor_ip_address[0], neighbor_port[0]) == shared_vars['coordinator_process']:
                next_neighbor_failed_process = True
                c_skt.close()
                c_skt = setup_skt(shared_vars['coordinator_next_process'], 'c')
                print('DEBUG: c_skt reset by priority ' + str(priority) + ' to ' + str(shared_vars['coordinator_next_process'][1]) \
                    + '\n', end='', flush=True, file=debug_file)
            elif (neighbor_ip_address[1], neighbor_port[1]) == shared_vars['coordinator_process']:
                previous_neighbor_failed_process = True
                s_skt.close()
                s_skt = setup_skt(('', port), 's')
                print('DEBUG: s_skt reset by priority ' + str(priority) + ' to ' + str(port) + '\n', \
                    end='', flush=True, file=debug_file)
            if shared_vars['coordinator_process'] == (None, None) and next_neighbor_failed_process:
                c_skt.close()
                c_skt = setup_skt((neighbor_ip_address[0], neighbor_port[0]), 'c')
                print('DEBUG: c_skt reset by priority ' + str(priority) + ' to ' + str(neighbor_port[0]) + '\n', \
                    end='', flush=True, file=debug_file)
            elif shared_vars['coordinator_process'] == (None, None) and previous_neighbor_failed_process:
                s_skt.close()
                # s_skt = setup_skt(('', port), 's')
                # TODO fix code to avoid using base_port
                s_skt = setup_skt(('', shared_vars['base_port']), 's')
                print('DEBUG: s_skt reset by priority ' + str(priority) + ' to ' + str(port) + '\n', file=debug_file)
            while True:
                try:
                    c_skt.sendall(pickle.dumps(shared_priority_list))
                    print('DEBUG: shared_priority_list is sent as ' + str(shared_priority_list) + ' by priority ' + str(priority) \
                        + '\n', end='', flush=True, file=debug_file)
                    break
                except ConnectionResetError:
                    pass
            if not failed:
                new_skt, addr = s_skt.accept()
                failed = True
            shared_priority_list = pickle.loads(new_skt.recv(256))
            print('DEBUG: shared_priority_list is received as ' + str(shared_priority_list) + ' by priority ' + str(priority) \
                + '\n', end='', flush=True, file=debug_file)
            lock.acquire()
            shared_vars['coordinator_id'] = max(shared_priority_list)
            lock.release()
        if shared_vars['coordinator_id'] == 0:
            if (neighbor_ip_address[0], neighbor_port[0]) == shared_vars['coordinator_process']:
                next_neighbor_failed_process = True
                c_skt.close()
                c_skt = setup_skt(shared_vars['coordinator_next_process'], 'c')
                print('DEBUG: c_skt reset by priority ' + str(priority) + ' to ' + str(shared_vars['coordinator_next_process'][1]) \
                    + '\n', end='', flush=True, file=debug_file)
            elif (neighbor_ip_address[1], neighbor_port[1]) == shared_vars['coordinator_process']:
                previous_neighbor_failed_process = True
                s_skt.close()
                s_skt = setup_skt(('', port), 's')
                print('DEBUG: s_skt reset by priority ' + str(priority) + ' to ' + str(port) + '\n', \
                    end='', flush=True, file=debug_file)
            if shared_vars['coordinator_process'] == (None, None) and next_neighbor_failed_process:
                next_neighbor_failed_process = False
                c_skt.close()
                c_skt = setup_skt((neighbor_ip_address[0], neighbor_port[0]), 'c')
                print('DEBUG: c_skt reset by priority ' + str(priority) + ' to ' + str(neighbor_port[0]) + '\n', \
                    end='', flush=True, file=debug_file)
            elif shared_vars['coordinator_process'] == (None, None) and previous_neighbor_failed_process:
                previous_neighbor_failed_process = False
                s_skt.close()
                # s_skt = setup_skt(('', port), 's')
                # TODO fix code to avoid using base_port
                # (the right neighbor of the failed coordinator binds to this port upon its recovery
                # instead of binding to its own port)
                s_skt = setup_skt(('', shared_vars['base_port']), 's')
                print('DEBUG: s_skt reset by priority ' + str(priority) + ' to ' + str(port) + '\n', \
                    end='', flush=True, file=debug_file)
            while not accepted:
                # print('DEBUG: priority ' + str(priority) + ' in accept stage', file=debug_file)
                new_skt, addr = s_skt.accept()
                if new_skt:
                    accepted = True
                    failed = True
                    break
            shared_priority_list = pickle.loads(new_skt.recv(256))
            print('DEBUG: shared_priority_list is received as ' + str(shared_priority_list) + ' by priority ' + str(priority) \
                + '\n', end='', flush=True, file=debug_file)
            shared_priority_list.append(priority)
            print('DEBUG: shared_priority_list is set to ' + str(shared_priority_list) + ' by priority ' + str(priority) + '\n', \
                end='', flush=True, file=debug_file)
            while True:
                try:
                    c_skt.sendall(pickle.dumps(shared_priority_list))
                    print('DEBUG: shared_priority_list is sent as ' + str(shared_priority_list) + ' by priority ' + str(priority) \
                        + '\n', end='', flush=True, file=debug_file)
                    break
                except ConnectionResetError:
                    pass

        # work done by each process
        print('work:' + str(priority) + '\n', end='', flush=True, file=output_file)

        time.sleep(5)
        count += 1
        if count == 5 and shared_vars['coordinator_id'] == priority:
            lock.acquire()
            shared_vars['coordinator_id'] = -1
            lock.release()
            shared_vars['coordinator_process'] = (ip_address, port)
            shared_vars['coordinator_next_process'] = (neighbor_ip_address[0], neighbor_port[0])
            shared_vars['coordinator_previous_process'] = (neighbor_ip_address[1], neighbor_port[1])
            s_skt.close()
            c_skt.close()
            print('failed:' + str(priority) + '\n', end='', flush=True, file=output_file)
            time.sleep(40)
            print('recovered:' + str(priority) + '\n', end='', flush=True, file=output_file)
            lock.acquire()
            shared_vars['coordinator_id'] = -1
            lock.release()
            shared_vars['coordinator_process'] = (None, None)
            shared_vars['coordinator_next_process'] = (None, None)
            shared_vars['coordinator_previous_process'] = (None, None)
            s_skt = setup_skt(('', port), 's')
            print('DEBUG: s_skt reset by priority ' + str(priority) + ' to ' + str(port) + '\n', \
                end='', flush=True, file=debug_file)
            # c_skt = setup_skt((neighbor_ip_address[0], neighbor_port[0]), 'c')
            # TODO fix code to avoid using base_port
            c_skt = setup_skt((neighbor_ip_address[0], shared_vars['base_port']), 'c')
            print('DEBUG: c_skt reset by priority ' + str(priority) + ' to ' + str(neighbor_port[0]) + '\n', \
                end='', flush=True, file=debug_file)
            coordinator = True
        if count == 15:
            break

if __name__ == '__main__':

    debug_file = open('debug.txt', 'w')
    output_file = open('output.txt', 'w')

    # setting up input of command line arguments
    args = setup_argument_parser()
    num_of_processes = args.num_of_processes
    if num_of_processes <= 2:
        print('ERROR: Number of processes must be greater than 2\n', end='', flush=True, file=debug_file)
        sys.exit(0)

    # initializing ip address and port for all processes (localhost is used for all processes)
    base_port = random.randrange(9000, 20000, num_of_processes + 1)
    ip_addresses = []
    ports = []
    for iterator in range(1, num_of_processes + 1):
        ip_addresses.append('127.0.0.1')
        ports.append(base_port + iterator)

    manager = Manager()
    lock = manager.Lock()
    shared_vars = manager.dict()
    jobs = []

    # setting variables to be shared among all processes
    shared_vars['coordinator_id'] = num_of_processes
    shared_vars['coordinator_process'] = (None, None)
    shared_vars['coordinator_next_process'] = (None, None)
    shared_vars['coordinator_previous_process'] = (None, None)
    shared_vars['base_port'] = base_port

    # process id is the same as process priority
    for process_id in range(num_of_processes, 0, -1):
        process = Process(target=run_proc, args=(process_id, shared_vars, ip_addresses[process_id - 1], ports[process_id - 1], \
            (ip_addresses[process_id % num_of_processes], ip_addresses[process_id - 2]), \
            (ports[process_id % num_of_processes], ports[process_id - 2]), lock))
        jobs.append(process)
        process.start()
    for process in jobs:
        process.join()

    debug_file.close()
    output_file.close()