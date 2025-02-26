from azure.cosmos import CosmosClient, exceptions

COSMOS_URL = "your_cosmos_db_url"
COSMOS_KEY = "your_cosmos_db_key"
DATABASE_NAME = "your_database_name"
CONTAINER_NAME = "your_container_name"

client = CosmosClient(COSMOS_URL, COSMOS_KEY)
database = client.get_database_client(DATABASE_NAME)
container = database.get_container_client(CONTAINER_NAME)

def save_barcode_data(barcode, name):
    item = {
        'id': barcode,
        'name': name
    }
    try:
        container.upsert_item(item)
    except exceptions.CosmosHttpResponseError as e:
        print(f"An error occurred: {e.message}")