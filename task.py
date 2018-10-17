# task.py
# Author: Mason Rowe <mason@rowe.sh>
# Project: pyPatrol-server
# License: WTFPL <http://www.wtfpl.net/>
# Last Updated: 15 Oct 2018
#
# Purpose: Dispatches a single service check to three pyPatrol-node workers and checks
#          the results for a status change. If a status change has occured, notify the
#          user.

from worker_mgr import Worker
from datetime import datetime
import psycopg2, threading, requests, json, smtplib, configparser

# initialize config parser
config = None

# initialize database parameters
db_host = ""
db_port = 0
db_database = ""
db_user = ""
db_pass = ""

# initialize smtp parameters
smtp_server = ""
smtp_port = 0
smtp_user = ""
smtp_pass = ""

# notify_user()
#   Purpose: A change in state of a service was detected, alert the user
#   Params:
#     - service: service check details
#     - new_status: the current status of the service (after a new service check)
#   Returns: (none)
def notify_user(service, new_status):
    cur_status = service[5] # current (previous) status of the service
    conn = None
    try:
        conn = psycopg2.connect(host=db_host, port=db_port, database=db_database, user=db_user, password=db_pass)
        cur = conn.cursor()
        cur.execute("SELECT * FROM alert_contact WHERE user_id = %s" % service[1])
        alert = cur.fetchone()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

    # found alert contact
    if alert is not None:
        # send alert email to user
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(smtp_user, smtp_pass)
        msg = "\nHello,\n\nYour service " + service[4] \
            + " has been detected as " + new_status + " at " \
            + service[9].strftime("%Y-%m-%d %H:%M:%S") + ".\n\n" + "Regards,\n-pyPatrol Team"
        server.sendmail(smtp_user, alert[3], msg)

        # update the status of the service to the new state
        try:
            conn = psycopg2.connect(host=db_host, port=db_port, database=db_database, user=db_user, password=db_pass)
            cur = conn.cursor()
            cur.execute("UPDATE service SET status = '%s', error_state = FALSE, status_change_time = NOW() WHERE id = %s" % (new_status, service[0]))
            conn.commit()
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
        finally:
            if conn is not None:
                conn.close()

# check_for_status_change()
#   Purpose: Checks the results of a service check to see if the status state has changed.
#            If the state has changed, then notify the user (notify_user())
#   Params:
#     - service: service check details
#     - results: array containing the results from a dispatched service check task (3 entries)
#   Returns: (none)
def check_for_status_change(service, results):
    # get the new service status, the status state must have consensus from at least two worker results
    if (results[0]['status'] == results[1]['status'] or results[0]['status'] == results[2]['status']):
        status = results[0]['status']
    elif (results[1]['status'] == results[2]['status']):
        status = results[1]['status']
    else:
        status = 'error'

    cur_error_state = service[7]
    cur_status = service[5]
    conn = None
    try:
        conn = psycopg2.connect(host=db_host, port=db_port, database=db_database, user=db_user, password=db_pass)
        cur = conn.cursor()
        if ((status == 'error' and cur_error_state) or (status == cur_status)):
            # service already in error state or status has not changed, skip
            return
        elif (status == 'error' and not cur_error_state):
            # service is now in an error state while not being in an error state previously
            cur.execute("UPDATE service SET error_state = TRUE WHERE id = %s" % service[0])
            conn.commit()
            cur.close()
        elif (status != cur_status):
            # service status has changed, notify the user
            notify_user(service, status)
        elif (status == cur_status and cur_error_state):
            # service is no longer in an error state
            cur.execute("UPDATE service SET error_state = FALSE WHERE id = %s" % service[0])
            conn.commit()
            cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

# execute_task()
#   Purpose: Sends the pyPatrol service check request to the pyPatrol-node worker and
#            waits for the results of the service check
#   Params:
#     - data: service check details
#     - worker_uri: http endpoint to send the task to the pypatrol-node worker
#     - results: results array for placing the status values returned from the worker
#     - index: index within the results array to place the returned status
#   Returns: (none)
def execute_task(data, worker_uri, results, index):
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    timeout_interval = int(config['tasks']['http_timeout'])
    try:
        r = requests.post(worker_uri, data=json.dumps(data), headers=headers, timeout=timeout_interval)
        results[index] = json.loads(r.text)
    except requests.exceptions.RequestException as e:
        print(e)
        err = { 'status': 'error' }
        results[index] = err

# orchestrate()
#   Purpose: Orchestrates the dispersing of the service check task to the three workers,
#            collects the status results, and calls to see if the status has changed
#   Params:
#     - data: service check details
#     - workers: array of three pypatrol-node worker URIs
#   Returns: (none)
def orchestrate(data, workers):
    # if for some reason no worker URIs were given, exit
    if workers is None:
        return

    # read pypatrol config
    global config
    config = configparser.ConfigParser()
    config.read('pypatrol.conf')

    # populate PSQL settings
    global db_host, db_port, db_database, db_user, db_pass
    db_host = config['database']['host']
    db_port = int(config['database']['port'])
    db_database = config['database']['database']
    db_user = config['database']['user']
    db_pass = config['database']['password']

    # populate SMTP settings
    global smtp_server, smtp_port, smtp_user, smtp_password
    smtp_server = config['mail']['smtp_server']
    smtp_port = int(config['mail']['smtp_port'])
    smtp_user = config['mail']['smtp_user']
    smtp_password = config['mail']['smtp_password']

    conn = None
    service_id = None
    service_type = None
    service_url = ""
    post_data = None
    # determine which service check type the service corresponds to and populate the revelant details
    #   in the data portion of the post request
    try:
        conn = psycopg2.connect(host=db_host, port=db_port, database=db_database, user=db_user, password=db_pass)
        cur = conn.cursor()
        service_id = data[0]
        service_type = data[3]
        # ip_port_service service check type
        if (service_type in {1, 2, 5, 6}):
            cur.execute("SELECT * FROM ip_port_service WHERE ip_port_service.service_id = %s" % service_id)
            service = cur.fetchone()
            if (service_type == 1): service_url = "/ping"
            elif (service_type == 2): service_url = "/ping6"
            elif (service_type == 5): service_url = "/tcp_socket"
            elif (service_type == 6): service_url = "/steam_server"

            port = service[3] if service[3] is not None else ""
            post_data = {
                'ip': service[2],
                'port': port
            }
            cur.close()
        # http_service service check type
        elif (service_type == 3):
            cur.execute("SELECT * FROM http_service WHERE http_service.service_id = %s" % service_id)
            service = cur.fetchone()
            service_url = "/http_response"
            post_data = {
                'hostname': service[2],
                'redirects': service[3],
                'check_string': service[4],
                'keywords': service[5]
            }
            cur.close()
        # cert_service service check type
        elif (service_type == 4):
            cur.execute("SELECT * FROM cert_service WHERE cert_service.service_id = %s" % service_id)
            service = cur.fetchone()
            service_url = "/cert"
            post_data = {
                'hostname': service[2],
                'buffer': int(service[3])
            }
            cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

    # initialize the threads and results array for the service checks
    threads = [None] * 3
    results = [None] * 3

    # create a new thread to send the service check to each of the three workers
    for i in range(len(workers)):
        worker_uri = workers[i] + service_url
        threads[i] = threading.Thread(target=execute_task, args=(post_data, worker_uri, results, i))
        threads[i].start()

    # wait until all three threads return, results are stored in the results array
    for i in range(len(threads)):
        threads[i].join()

    # determine if a status change has occured and if so, notify the user
    check_for_status_change(data, results)
