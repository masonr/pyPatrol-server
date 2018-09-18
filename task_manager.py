import job, task, worker_mgr
import psycopg2, time, zmq, threading

def send_task(data, workers):
    task.orchestrate(data, workers)

def process_tasks(tasks):
    conn = None
    context = None
    try:
        conn = psycopg2.connect(host="localhost", database="pypatrol_test", user="pypatrol", password="onaroll")
        cur = conn.cursor()
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect("tcp://127.0.0.1:6668")
        for task in tasks:
            msg = { 'request' : 'workers' }
            socket.send_json(msg)
            reply = socket.recv_json()
            #print("Received reply: " + str(reply))
            t = threading.Thread(target=send_task, args=(task, reply))
            t.start()
            cur.execute("UPDATE service SET last_check_time = NOW() WHERE id = %s" % task[0])
        print("Updating %s rows" % len(tasks))
        conn.commit()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

def check_for_new_tasks():
    conn = None
    try:
        conn = psycopg2.connect(host="localhost", database="pypatrol_test", user="pypatrol", password="onaroll")
        cur = conn.cursor()
        cur.execute("SELECT * FROM service WHERE NOW() >= (service.last_check_time + (service.interval * interval '1 sec'))")
        rows = cur.fetchall()
        #for row in rows:
        #    print(row)
        if len(rows) > 0:
            process_tasks(rows)
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

def main():
    print('Started task_manager.py...')
    while (True):
        check_for_new_tasks()
        time.sleep(5)

if __name__ == '__main__':
    main()
