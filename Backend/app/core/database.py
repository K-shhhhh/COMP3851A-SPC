"""
Database configuration.

Actual PostgreSQL integration will be added later.
"""


class Database:
    def connect(self):
        print("Connecting to PostgreSQL...")

    def disconnect(self):
        print("Closing database connection...")


database = Database()