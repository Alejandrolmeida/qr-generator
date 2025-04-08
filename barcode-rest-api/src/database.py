import os
from datetime import datetime
import pytz
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from dotenv import load_dotenv

# Cargar el archivo .env relativo al script actual
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# Read environment variables
COSMOS_URL = os.getenv("COSMOS_URL")
COSMOS_KEY = os.getenv("COSMOS_KEY")
DATABASE_NAME = os.getenv("DATABASE_NAME")
CONTAINER_NAME = os.getenv("CONTAINER_NAME")

# Validate that all required environment variables are present
if not all([COSMOS_URL, COSMOS_KEY, DATABASE_NAME, CONTAINER_NAME]):
    raise ValueError("One or more required environment variables (COSMOS_URL, COSMOS_KEY, DATABASE_NAME, CONTAINER_NAME) are missing.")

client = CosmosClient(COSMOS_URL, COSMOS_KEY)

# Create the database if it does not exist
database = client.create_database_if_not_exists(id=DATABASE_NAME)

# Create the container if it does not exist, using 'name' as the partition key
container = database.create_container_if_not_exists(
    id=CONTAINER_NAME,
    partition_key=PartitionKey(path="/name"),
    offer_throughput=400
)

def save_to_database(barcode, name):
    madrid_tz = pytz.timezone('Europe/Madrid')
    item = {
        'id': barcode,  # using barcode as unique id 
        'name': name,
        'timestamp': datetime.now(madrid_tz).isoformat()  # add Madrid timezone-aware timestamp
    }
    try:
        container.upsert_item(item)
    except exceptions.CosmosHttpResponseError as e:
        print(f"An error occurred: {e.message}")