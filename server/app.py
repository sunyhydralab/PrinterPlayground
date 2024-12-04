import asyncio
import logging
import sys
import threading
import uuid

from flask import request, Response, send_from_directory, Flask, current_app as flask_current_app
from flask_cors import CORS
import os
from flask_migrate import Migrate
from dotenv import load_dotenv
import shutil
from flask_socketio import SocketIO
import websockets
from routes import defineRoutes
from werkzeug.local import LocalProxy
from Classes.EventEmitter import EventEmitter
from controllers.emulator import emulator_bp  # import the blueprint

emulator_connections = {}
event_emitter = EventEmitter()

async def websocket_server():
    async def handle_client(websocket):
        client_id = str(uuid.uuid4())

        print(f"Emulator websocket connected: {client_id}")

        emulator_connections[client_id] = websocket

        try:
            while True:
                message = await websocket.recv()
                assert isinstance(message, str), f"Received non-string message: {message}, Type: ({type(message)})"
                #print(f"Received message from {client_id}: {message}")

                event_emitter.emit("message_received", client_id, message)

                if not hasattr(emulator_connections[client_id],"fake_port"):
                    fake_port = message.split('port":"')[-1].split('",')[0]
                    print(f"Fake port: {fake_port}" if fake_port else "No fake port found")
                    if fake_port:
                        emulator_connections[client_id].fake_port = fake_port
                    fake_name = message.split('Name":"')[-1].split('",')[0]
                    print(f"Fake name: {fake_name}" if fake_name else "No fake name found")
                    if fake_name:
                        emulator_connections[client_id].fake_name = fake_name
                    fake_hwid = message.split('Hwid":"')[-1].split('",')[0]
                    print(f"Fake Hwid: {fake_hwid}" if fake_hwid else "No fake Hwid found")
                    if fake_hwid:
                        emulator_connections[client_id].fake_hwid = fake_hwid
                else:
                    print(f"Fake port: {emulator_connections[client_id].fake_port}")
                    print(f"Fake name: {emulator_connections[client_id].fake_name}")
                    print(f"Fake Hwid: {emulator_connections[client_id].fake_hwid}")
                #await websocket.send(f"Echo from {client_id}: {message}")
        except websockets.exceptions.ConnectionClosed as e:
            # Handle disconnection gracefully
            print(f"Emulator '{client_id}' has been disconnected.")
        except Exception as e:
            # Handle any other exception (unexpected disconnection, etc.)
            print(f"Error with client {client_id}: {e}")
        finally:
             if client_id in emulator_connections:
                del emulator_connections[client_id]

    try:
        server = await websockets.serve(handle_client, "localhost", 8001)
        await server.wait_closed()
    except Exception as e:
        print(f"WebSocket server error: {e}")

def start_websocket():
    print("Starting WebSocket server...")
    asyncio.run(websocket_server())

websocket_thread = threading.Thread(target=start_websocket)
websocket_thread.daemon = True  # Make it a daemon thread to exit with the main program
websocket_thread.start()

# Global variables
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
uploads_folder = os.path.abspath(os.path.join(root_path, 'uploads'))


