import sqlite3
from contextlib import contextmanager

class Database:
    # Initializes the database
    def init_app(self, app):
        # Gets the path to the database and sets the database path to it
        self.db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        # Create tables if they don't exist
        with self.get_db() as conn:
            self._create_tables(conn)

    # Ensures that the resources are allocated and closed while and after this function is called.
    @contextmanager
    # Allows for us to open a connection the database within a "with" statement
    def get_db(self):
        # Connects to the databse
        conn = sqlite3.connect(self.db_path)
        # Allows for us to access rows by name instead of index
        conn.row_factory = sqlite3.Row
        # Specifies that conn is able to be used in a with statement until it is completed in which case it will end the connection
        try:
            yield conn
        finally:
            conn.close()

    # Creates the tables in the database
    def create_tables(self, conn):
        # Creates the fabricators table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS Fabricators (
                dbID INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                hwid TEXT NOT NULL,
                name TEXT NOT NULL,
                date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                devicePort TEXT NOT NULL
            )
        ''')

        # Creates the Jobs table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS Jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file BLOB,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                fabricator_id INTEGER,
                fabricator_name TEXT,
                td_id INTEGER,
                error_id INTEGER,
                comments TEXT,
                file_name_original TEXT NOT NULL,
                favorite BOOLEAN NOT NULL DEFAULT 0,
                FOREIGN KEY (fabricator_id) REFERENCES Fabricators (dbID),
                FOREIGN KEY (error_id) REFERENCES Issues (id)
            )
        ''')

        # Creates the Issues table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS Issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue TEXT NOT NULL,
                job_id INTEGER,
                FOREIGN KEY (job_id) REFERENCES Jobs (id)

            )
        ''')
        # Updates the database
        conn.commit()
# Creates a database object
db = Database()