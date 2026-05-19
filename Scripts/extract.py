import os
from dotenv import load_dotenv
import psycopg2
import pandas as pd
import awswrangler as wr
import boto3

load_dotenv()

db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT')
db_name = os.getenv('DB_NAME')
db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')

access = os.getenv('AWS_ACCESS_KEY_ID')
secret = os.getenv('AWS_SECRET_ACCESS_KEY')
region = os.getenv('AWS_REGION')
bucket = os.getenv('S3_BUCKET_NAME')

try:
    db_connection = psycopg2.connect(
        host = db_host,
        port = db_port,
        dbname = db_name,
        user = db_user,
        password = db_password,
        sslmode='require'
        )

    session = boto3.Session(
        aws_access_key_id = access,
        aws_secret_access_key = secret,
        region_name = region
    )

    cursor = db_connection.cursor()
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='public'
    """)
    tables = [row[0] for row in cursor.fetchall()]

    for table in tables:
        df = pd.read_sql(f"SELECT * FROM {table}",db_connection)
        wr.s3.to_csv(
            df=df,
            path = f"s3://{bucket}/landing/{table}",
            mode = 'overwrite',
            dataset = True,
            index=False,
            boto3_session= session
        )
        print(f"{table} table has been added to landing page with {df.shape[0]} rows")

except Exception as e:
    print(e)

finally:
    try:
        cursor.close()
        db_connection.close()
    except:
        pass 