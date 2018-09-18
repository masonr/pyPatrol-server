from worker_mgr import Worker
from datetime import datetime
import psycopg2, threading, requests, json, smtplib

smtp_server = 'smtp.example.com'
smtp_ssl_port = 465
smtp_user = 'no-reply@example.com'
smtp_pass = 'changme123'

def notify_user(service, new_status):
    cur_status = service[5]
    conn = None
    try:
        conn = psycopg2.connect(host="localhost", database="pypatrol_test", user="pypatrol", password="onaroll")
        cur = conn.cursor()
        cur.execute("SELECT * FROM alert_contact WHERE user_id = %s" % service[1])
        alert = cur.fetchone()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

    if alert is not None:
        print("SEND EMAIL TO: " + alert[3])
        server = smtplib.SMTP_SSL(smtp_server, smtp_ssl_port)
        server.login(smtp_user, smtp_pass)
        msg = "\nHello,\n\nYour service " + service[4] \
            + " has been detected as " + new_status + " at " \
            + service[9].strftime("%Y-%m-%d %H:%M:%S") + ".\n\n" + "Regards,\n-pyPatrol Team"
        server.sendmail("notify@rowe.sh", alert[3], msg)

        try:
            conn = psycopg2.connect(host="localhost", database="pypatrol_test", user="pypatrol", password="onaroll")
            cur = conn.cursor()
            cur.execute("UPDATE service SET status = '%s', error_state = FALSE, status_change_time = NOW() WHERE id = %s" % (new_status, service[0]))
            conn.commit()
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
        finally:
            if conn is not None:
                conn.close()


def check_for_status_change(service, results):
    print(results)
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
        conn = psycopg2.connect(host="localhost", database="pypatrol_test", user="pypatrol", password="onaroll")
        cur = conn.cursor()
        if ((status == 'error' and cur_error_state) or (status == cur_status)):
            # service already in error state, skip
            return
        elif (status == 'error' and not cur_error_state):
            cur.execute("UPDATE service SET error_state = TRUE WHERE id = %s" % service[0])
            conn.commit()
            cur.close()
        elif (status != cur_status):
            cur.execute("UPDATE service SET status = '%s' WHERE id = %s" % (status, service[0]))
            conn.commit()
            cur.close()
            notify_user(service, status)
        elif (status == cur_status and cur_error_state):
            cur.execute("UPDATE service SET error_state = FALSE WHERE id = %s" % service[0])
            conn.commit()
            cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

def execute_task(data, worker_uri, results, index):
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    r = requests.post(worker_uri, data=json.dumps(data), headers=headers, timeout=20)
    results[index] = json.loads(r.text)

def orchestrate(data, workers):
    if workers is None:
        return

    conn = None
    service_id = None
    service_type = None
    service_url = ""
    post_data = None
    try:
        conn = psycopg2.connect(host="localhost", database="pypatrol_test", user="pypatrol", password="onaroll")
        cur = conn.cursor()
        service_id = data[0]
        service_type = data[3]
        if (service_type in {1, 2, 5, 6}):
            cur.execute("SELECT * FROM ip_port_service WHERE ip_port_service.service_id = %s" % service_id)
            service = cur.fetchone()
            #print("service id: " + str(service_id) + ", service: " + service)
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

    threads = [None] * 3
    results = [None] * 3

    for i in range(len(workers)):
        worker_uri = workers[i] + service_url
        print("worker_uri: " + worker_uri)
        threads[i] = threading.Thread(target=execute_task, args=(post_data, worker_uri, results, i))
        threads[i].start()

    for i in range(len(threads)):
        threads[i].join()

    check_for_status_change(data, results)
