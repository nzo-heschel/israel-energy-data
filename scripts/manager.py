import threading

from scripts import server, charts
# run the server in a thread
t1 = threading.Thread(target=server.main)
t1.start()
# run the charts dash app in the main thread
charts.main()
