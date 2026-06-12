import argparse
import sys
import threading
from http.server import ThreadingHTTPServer

from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView

from web_app import GarageWebHandler, add_inference_arguments, start_web_runtime


class GarageWebViewWindow(QMainWindow):
    def __init__(self, server: ThreadingHTTPServer, url: str):
        super().__init__()
        self.server = server
        self.setWindowTitle("地库车辆定位系统")

        self.webview = QWebEngineView(self)
        self.webview.setUrl(QUrl(url))
        self.setCentralWidget(self.webview)
        self.resize(1440, 900)
        self.showMaximized()

    def closeEvent(self, event):
        self.server.shutdown()
        self.server.server_close()
        event.accept()


def start_server(host: str, port: int):
    server = ThreadingHTTPServer((host, port), GarageWebHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main():
    parser = argparse.ArgumentParser(description="地库车辆定位系统桌面 WebView 壳")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=0, type=int, help="默认 0 表示自动选择可用端口")
    add_inference_arguments(parser)
    args = parser.parse_args()

    runtime = start_web_runtime(args)
    server = start_server(args.host, args.port)
    actual_host, actual_port = server.server_address
    url = f"http://{actual_host}:{actual_port}/"

    app = QApplication(sys.argv)
    window = GarageWebViewWindow(server, url)
    window.show()
    print(f"Garage Locator Desktop WebView is running at {url}")
    try:
        sys.exit(app.exec_())
    finally:
        if runtime:
            runtime.stop()


if __name__ == "__main__":
    main()
