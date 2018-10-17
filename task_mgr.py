# task_mgr.py
# Author: Mason Rowe <mason@rowe.sh>
# Project: pyPatrol-server
# License: WTFPL <http://www.wtfpl.net/>
# Last Updated: 15 Oct 2018
#
# Purpose: Manages service checks registered in the pyPatrol database. Will continuously
#          check the database for expired service checks. If any checks need to be executed,
#          each check is placed within its own task in a non-blocking thread

import task, worker_mgr
import psycopg2, time, zmq, threading, configparser

# initialize config parser
config = None

# initialize database parameters
db_host = ""
db_port = 0
db_database = ""
db_user = ""
db_pass = ""

# send_task()
#   Purpose: Helper method to be able to spawn a task in a new thread
#   Params:
#     - data: service check details required for a pyPatrol-node worker
#     - workers: array containing pyPatrol-node worker URI's for task dispatch
#   Returns: (none)
def send_task(data, workers):
    task.orchestrate(data, workers)

# process_tasks()
#   Purpose: Takes an array of tasks whose last check time > check interval and spawns
#            each task to be processed in its own thread. Also updates last check time
#   Params:
#     - tasks: array of tasks which require a new updated service check
#   Returns: (none)
def process_tasks(tasks):
    conn = None
    context = None
    try:
        conn = psycopg2.connect(host=db_host, port=db_port, database=db_database, user=db_user, password=db_pass)
        cur = conn.cursor()
        # initialize zeromq request message to obtain three workers from the worker manger
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        dispatcher_host = config['workers']['dispatcher_host']
        dispatcher_port = config['workers']['dispatcher_port']
        socket.connect("tcp://" + dispatcher_host + ":" + dispatcher_port)
        # get workers for each service check task and send each task to its own thread
        for task in tasks:
            type = 'ipv6' if int(task[3]) == 2 else 'ipv4' # ipv6 if ping6 task, otherwise ipv4
            msg = { 'request' : type }
            socket.send_json(msg)
            # worker manager returns three workers
            reply = socket.recv_json()
            # spawn task thread
            t = threading.Thread(target=send_task, args=(task, reply))
            t.start()
            # update last check time in the database for that service check
            cur.execute("UPDATE service SET last_check_time = NOW() WHERE id = %s" % task[0])
        print("Updating %s rows" % len(tasks))
        conn.commit()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

# check_for_new_tasks()
#   Purpose: Poll the database, check if any service checks need to be re-executed (when
#   the last_check_time > check interval), and dispatch these checks as tasks
#   Params: (none)
#   Returns: (none)
def check_for_new_tasks():
    conn = None
    try:
        conn = psycopg2.connect(host=db_host, port=db_port, database=db_database, user=db_user, password=db_pass)
        cur = conn.cursor()
        cur.execute("SELECT * FROM service WHERE NOW() >= (service.last_check_time + (service.interval * interval '1 sec'))")
        rows = cur.fetchall()
        # process any service checks that need to be executed
        if len(rows) > 0:
            process_tasks(rows)
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

# main()
#   Purpose: Continuously check the database for expired service checks
#   Params: (none)
#   Returns: (none)
def main():
    print('Started task_manager.py...')

    # read pypatrol config
    global config
    config = configparser.ConfigParser()
    config.read('pypatrol.conf')

    global db_host, db_port, db_database, db_user, db_pass
    db_host = config['database']['host']
    db_port = int(config['database']['port'])
    db_database = config['database']['database']
    db_user = config['database']['user']
    db_pass = config['database']['password']

    interval = int(config['tasks']['db_poll_interval'])

    while (True):
        check_for_new_tasks()
        time.sleep(interval)

if __name__ == '__main__':
    main()
