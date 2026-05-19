# HealthBridge Data Pipeline

## What is this project?

HealthBridge Diagnostics Ltd. is a healthcare diagnostics provider that handles lab testing, diagnostic imaging, and digital health reporting. The company processes thousands of patient records every day across multiple diagnostic centres, and all of that data lives in a PostgreSQL database.

The problem is that running analytical queries directly on a live transactional database slows it down and creates risk. Analysts need access to the data but shouldn't be querying production systems directly.

This pipeline solves that. It automatically pulls data out of the source database, stores it in a cloud data lake on AWS S3, cleans and optimises it, and makes it queryable through AWS Athena. Analysts get fast, reliable access to the data without ever touching the live system.

---

## How the pipeline works

```
Supabase (PostgreSQL)
        |
        |  psycopg2 / SQLAlchemy
        v
S3 Landing Zone (Raw CSV)
s3://healthbridge-datalake-ik/landing/{table}/
        |
        |  pandas + awswrangler
        v
S3 Processed Zone (Clean Parquet, Partitioned)
s3://healthbridge-datalake-ik/processed/{table}/year={}/month={}/
        |
        |  awswrangler catalog registration
        v
AWS Glue Data Catalog
(Stores table schemas, column types, partition info)
        |
        |  SQL
        v
AWS Athena
(Analytical queries directly on S3 data)
```

---

## Tools used

| Tool | What it does in this project |
|---|---|
| Supabase (PostgreSQL) | Source database storing all patient, appointment, lab and billing data |
| Python 3 | Main scripting language for the pipeline |
| psycopg2 | Connects Python to PostgreSQL to extract data |
| SQLAlchemy | Database engine used to load data into Supabase |
| pandas | Handles data manipulation and cleaning in memory |
| AWS S3 | Cloud storage for the data lake (landing and processed zones) |
| awswrangler | Reads and writes S3 data, registers tables in Glue catalog |
| boto3 | Manages the AWS session and authentication |
| AWS Glue | Stores metadata about the tables so Athena can query them |
| AWS Athena | Runs SQL queries directly against files in S3 |
| Google Drive API | Pulls source CSV files from a shared Drive folder automatically |
| python-dotenv | Loads credentials from a .env file so they are never hardcoded |

---

## Project structure

```
healthbridge-pipeline/
|
|-- scripts/
|   |-- load_to_supabase.py   # Loads CSVs from Google Drive into Supabase
|   |-- extract.py            # Extracts Supabase tables to S3 landing zone as CSV
|   |-- transform.py          # Cleans data and writes Parquet to S3 processed zone
|   |-- glue_catalog.py       # Registers processed tables in AWS Glue Data Catalog
|   |-- quality_checks.py     # Validates row counts and checks for nulls
|
|-- docs/                     # Architecture diagrams and notes
|-- data/                     # Local sample data (not committed to Git)
|-- .env                      # Credentials (never committed to Git)
|-- .gitignore
|-- requirements.txt
|-- README.md
```

---

## What each script does

### load_to_supabase.py
Connects to a shared Google Drive folder using a service account, finds all CSV files in that folder automatically, and loads each one into Supabase as a table. If new CSV files are added to the Drive folder later, the script picks them up without any code changes.

### extract.py
Connects to Supabase and queries the database internal schema table (information_schema.tables) to get a list of all tables automatically. This means if a new table is added to the database, the script picks it up on the next run without needing to be updated. Each table is extracted with a SELECT query and written to the S3 landing zone as a raw CSV file.

### transform.py
Reads the raw CSVs from the S3 landing zone. It discovers which tables are available by listing the folders in S3 automatically rather than relying on a hardcoded list. For each table it applies the following cleaning steps:

- Removes exact duplicate rows
- Removes completely empty rows
- Strips whitespace from column names
- Casts columns to their correct data types (IDs to integers, dates to timestamps, amounts to floats)

For tables that have a date column (appointments, payments, test_results), it extracts the year and month as separate partition columns before writing to S3. All tables are written to the processed zone as Parquet files.

### glue_catalog.py
Creates the healthbridge database in AWS Glue and registers each processed table with its schema and partition information. Once registered, the tables are visible and queryable in Athena.

### quality_checks.py
Runs after the pipeline to catch any issues. It compares row counts between Supabase and S3 to make sure no data was lost during extraction. It also checks all ID columns across every table for null values. Results are printed as a report.

---

## How to run it

### Requirements
- Python 3.8 or above
- AWS account with access to S3, Glue, and Athena
- Supabase project
- Google Cloud project with the Drive API enabled

### Setup

Clone the repo and navigate into it:
```bash
git clone https://github.com/Ikay106/healthbridge-pipeline.git
cd healthbridge-pipeline
```

Create and activate a virtual environment:
```bash
python -m venv venv
venv\Scripts\activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Create a .env file in the root folder with the following:
```
DB_HOST=your-supabase-host
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres.your-project-id
DB_PASSWORD=your-password

AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=eu-west-1
S3_BUCKET_NAME=your-bucket-name

GOOGLE_CREDENTIALS_PATH=google_credentials.json
GOOGLE_DRIVE_FOLDER_ID=your-folder-id
```

### Run the pipeline in order

```bash
python scripts/load_to_supabase.py
python scripts/extract.py
python scripts/transform.py
python scripts/glue_catalog.py
python scripts/quality_checks.py
```

---

## Athena queries

### Daily diagnostic volume
```sql
SELECT DATE(appointment_date) AS date,
       COUNT(*) AS total_appointments
FROM appointments
GROUP BY DATE(appointment_date)
ORDER BY date;
```

### Top performing test categories
```sql
SELECT test_name, COUNT(test_results.test_id) AS total
FROM test_results
JOIN tests ON test_results.test_id = tests.test_id
GROUP BY test_name
ORDER BY total DESC;
```

### Revenue by diagnostic center
```sql
SELECT center_name, ROUND(SUM(amount), 2) AS total_revenue
FROM payments
JOIN appointments ON payments.patient_id = appointments.patient_id
JOIN centers ON appointments.center_id = centers.center_id
GROUP BY center_name
ORDER BY total_revenue DESC;
```

### Patient visit trends by month
```sql
SELECT year, month, COUNT(appointment_id) AS total_visits
FROM appointments
GROUP BY year, month
ORDER BY year DESC, month;
```

---

## Data tables

| Table | Rows | Description |
|---|---|---|
| patients | 5,000 | Patient demographic records |
| appointments | 20,000 | Patient appointment bookings |
| test_results | 80,000 | Laboratory test outcomes |
| payments | 20,000 | Billing and payment records |
| centers | 10 | Diagnostic centre details |
| tests | 5 | Test category reference data |

---

## Design decisions

**Two S3 zones instead of one**

The landing zone keeps the raw data exactly as it came out of the database. If something goes wrong during transformation, the raw data is still there and can be reprocessed without going back to the source database.

**Parquet instead of CSV in the processed zone**

Parquet stores data column by column rather than row by row. This means a query that only needs two columns out of ten only reads those two columns, which is much faster and cheaper when using Athena (which charges per byte scanned).

**Partitioning by year and month**

When Athena queries a partitioned table and you filter by year or month, it skips all the other folders entirely. A query for one specific month reads only that month's files instead of the full dataset. This is called partition pruning.

**Dynamic table discovery**

Neither the extraction script nor the transformation script has a hardcoded list of table names. The extraction script asks the database what tables exist. The transformation script asks S3 what folders exist in the landing zone. This means new tables are handled automatically without touching the code.
