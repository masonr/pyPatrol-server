from twisted.internet.protocol import Protocol, Factory
from twisted.internet import reactor
from datetime import datetime
import json, random, threading, time, zmq

my_secret = 'changeme123'
workers = []
secrets = [my_secret]
workers_lock = threading.Lock()

class Worker():

    def __init__(self, data):
        self.name = data['name']
        self.node_ip = data['ip']
        self.node_port = data['port']
        self.ipv4_capable = data['ipv4']
        self.ipv6_capable = data['ipv6']
        self.use_ssl = data['ssl']
        self.last_contact = datetime.now()

def add_worker(data):
    workers_lock.acquire()
    for w in workers:
        if w.name == data['name']:
            #print("worker_mgr.py: add_worker - worker already in queue: " + str(worker.name))
            w.last_contact = datetime.now()
            workers_lock.release()
            return
    worker = Worker(data)
    workers.append(worker)
    print("worker_mgr.py: add_worker - added worker: " + str(worker.name))
    workers_lock.release()

def check_workers():
    print("Started check_workers thread...")
    while (True):
        for w in workers:
            if ((datetime.now() - w.last_contact).seconds > 45):
                print("worker_mgr.py: check_workers - removing worker due to inactivity: " + str(w.name))
                workers_lock.acquire()
                workers.remove(w)
                workers_lock.release()
        time.sleep(30)

class WorkerQueue(Protocol):
    def dataReceived(self, data):
        #print("worker_mgr.py: WorkerQueue - dataReceived: " + str(data))
        data = json.loads(data)
        if data['secret'] in secrets:
            add_worker(data)
        else:
            print("Rejected unauthorized worker: " + data['name'])

def get_worker(type):
    if (len(workers) == 0):
        return None
    if (type == 'ipv4'):
        while (True):
            rand_int = random.randint(0, len(workers) - 1)
            if (workers[rand_int].ipv4_capable):
                #print("get_worker - returning: " + workers[rand_int].name)
                return workers[rand_int]
    elif (type == 'ipv6'):
        rand_int = random.randint(0, len(workers) - 1)
        if (workers[rand_int].ipv6_capable):
            return workers[rand_int]
    else:
        return None

def get_3_workers(type):
    if (len(workers) < 3):
        return None
    three_workers = []
    current_worker = None
    while (True):
        if (len(three_workers) == 3):
            return three_workers
        current_worker = get_worker(type)
        duplicate = False
        for w in three_workers:
            if w.name == current_worker.name:
                duplicate = True
                break
        if (not duplicate):
            three_workers.append(current_worker)

def worker_dispatcher():
    print("Started worker_dispatcher thread...")
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://127.0.0.1:6668")

    while (True):
        message = socket.recv_json()
        #print("Received request: " + str(message))
        workers = get_3_workers('ipv4')
        if (workers is not None):
            results = [None] * 3
            for i in range(len(workers)):
                worker_uri = "http://" + str(workers[i].node_ip) + ":" + str(workers[i].node_port)
                results[i] = worker_uri
        else:
            results = None
        socket.send_json(results)

def main():
    print("Started worker_mgr.py...")

    workers = []
    random.seed()

    # Start Worker Inactivity check thread
    t = threading.Thread(target=check_workers, name='check_workers')
    t.setDaemon(True)
    t.start()

    # Start Worker Dispatcher thread
    d = threading.Thread(target=worker_dispatcher, name='worker_dispatcher')
    d.setDaemon(True)
    d.start()

    f = Factory()
    f.protocol = WorkerQueue
    reactor.listenTCP(6667, f)
    reactor.run(installSignalHandlers=0)

if __name__ == '__main__':
    main()
