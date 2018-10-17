# main.py
# Author: Mason Rowe
# Project: pyPatrol-server
# License: WTFPL <http://www.wtfpl.net/>
# Last Updated: 11 Oct 2018
#
# Purpose: Kicks off the pyPatrol-server workflow by spawing the worker manager and
#          the task manager threads

import threading, time

def run_worker_mgr():
    import worker_mgr
    worker_mgr.main()

def run_task_mgr():
    import task_mgr
    task_mgr.main()

def main():
    # Start Worker Manager thread
    wm = threading.Thread(target=run_worker_mgr, name='worker_mgr')
    wm.setDaemon(True)
    wm.start()

    # Start Task Manager thread
    tm = threading.Thread(target=run_task_mgr, name='task_mgr')
    tm.setDaemon(True)
    tm.start()

    # Keep alive
    while (True):
        print('pyPatrol... chugging along!')
        time.sleep(120)

if __name__ == '__main__':
    main()
