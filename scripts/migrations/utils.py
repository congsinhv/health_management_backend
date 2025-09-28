from urllib.parse import urlparse, unquote
import psycopg2
from migrations import config


def database_connect():
    """Connect to the PostgreSQL database server"""
    r = urlparse(config.DATABASE_URI)
    conn_args = {
        "host": r.hostname,
        "database": r.path[1:],
        "user": r.username,
        "password": unquote(r.password),
        "port": r.port,
    }

    conn = None
    try:
        # connect to the PostgreSQL server
        print("Connecting to the PostgreSQL database...")
        conn = psycopg2.connect(**conn_args)
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        # sys.exit(1)
    print("Connection successful")
    return conn
