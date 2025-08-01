import pymongo
import pandas as pd
from urllib.parse import quote_plus

# Encode username & password
username = "admin"
password = "Gurpreet@23"  # Keep it empty if there's no password

encoded_username = quote_plus(username)
encoded_password = quote_plus(password)

# Correct MongoDB Connection URI
MONGO_URI = f"mongodb://{encoded_username}:{encoded_password}@3.86.209.148:27017/Gardening_Companion?authSource=admin"
mongo_client = pymongo.MongoClient(MONGO_URI)

db = mongo_client["Gardening_Companion"]
collection = db["plants"]

# Read the Excel file
def read_excel_file(file_path):
    try:
        data = pd.read_excel(file_path)
        return data
    except Exception as e:
        print(f"❌ Failed to read Excel file: {e}")
        return None

# Insert data into MongoDB
def insert_data_into_mongodb(data):
    try:
        for index, row in data.iterrows():
            # ✅ Ensure Image URL is stored as string only
            imageURL = row.get('Image URL', '')  # Default to empty string if missing

            if not isinstance(imageURL, str):
                imageURL = ''  # ✅ Convert NaN/float to empty string

            document = {
                "commonName": row.get('Common Name', ''),
                "scientificName": row.get('Scientific Name', ''),
                "familyCommonName": row.get('Family Common Name', ''),
                "edible": row.get('Edible', ''),
                "saplingDescription": row.get('Sapling Description', ''),
                "genus": row.get('Genus', ''),
                "imageURL": imageURL,
                  "rank":row.get('Rank',''),  # ✅ Store Image URL as string
            }
            collection.insert_one(document)
        print("✅ Data inserted successfully!")
    except Exception as e:
        print(f"❌ Failed to insert data into MongoDB: {e}")

# Main function
def main():
    file_path = "/home/gurpreet/Downloads/final.xlsx"  # Replace with your Excel file path
    data = read_excel_file(file_path)
    if data is not None:
        insert_data_into_mongodb(data)

if __name__ == "__main__":
    main()
