import os
from dotenv import load_dotenv
import psycopg2
import sqlalchemy
import pandas as pd
import io
from googleapiclient.discovery import build
from google.oauth2 import service_account

load_dotenv()
db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT')
db_name = os.getenv('DB_NAME')
db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')

google_cred = os.getenv('GOOGLE_CREDENTIALS_PATH')
folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
try:
    credentials = service_account.Credentials.from_service_account_file(
        google_cred,
        scopes=['https://www.googleapis.com/auth/drive.readonly']
    )

    drive_service = build('drive', 'v3', credentials=credentials)

    results = drive_service.files().list(
        q=f"'{folder_id}' in parents and mimeType='text/csv'",
        fields="files(id, name)"
    ).execute()

    files = results.get('files',[])

    engine = sqlalchemy.create_engine(
        f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode=require"
    )

    for file in files:
        name = file['name'].replace('.csv', '')  # use filename without extension as table name
        file_id = file['id']
        
        # download file content from Drive
        request = drive_service.files().get_media(fileId=file_id)
        file_content = request.execute()
        
        # read into pandas
        df = pd.read_csv(io.BytesIO(file_content))
        
        # write to Supabase
        df.to_sql(name, engine, if_exists='replace', index=False)
        
        print(f"{name} loaded into Supabase with {df.shape[0]} rows")

except Exception as e:
    print(e)

finally:
    engine.dispose()