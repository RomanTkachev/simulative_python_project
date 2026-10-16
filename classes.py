import psycopg2 
import os
from psycopg2.extras import execute_values

class DatabaseConnection: 

    __instance = None

    def __init__(self):
        if DatabaseConnection.__instance:
            raise Exception('Это Singleton, для получения инстанса используй метод get_instance')
        else:
            self.connection = psycopg2.connect(
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", 5432)),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD"),
                dbname=os.getenv("DB_NAME", "postgres"),
)
            DatabaseConnection.__instance = self 

    @staticmethod
    def get_instance():
        if DatabaseConnection.__instance:
            return DatabaseConnection.__instance
        else:
            return DatabaseConnection()

    def get_connection(self):
        return self.connection

class DatabaseOperations: 

    def __init__(self, connection):
        self.connection = connection

    def check_connection(self):
        cur = self.connection.cursor()
        cur.execute("SELECT version();")
        print(cur.fetchone())
        cur.close()

    def check_last_date(self):
        cur = self.connection.cursor()
        cur.execute('''select max(date(created_at)) as max_date 
                       from it_resume.grader_usage;''')
        last_date = cur.fetchone()
        cur.close()
        return last_date[0]


    def insert_rows(self, rows):

        if not rows:
            return 0

        query = ''' INSERT INTO it_resume.grader_usage (
                                    user_id, 
                                    oauth_consumer_key, 
                                    lis_result_sourcedid, 
                                    lis_outcome_service_url, 
                                    is_correct, 
                                    attempt_type, 
                                    created_at
                                ) 
                                VALUES %s ON CONFLICT (user_id, created_at) DO NOTHING 
                                RETURNING user_id;''' #не вставляем дубли

        try:
            with self.connection.cursor() as cursor:
                inserted = len(execute_values(
                    cursor, query, rows, page_size=1000, fetch=True
                ))
            self.connection.commit()
            return inserted

        except Exception:
            self.connection.rollback()
            raise


    def close_connection(self):
        self.connection.close()
