import os 
from dotenv import load_dotenv
import boto3
import awswrangler as wr


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

    wr.catalog.create_database(
        name='healthbridge',
        exist_ok=True,
        boto3_session=session
    )

    objects = wr.s3.list_objects(f"s3://{bucket}/processed/", boto3_session=session)
    tables = list(set([obj.split('/')[4] for obj in objects]))

    partition_config = {
    "appointments": "appointment_date",
    "payments": "payment_date",
    "test_results": "test_date"
    }

    for table in tables:
        df = wr.s3.read_parquet(f"s3://{bucket}/processed/{table}/",boto3_session=session)
        df = df.loc[:, ~df.columns.str.startswith('Unnamed')]
        columns_types, _ = wr.catalog.extract_athena_types(df)

        if table in partition_config:
            partitions_types = {'year': 'int', 'month': 'int'}
        else:
            partitions_types = {}
            
        wr.catalog.create_parquet_table(
            database='healthbridge',
            table=table,
            path=f"s3://{bucket}/processed/{table}/",
            columns_types=columns_types,
            partitions_types=partitions_types,
            mode='overwrite',
            boto3_session=session
            )
        print(f"{table} added to glue catalogue")

except Exception as e:
    print(e)

