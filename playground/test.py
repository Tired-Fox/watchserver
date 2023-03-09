from time import sleep

from watchserver import LiveServer

liveserver = LiveServer(
    base="pages/",
    ignore_list=["**/pages/blog/*"],
    auto_open=None #"pages/"
)

try:
    print(f"Serving at http://localhost:{liveserver.port}!")
    liveserver.start()
    while True:
        sleep(1)
except KeyboardInterrupt:
    print("Shutting down...")
    liveserver.stop()
