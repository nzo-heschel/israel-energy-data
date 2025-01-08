import threading
import logging
import time

import ischedule
import psutil

from scripts import server, charts

FORMAT = '%(asctime)s [%(levelname)s] : %(message)s'
logging.basicConfig(format=FORMAT, level=logging.INFO)

def log_memory_usage():
    total_mb = psutil.virtual_memory().total / 1024 / 1024
    used_mb = psutil.virtual_memory().used / 1024 / 1024
    pct = used_mb / total_mb
    logging.info(f"Memory usage: {total_mb:,.0f} MB total, {used_mb:,.0f} MB used ({pct:.2f}%)")


def shcedule_mem_usage():
    interval = 600
    log_memory_usage()
    logging.info("Scheduling mem usage thread every %s seconds", interval)
    ischedule.schedule(log_memory_usage, interval=interval)
    ischedule.run_loop()


# run the server and memory usage logging in threads
threading.Thread(target=server.main).start()
threading.Thread(target=shcedule_mem_usage).start()
# wait for server to start
time.sleep(4)
# run the charts dash app in the main thread
charts.main()
