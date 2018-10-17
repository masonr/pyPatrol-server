# worker_mgr.py
# Author: Mason Rowe <mason@rowe.sh>
# Project: pyPatrol-server
# License: WTFPL <http://www.wtfpl.net/>
# Last Updated: 15 Oct 2018
#
# Purpose: Manages pyPatrol-node workers by maintaining a list currently active workers
#          that have registered with the server (via the Twisted endpoint), regularaly
#          polls the worker array to remove inactive workers, and responds to requests
#          from task threads with worker details to carry out the service check

from twisted.internet.protocol import Protocol, Factory
from twisted.internet import reactor
from datetime import datetime
import json, random, threading, time, zmq, configparser

workers = []
secrets = [] # secret key(s) that a worker must present to the server
workers_lock = threading.Lock() # lock to protect the workers array

# initialize config parser
config = None

# Worker class - holds details for a pyPatrol-node worker
class Worker():
    def __init__(self, data):
        self.name = data['name']
        self.node_ip = data['ip']
        self.node_port = data['port']
        self.ipv4_capable = data['ipv4']
        self.ipv6_capable = data['ipv6']
        self.use_ssl = data['ssl']
        self.last_contact = datetime.now()

# add_worker()
#   Purpose: Add a worker to the active workers array
#   Params:
#     - data: json formatted data with details required for a pyPatrol-node worker
#   Returns: (none)
def add_worker(data):
    workers_lock.acquire() # lock the active workers array from modifications
    # first check if the worker is already in the array
    for w in workers:
        if w.name == data['name']:
            # if the worker is already registered, update the last_contact time
            w.last_contact = datetime.now()
            workers_lock.release()
            return
    # create a new Worker object and load in data
    worker = Worker(data)
    # add the worker to the active workers array
    workers.append(worker)
    print("worker_mgr.py: add_worker - added worker: " + str(worker.name))
    workers_lock.release() # release lock on active workers array

# check_workers()
#   Purpose: Periodically poll the active workers array and purge any workers that haven't been
#            contacted within the past x seconds, in effect removing not responding/inactive
#            workers
#   Params: (none)
#   Returns: (none)
def check_workers():
    print("Started check_workers thread...")
    inactivity_interval = int(config['workers']['inactivity_interval'])
    while (True):
        for w in workers:
            if ((datetime.now() - w.last_contact).seconds > (inactivity_interval * 1.5)):
                print("worker_mgr.py: check_workers - removing worker due to inactivity: " + str(w.name))
                workers_lock.acquire()
                workers.remove(w)
                workers_lock.release()
        time.sleep(inactivity_interval)

# WorkerQueue class - the Twisted endpoint for pyPatrol-node workers to send their heartbeats
class WorkerQueue(Protocol):
    def dataReceived(self, data):
        data = json.loads(data)
        # ensure the worker is authorized to accept work (presents a secret key)
        if data['secret'] in secrets:
            add_worker(data)
        else:
            print("Rejected unauthorized worker: " + data['name'])

# get_worker()
#   Purpose: Return one randomly selected worker of a specific type (ipv4 or ipv6) from the
#            pypatrol node workers queue
#   Params:
#     - type: 'ipv4' or 'ipv6' denotes the type of service check required
#   Returns: A Worker object
def get_worker(type):
    # exit if no workers are registered with the server
    if (len(workers) == 0):
        return None
    # get worker of requested type (ipv4 or ipv6)
    while (True):
        rand_int = random.randint(0, len(workers) - 1)
        if (type == 'ipv4' and workers[rand_int].ipv4_capable):
            return workers[rand_int]
        elif (type == 'ipv6' and workers[rand_int].ipv6_capable):
            return workers[rand_int]
        # unknown service type requested, return null
        else:
            return None

# get_3_workers()
#   Purpose: Returns three randomly selected workers of a specific type (ipv4 or ipv6)
#            by repeatedly calling get_worker() until three unique workers are returned
#   Params:
#     - type: 'ipv4' or 'ipv6' denotes the type of service check required
#   Returns: Three Worker objects in an array
def get_3_workers(type):
    # requires at least three workers to be registered with the server
    if (len(workers) < 3):
        return None
    three_workers = []
    current_worker = None
    # continue looping until three unique workers are obtained
    while (True):
        if (len(three_workers) == 3):
            return three_workers
        current_worker = get_worker(type)
        duplicate = False
        # make sure the returned worker is not already in the array before continuing
        for w in three_workers:
            if w.name == current_worker.name:
                # worker is a duplicate, do not add worker to the array
                duplicate = True
                break
        # worker is not duplicate, add to the array
        if (not duplicate):
            three_workers.append(current_worker)

# worker_dispatcher()
#   Purpose: A ZeroMQ listener that receives requests from tasks to find three workers
#            capable of handling the service request
#   Params: (none)
#   Returns: Three Worker uri's in an array via ZeroMQ
def worker_dispatcher():
    print("Started worker_dispatcher thread...")
    # ZeroMQ "reply" (REP) socket listening on port 6668 of localhost
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    dispatcher_host = config['workers']['dispatcher_host']
    dispatcher_port = config['workers']['dispatcher_port']
    socket.bind("tcp://" + dispatcher_host + ":" + dispatcher_port)

    # continuously listen for requests over zmq
    while (True):
        message = socket.recv_json()
        # get three workers based on the service check type requested
        workers = get_3_workers(message['request'])
        if (workers is not None):
            results = [None] * 3 # initialize the return array
            # fill array with three workers' uri
            for i in range(len(workers)):
                worker_uri = "http://" + str(workers[i].node_ip) + ":" + str(workers[i].node_port)
                results[i] = worker_uri
        else:
            results = None
        # send serialized json back over the zmq socket
        socket.send_json(results)

# main()
#   Purpose: Initialize the worker manager component and kick off the worker inactivity
#            thread, the worker dispatcher thread, and the Twisted factory endpoint
#   Params: (none)
#   Returns: (none)
def main():
    print("Started worker_mgr.py...")

    # read pypatrol config
    global config
    config = configparser.ConfigParser()
    config.read('pypatrol.conf')

    global secrets
    secrets = json.loads(config['workers']['secrets'])
    random.seed() # seed random to increase entropy

    # Start Worker Inactivity check thread
    t = threading.Thread(target=check_workers, name='check_workers')
    t.setDaemon(True)
    t.start()

    # Start Worker Dispatcher thread
    d = threading.Thread(target=worker_dispatcher, name='worker_dispatcher')
    d.setDaemon(True)
    d.start()

    # Start Twisted pyPatrol node worker endpoint
    f = Factory()
    f.protocol = WorkerQueue
    endpoint_port = int(config['workers']['endpoint_port'])
    reactor.listenTCP(endpoint_port, f)
    reactor.run(installSignalHandlers=0)

if __name__ == '__main__':
    main()
