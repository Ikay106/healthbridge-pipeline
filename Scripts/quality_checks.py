import os
from dotenv import load_dotenv
import pandas as pd
import awswrangler as wr 
import boto3
import psycopg2

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
    session = boto3.Session(
        aws_access_key_id = access,
        aws_secret_access_key = secret,
        region_name = region
    )
    db_connection = psycopg2.connect(
        host = db_host,
        port = db_port,
        dbname = db_name,
        user = db_user,
        password = db_password,
        sslmode='require'
        )

    cursor= db_connection.cursor()

    cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema='public'
        """)
    tables = [row[0] for row in cursor.fetchall()]
    quality_report = []

    for table in tables:
        cursor.execute(f"""
            SELECT COUNT(*) FROM {table}
        """)
        supabase_count = cursor.fetchone()[0]

        df = wr.s3.read_parquet(f"s3://{bucket}/processed/{table}/",boto3_session=session)
        s3_count= len(df)

        quality_report.append({
        'table': table,
        'supabase_count': supabase_count,
        's3_count': s3_count,
        'match': supabase_count == s3_count
        })

        id_columns = [col for col in df.columns if col.endswith('_id')]
        for col in id_columns:
            null_count = df[col].isnull().sum()
            null_pct = (null_count / len(df)) * 100
            print(f"{table} - {col} nulls: {null_count} ({null_pct:.2f}%)")

    report_df = pd.DataFrame(quality_report)
    print(report_df)

except Exception as e:
    print(e)

finally:
    try:
        cursor.close()
        db_connection.close()
    except:
        pass