# moved this up here so we can pass the app to the PrinterStatusService
# Basic app setup 
class MyFlaskApp(Flask):
    def __init__(self):
        from models.config import Config
        from Classes.FabricatorList import FabricatorList
        from models.db import db

        super().__init__(__name__, static_folder=os.path.abspath(os.path.join(root_path, "client", "dist")))
        self._logger = None
        from Classes.Logger import Logger
        logs = os.path.join(root_path, "server", "logs")
        os.makedirs(logs, exist_ok=True)
        self.logger = Logger("App", consoleLogger=sys.stdout, fileLogger=os.path.abspath(os.path.join(logs, f"{__name__}.log")),
                            consoleLevel=logging.ERROR)
        self.config.from_object(__name__) # update application instantly
        # start database connection
        self.config["environment"] = Config.get('environment')
        self.config["ip"] = Config.get('ip')
        self.config["port"] = Config.get('port')
        self.config["base_url"] = Config.get('base_url')

        load_dotenv()
        basedir = os.path.abspath(os.path.join(root_path, "server"))
        database_file = os.path.abspath(os.path.join(basedir, Config.get('database_uri')))
        if isinstance(database_file, bytes):
            database_file = database_file.decode('utf-8')
        databaseuri = 'sqlite:///' + database_file
        self.config['SQLALCHEMY_DATABASE_URI'] = databaseuri
        self.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(self)

        Migrate(self, db)

        self.socketio = SocketIO(self, cors_allowed_origins="*", engineio_logger=False, socketio_logger=False,
                            async_mode='eventlet' if self.config["environment"] == 'production' else 'threading',
                            transport=['websocket', 'polling'])  # make it eventlet on production!

        self.emulator_connections = emulator_connections
        self.event_emitter = event_emitter

        CORS(self)

        # Register all routes
        defineRoutes(self)
        self.register_blueprint(emulator_bp, url_prefix='/api', name='emulator_bp')  # Register the emulator blueprint with a unique name

        self.fabricator_list = FabricatorList(self)

        @self.cli.command("test")
        def run_tests():
            """Run all tests."""
            import subprocess
            subprocess.run(["python", "../Tests/parallel_test_runner.py"])

        @self.before_request
        def handle_preflight():
            if request.method == "OPTIONS":
                res = Response()
                res.headers['X-Content-Type-Options'] = '*'
                res.headers['Access-Control-Allow-Origin'] = '*'
                res.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
                res.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
                return res

        # Serve static files
        @self.route('/')
        def serve_static(path='index.html'):
            return send_from_directory(self.static_folder, path)

        @self.route('/assets/<path:filename>')
        def serve_assets(filename):
            return send_from_directory(os.path.join(self.static_folder, 'assets'), filename)

        @self.socketio.on('ping')
        def handle_ping():
            self.socketio.emit('pong')

        @self.socketio.on('connect')
        def handle_connect():
            print("Client connected")


    @property
    def logger(self):
        return self._logger

    @logger.setter
    def logger(self, logger):
        self._logger = logger

    @logger.getter
    def logger(self):
        return self._logger

    def handle_errors_and_logging(self, e: Exception | str, fabricator=None):
        from Classes.Fabricators.Fabricator import Fabricator
        device = fabricator
        if isinstance(fabricator, Fabricator):
            device = fabricator.device
        if device is not None and hasattr(device, "logger") and device.logger is not None:
            device.logger.error(e, stacklevel=3)
        elif self.logger is None:
            if isinstance(e, str):
                print(e.strip())
            else:
                import traceback
                print(traceback.format_exception(None, e, e.__traceback__))
        else:
            self.logger.error(e, stacklevel=3)
        return False

    def get_emu_ports(self):
        fake_device = next(iter(self.emulator_connections.values()), None)
        if fake_device:
            return [fake_device.fake_port, fake_device.fake_name, fake_device.fake_hwid]
        return [None, None, None]

def _find_custom_app():
    app = flask_current_app._get_current_object()
    return app if isinstance(app, MyFlaskApp) else None

current_app = LocalProxy(_find_custom_app)

app = MyFlaskApp()

# own thread
with app.app_context():
    try:
        # Define directory paths for uploads and tempcsv
        uploads_folder = os.path.abspath('../uploads')
        tempcsv = os.path.abspath('../tempcsv')
        # Check if directories exist and handle them accordingly
        for folder in [uploads_folder, tempcsv]:
            if os.path.exists(folder):
                # Remove the folder and all its contents
                shutil.rmtree(folder)
                app.logger.info(f"{folder} removed and will be recreated.")
            # Recreate the folder
            os.makedirs(folder)
            app.logger.info(f"{folder} recreated as an empty directory.")

    except Exception as e:
        # Log any exceptions for troubleshooting
        app.handle_errors_and_logging(e)

def run_socketio(app):
    try:
        app.socketio.run(app, allow_unsafe_werkzeug=True)
    except Exception as e:
        app.handle_errors_and_logging(e)

if __name__ == "__main__":
    # If hits last line in GCode file: 
        # query for status ("done printing"), update. Use frontend to update status to "ready" once user removes print from plate. 
        # Before sending to printer, query for status. If error, throw error. 
    # since we are using socketio, we need to use socketio.run instead of app.run
    # which passes the app anyways
    run_socketio(app)  # Replace app.run with socketio.run
