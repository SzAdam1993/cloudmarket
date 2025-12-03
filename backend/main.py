import os
import boto3
import uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- KONFIGURÁCIÓ (Környezeti változókból) ---
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "db") # 'db' a docker service neve
DB_NAME = os.getenv("DB_NAME", "marketdb")
AWS_BUCKET = os.getenv("AWS_BUCKET_NAME", "my-test-bucket")
AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")

# Adatbázis URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

# --- INITIALIZATION ---
app = FastAPI()

# CORS engedélyezése (hogy a Frontend elérje a Backendet)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Adatbázis setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# S3 Kliens
s3_client = boto3.client('s3')

# --- DB MODELL ---
class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    price = Column(Float)
    description = Column(String)
    image_url = Column(String)

# Táblák létrehozása indításkor
Base.metadata.create_all(bind=engine)

# --- ENDPOINTS ---

@app.get("/")
def read_root():
    return {"message": "CloudMarket API is running!"}

@app.get("/products")
def get_products():
    db = SessionLocal()
    products = db.query(Product).all()
    db.close()
    return products

@app.post("/products")
async def create_product(
    name: str = Form(...),
    price: float = Form(...),
    description: str = Form(...),
    file: UploadFile = File(...)
):
    # 1. Kép feltöltése S3-ra
    file_extension = file.filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{file_extension}"
    
    try:
        # Ha nincs beállítva AWS kulcs, ez hibát dob, de lokálisan kezeljük
        s3_client.upload_fileobj(file.file, AWS_BUCKET, filename)
        image_url = f"https://{AWS_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{filename}"
    except Exception as e:
        print(f"S3 Error (running locally without keys?): {e}")
        # Fallback teszteléshez, ha nincs S3 beállítva
        image_url = "https://via.placeholder.com/150"

    # 2. Adat mentése DB-be
    db = SessionLocal()
    new_product = Product(name=name, price=price, description=description, image_url=image_url)
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    db.close()

    return new_product