import os
from dotenv import load_dotenv
import boto3
import awswrangler as wr
import pandas as pd

load_dotenv()

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

    partition_config ={
        "payments":"payment_date",
        "appointments":"appointment_date",
        "test_results":"test_date",
    }
    
    type_config = {
    'patient_id': 'int',
    'appointment_id': 'int',
    'center_id': 'int',
    'result_id': 'int',
    'test_id': 'int',
    'payment_id': 'int',
    'dob': 'date',
    'created_at': 'timestamp',
    'appointment_date': 'timestamp',
    'test_date': 'timestamp',
    'payment_date': 'timestamp',
    'result_value': 'float',
    'amount': 'float',
    'price': 'float'
    }

    objects = wr.s3.list_objects(f"s3://{bucket}/landing/", boto3_session=session)
    tables = list(set([obj.split('/')[4] for obj in objects]))

    for table in tables:
        df = wr.s3.read_csv(f"s3://{bucket}/landing/{table}/",boto3_session=session)
        df = df.drop_duplicates()
        df = df.dropna(how='all')
        df.columns = df.columns.str.strip()

        for col, dtype in type_config.items():
            if col in df.columns:
                if dtype == 'int':
                    df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
                elif dtype in ['date', 'timestamp']:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                elif dtype == 'float':
                    df[col] = pd.to_numeric(df[col], errors='coerce')

        if table in partition_config:
            date_col = partition_config[table]
            df[date_col] = pd.to_datetime(df[date_col])
            df['year'] = df[date_col].dt.year
            df['month'] = df[date_col].dt.month
            wr.s3.to_parquet(
                df =df,
                path= f"s3://{bucket}/processed/{table}/",
                partition_cols=['year', 'month'],
                mode = 'overwrite',
                dataset = True,
                boto3_session= session
            )
        
        else:
            wr.s3.to_parquet(
            df =df,
            path= f"s3://{bucket}/processed/{table}/",
            mode = 'overwrite',
            dataset = True,
            boto3_session= session
        )
        print(f"{table} has been processed")

except Exception as e:
    print(e)

finally:
    print("transformation complete")