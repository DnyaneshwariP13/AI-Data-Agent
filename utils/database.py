#Complete class where connection object is created
#2. we can fetch all the information about the database and tables from the connection object and store it in a variable, so that we can use it later to generate the prompt for the agent
'''
import psycopg2


class DatabaseUtil:
    def __init__(self, db_config):
        """
        Initializes the DatabaseUtil class with the provided database configuration.

        Args:
            db_config (dict): A dictionary containing database connection parameters.
        """
        self.db_config = db_config

        try:
            self.connection = psycopg2.connect(**self.db_config)
        except Exception as e:
            print(f"Error connecting to the database: {e}")
            self.connection = None


    def schema_details(self,schema_name):
        schema_info_context= ""
        connection = self.connection
        cursor= connection.cursor() #obj we get with postgres connection and with help of which we run the queries

        schema_info_context=f"Database Schema:{schema_name}\n"

        try:
            cursor.execute(f"SELECT table_name FROM information_schema.tables WHERE table_schema = %s;", (schema_name,))
            tables = cursor.fetchall()

            schema_info_context += "Tables:\n"

            for table in tables:
                table_name= table[0]
                schema_info_context = f"{schema_info_context}Table Name: {table_name}\n"

                #Adding columns and data types for each table
                cursor.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = %s AND table_name = %s;", (schema_name, table_name))
                column_list=cursor.fetchall()

                for column in column_list:
                    column_name= column[0]
                    data_type= column[1]
                    schema_info_context = f"{schema_info_context}Column Name: {column_name}, Data Type: {data_type}\n"

                #Adding sample data
                cursor.execute(f"SELECT * FROM {schema_name}.{table_name} LIMIT 5;")
                sample_data= cursor.fetchall()
                schema_info_context = f"{schema_info_context}Sample Data: {sample_data}\n"
                for row in sample_data:
                    schema_info_context = f"{schema_info_context}{row}\n"

            
        except Exception as e:
            print(f"Error fetching schema details: {e}")
            schema_info_context = "Error fetching schema details."

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

        return schema_info_context
    
    def execute_sql(self, query):
        try:
            connection = self.connection
            cursor = connection.cursor()
            cursor.execute(query)
            result = cursor.fetchall()
            connection.commit()
            return str(result)
        except Exception as e:
            print(f"Error executing query: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
                
obj=DatabaseUtil({
    'host': 'localhost',
    'port': 5432,
    'database': 'postgres',
    'user': 'postgres',
    'password': 'dnya'
})

result=obj.schema_details('public')

with open("test_schema_details.txt", "w") as f:
    f.write(result)'''


import psycopg2
import psycopg2.extras
import json


class DatabaseUtil:
    def __init__(self, conn_details: dict):
        # Store only the config — do NOT open a shared connection
        self.conn_details = conn_details

    def _connect(self):
        """Open a fresh connection. Caller is responsible for closing it."""
        return psycopg2.connect(**self.conn_details)

    # ------------------------------------------------------------------ #
    def schema_details(self, schema_name: str = "public") -> str:
        """
        Return a formatted string describing every table in the schema:
        table name, columns + types, and a few sample rows.
        """
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = %s
                      AND table_type = 'BASE TABLE'
                    ORDER BY table_name;
                    """,
                    (schema_name,),
                )
                tables = [row["table_name"] for row in cur.fetchall()]

                lines = []
                for table in tables:
                    lines.append(f"TABLE: {table}")

                    cur.execute(
                        """
                        SELECT column_name, data_type
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s
                        ORDER BY ordinal_position;
                        """,
                        (schema_name, table),
                    )
                    for col in cur.fetchall():
                        lines.append(f"  - {col['column_name']} ({col['data_type']})")

                    try:
                        cur.execute(
                            f'SELECT * FROM "{schema_name}"."{table}" LIMIT 3;'
                        )
                        samples = cur.fetchall()
                        if samples:
                            lines.append("  Sample rows:")
                            for s in samples:
                                lines.append(f"    {dict(s)}")
                    except Exception as sample_err:
                        lines.append(f"  (sample rows unavailable: {sample_err})")

                    lines.append("")  # blank line between tables

                return "\n".join(lines)
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    def execute_sql(self, sql_query: str):
        """Execute a read-only SQL query, return list of dicts (or [] on error)."""
        conn = self._connect()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cursor.execute(sql_query)
            rows = cursor.fetchall()
            return [dict(r) for r in rows] if rows else []
        except Exception as e:
            print(f"Error executing query: {e}")
            return []
        finally:
            cursor.close()
            conn.close()