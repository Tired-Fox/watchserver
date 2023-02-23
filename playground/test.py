from time import sleep

from liveserver import LiveServer

liveserver = LiveServer(base="pages/")

try:
    print(f"Serving at http://localhost:{liveserver.port}!")
    liveserver.start()
    while True:
        sleep(1)
except KeyboardInterrupt:
    print("Shutting down...")
    liveserver.stop()
