"""
HotReloader
-----------
Uses kaki module for Hot Reload (limited to some uses cases).
Before using, install kaki by `pip install kaki`

"""

import os
from threading import Thread
import socket
from kaki.app import App as HotReloaderApp  # NOQA: E402
from kivy.factory import Factory
from kivy.logger import LOG_LEVELS, Logger  # NOQA: E402
from kivy import platform
from kivy.clock import Clock
from kivy.core.window import Window  # NOQA: E402
from kivymd.app import MDApp  # NOQA: E402
import pickle
# This is needed for supporting Windows 10 with OpenGL < v2.0
from kivymd.toast.kivytoast import toast

if platform == "android":
    from kvdroid import device_info

if platform == "win":
    os.environ["KIVY_GL_BACKEND"] = "angle_sdl2"
Logger.setLevel(LOG_LEVELS["debug"])


class KivyLive(MDApp, HotReloaderApp):
    DEBUG = 1  # To enable Hot Reload

    # *.kv files to watch
    KV_FILES = [f"libs/libkv/{kv_file}" for kv_file in os.listdir("libs/libkv")]

    # Class to watch from *.py files
    # You need to register the *.py files in libs/uix/baseclass/*.py
    CLASSES = {"Root": "libs.libpy.root", "Home": "libs.libpy.home"}

    # Auto Reloader Path
    AUTORELOADER_PATHS = [
        (".", {"recursive": True}),
    ]

    AUTORELOADER_IGNORE_PATTERNS = [
        "*.pyc", "*__pycache__*", "*p4a_env_vars.txt*", "*sitecustomize.py*", "*/.kivy*"
    ]

    def __init__(self, **kwargs):
        super(KivyLive, self).__init__(**kwargs)
        self.current = "home"
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False
        self.HEADER_LENGTH = 64
        Window.soft_input_mode = "below_target"
        self.title = "KivyLiveUi"

        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.primary_hue = "500"

        self.theme_cls.accent_palette = "Amber"
        self.theme_cls.accent_hue = "500"

        self.theme_cls.theme_style = "Light"

    def build_app(self):  # build_app works like build method
        return Factory.Root()

    def on_rebuild(self, *args):
        if self.connected:
            self.root.children[0].current = self.current

    def thread_server_connection(self, ip):
        toast(f"establishing connection to {ip}:6051", background=self.theme_cls.primary_color) if ":" not in ip else \
            toast(f"establishing connection to {ip.split(':')[0]}: {ip.split(':')[1]}",
                  background=self.theme_cls.primary_color)
        Thread(target=self.connect2server, args=(ip,)).start()

    def connect2server(self, ip):
        port = 6051
        try:
            if ":" in ip:
                port = ip.split(":")[1]
            self.client_socket.connect((ip.split(":")[0], port))
            self.connected = True
            Clock.schedule_once(
                lambda x: toast("Connection Established Successfully", background=self.theme_cls.primary_color))
            Logger.info(f"{ip}>6050: Connection Established")
            Thread(target=self.listen_4_update).start()
        except (OSError, socket.gaierror) as e:
            self.connected = False
            exception = e
            Clock.schedule_once(lambda x: toast(f"{exception}", background=[1, 0, 0, 1]))
        except:
            pass

    def listen_4_update(self):
        try:
            _header = int(self.client_socket.recv(self.HEADER_LENGTH))
            _iter_chunks = _header // 1000
            _chunk_remainder = _header % 1000
            data = [
                self.client_socket.recv(1000)
                for _ in range(_iter_chunks)
                if _iter_chunks >= 1
            ]
            data.append(self.client_socket.recv(_chunk_remainder))
            data = b"".join(data)
            load_initial_code = pickle.loads(data)
        except pickle.UnpicklingError as e:
            exception = e
            Logger.error(exception)
            Clock.schedule_once(lambda x: toast(f"{exception}"))
            Logger.info("UNPICKLING ERROR: It seems there was an unpickling error, Just hit the connect button again")
            self.client_socket.close()
            del self.client_socket
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            return
        except ConnectionError as e:
            exception = e
            Logger.error(exception)
            Clock.schedule_once(lambda x: toast(f"{exception}"))
            Logger.info("SERVER DOWN?: Maybe, just check your server")
            Clock.schedule_once(lambda x: toast(f"{exception}"))
            return

        for i in load_initial_code:
            file_path = os.path.split(i)[0]
            try:
                os.makedirs(file_path)
            except (FileExistsError, FileNotFoundError) as e:
                Logger.debug(f"{e} : Ignore this")
            if os.path.split(i)[1] == "Main.py":
                continue
            with open(
                    os.path.join(file_path, os.path.split(i)[1]), "wb" if type(load_initial_code[i]) == bytes else "w"
            ) as f:
                f.write(load_initial_code[i])
                f.close()
        try:
            while True:
                header = self.client_socket.recv(self.HEADER_LENGTH)
                # if not len(header):
                #     Clock.schedule_once(
                #         lambda x: toast("IS SERVER DOWN: Shutting down the connection", background=[1, 0, 0, 1])
                #     )
                #     Logger.info("SERVER DOWN: Shutting down the connection")
                message_length = int(header)
                __chunks = message_length // 1000
                __remainder = message_length % 1000
                code_data = [
                    self.client_socket.recv(1000)
                    for _ in range(__chunks)
                    if __chunks >= 1
                ]
                code_data.append(self.client_socket.recv(__remainder)) if __remainder else None
                code_data = b"".join(code_data)
                try:
                    _data = pickle.loads(code_data)
                except pickle.UnpicklingError as e:
                    Logger.error(e)
                    Logger.info(f"Re-save: Save Your file again on the Client Updater(KivyLiveClient)")
                    continue
                self.update_code(_data)
        except (BrokenPipeError, ConnectionError, socket.error) as e:
            Logger.error(e)
            Clock.schedule_once(lambda x: toast("SERVER DOWN: Shutting down the connection", background=[1, 0, 0, 1]))
            Logger.info("SERVER DOWN: Shutting down the connection")

    def update_code(self, code_data):
        # write code
        file = code_data["data"]["file"]
        with open(file if file != "liveappmain.py" else "Main.py", "w") as f:
            f.write(code_data["data"]["code"])
        Logger.info(f"FILE UPDATE: {file} was updated by {code_data['address']}")
        Clock.schedule_once(
            lambda x: toast(f"{file} was updated by {code_data['address']}", background=self.theme_cls.primary_color)
        )


if __name__ == "__main__":
    KivyLive().run()
