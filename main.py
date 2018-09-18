import threading
import time

def run_worker_mgr():
    import worker_mgr
    worker_mgr.main()

def run_task_mgr():
    import task_manager
    task_manager.main()

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
        print('Hello, still alive here!')
        time.sleep(30)

if __name__ == '__main__':
    main()
