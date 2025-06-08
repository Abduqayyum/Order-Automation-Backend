import io
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Form, BackgroundTasks, Request, status
import os
from fastapi.responses import JSONResponse
import filetype
from google import genai
from google.genai import types
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import re
from fastapi import BackgroundTasks
from datetime import datetime
import json
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import timedelta
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import logging
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

import crud, models, schemas
import auth_crud, auth_models, auth_schemas
from auth_utils import (create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES,
                       create_refresh_token, is_valid_refresh_token, get_user_from_refresh_token,
                       revoke_refresh_token, revoke_all_user_tokens)

from database import SessionLocal, engine, get_db, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME, CHAT_ID, BOT_TOKEN

from pydantic import BaseModel


def send_to_telegram(contents: bytes, filename: str, orders_data: list):
    import requests

    message = f"🧾 New Order Extracted:\n\n{json.dumps(orders_data, indent=2)}"

    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendAudio",
            data={"chat_id": CHAT_ID},
            files={"audio": (filename, io.BytesIO(contents))}
        )

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": message}
        )

    except Exception as e:
        print("Telegram send error:", e)


class Item(BaseModel):
    id: int
    quantity: int

def ensure_database_exists():
    logger = logging.getLogger("database_init")
    logger.setLevel(logging.INFO)
    
    try:
        logger.info(f"Checking if database {DB_NAME} exists...")
        conn = psycopg2.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT,
            database="postgres"  
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{DB_NAME}'")
        exists = cursor.fetchone()
        
        if not exists:
            logger.info(f"Creating database '{DB_NAME}'...")
            cursor.execute(f"CREATE DATABASE {DB_NAME}")
            logger.info("Database created successfully!")
        else:
            logger.info(f"Database '{DB_NAME}' already exists.")
        
        cursor.close()
        conn.close()
        
        return True
    except Exception as e:
        logger.error(f"Error creating database: {str(e)}")
        return False

ensure_database_exists()

models.Base.metadata.create_all(bind=engine)
auth_models.Base.metadata.create_all(bind=engine)

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", None)

client = genai.Client(api_key=GOOGLE_API_KEY)

class PromptRequest(BaseModel):
    text: str

def process_audio(audio_bytes, mime_type, prompt):
    response = client.models.generate_content(
            model='gemini-2.5-flash-preview-05-20',
            contents = [
                prompt,
                types.Part.from_bytes(
                    data=audio_bytes,
                    mime_type=mime_type
                )
            ]
        )

    return response.text

def summarize_order(prompt):
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )

    return response.text


app = FastAPI(title="Order Automation API", root_path="")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    error_message = str(exc)
    
    if isinstance(exc, IntegrityError):
        if "violates foreign key constraint" in error_message:
            if "products_organization_id_fkey" in error_message:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "The specified organization does not exist. Please use a valid organization ID."}
                )
            elif "orders_organization_id_fkey" in error_message:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "The specified organization does not exist. Please use a valid organization ID."}
                )
    
    return JSONResponse(
        status_code=400,
        content={"detail": f"Database error: {error_message}"})


allowed_file_types = ["audio/wav", "audio/mp3", "audio/aiff", "audio/aac", "audio/ogg", "audio/flac", "audio/x-wav", "audio/mpeg"]

@app.post("/stt/")
async def transcribe_audio(audio: UploadFile = File(None), current_user: auth_models.User = Depends(get_current_user)):
    try:
        if audio is None:
            return JSONResponse(status_code=400, content={"success": {}, "error": {"description": {"Please upload a file!"}}})
        
        contents = await audio.read()
        kind = filetype.guess(contents)
        print(kind.mime, "file type")
        print("file name", audio.filename)

        if kind is None or kind.mime not in allowed_file_types:
            return JSONResponse(status_code=400, content={"success": {}, "error": {"description": f"Invalid file type. Only following audio files are accepted {allowed_file_types}."}})
        
        prompt = "Extract text from audio, conversation might happen only in three language uzbek, english, and russian. Print text in uzbek"

        extracted_text = process_audio(contents, kind.mime, prompt)
        
        return JSONResponse(status_code=200, content={"success": {"result": extracted_text}, "error": {}})
    
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": {}, "error": {"description": str(e)}})
        
    
@app.post("/summarize_order_from_audio/")
async def process_audio_file(background_tasks: BackgroundTasks, audio: UploadFile = File(None), current_user: auth_models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        if audio is None:
            return JSONResponse(status_code=400, content={"success": {}, "error": {"description": {"Please upload a file!"}}})
        
        contents = await audio.read()
        kind = filetype.guess(contents)
        print("file name", audio.filename)

        if kind is None or kind.mime not in allowed_file_types:
            return JSONResponse(status_code=400, content={"success": {}, "error": {"description": f"Invalid file type. Only following audio files are accepted {allowed_file_types}."}})
        
        if current_user.organization_id:
            products = auth_crud.get_products_by_organization(db, current_user.organization_id)
            # products_data = {product.label_for_ai: product.id for product in products}
            products_data = [{"id": product.id, "label_for_ai": product.label_for_ai} for product in products]
            print(products_data)
        else:
            products_data = list()

        filename = f"{datetime.utcnow().isoformat()}_{audio.filename}"
        
        mime_type = kind.mime

        response = client.models.generate_content(
            # model="gemini-2.0-flash",
            model = "gemini-2.5-flash-preview-05-20",
            contents = [
                f"""
                Here is the list of valid items you can use in the response: {products_data}

                Your task is to analyze the conversation audio and extract only the final confirmed orders based on this list.

                Strictly follow these rules:

                - Only include items that are in the above list. If an item is not in the list, do NOT include it in the response.
                - Only include items that the speaker has clearly confirmed they want to order.
                - If an item is canceled, changed, or rejected during the conversation, do NOT include it.
                - The conversation may be in Uzbek, Russian, Tajik, or English. Accurately understand the language and context.
                - If the conversation is not about placing an order, return an empty list: []
                - Here the meaning of sizes in tajik: Small - Xutarak, Medium - Sredniy, Large - Kalun.

                Return the result as a JSON list **with no explanation**, only in this exact format:
                [
                {{"id": 1, "quantity": 1}},
                {{"id": 2, "quantity": 2}}
                ]

                If no valid items are ordered, return: []

                """,
                types.Part.from_bytes(
                    data=contents,
                    mime_type=mime_type
                )
            ],
            config={
                "response_mime_type": "application/json",
                "response_schema": list[Item],
            },
        )

        # print(response.text)

        orders: list[Item] = response.parsed
        orders_data = [{"item_id": dict(item)["id"], "quantity": dict(item)["quantity"]} for item in orders]
        orders_data_for_bot = [{"item_id": dict(item)["id"], "quantity": dict(item)["quantity"]} for item in orders]
        for order in orders_data_for_bot:
            for product in products_data:
                if product["id"] == order["item_id"]:
                    order["label_for_ai"] = product["label_for_ai"]

        background_tasks.add_task(send_to_telegram, contents, filename, orders_data_for_bot)
        return JSONResponse(
            status_code=200,
            content={
                "success": orders_data,
                "error": {} 
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": {},
                "error": str(e)
            }
        )

    
@app.post("/orders/", response_model=schemas.Order)
async def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db), current_user: auth_models.User = Depends(get_current_user)):
    db_order = models.Order(total_price=0.0, organization_id=current_user.organization_id)
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    
    total_price = 0.0
    for item_data in order.items:
        product = auth_crud.get_product(db, item_data.item_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Product with ID {item_data.item_id} not found")
            
        if not current_user.is_admin and product.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail=f"Access denied for product with ID {item_data.item_id}")
        
        item_price = product.price
        
        db_item = models.OrderItem(
            order_id=db_order.id,
            item_id=item_data.item_id,
            quantity=item_data.quantity,
            price=item_price
        )
        db.add(db_item)
        
        item_total = item_price * item_data.quantity
        total_price += item_total
    
    db_order.total_price = total_price
    
    db.commit()
    db.refresh(db_order)
    return db_order

@app.get("/orders/", response_model=List[schemas.Order])
async def read_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: auth_models.User = Depends(get_current_user)):
    if current_user.organization_id:
        return db.query(models.Order).filter(models.Order.organization_id == current_user.organization_id).offset(skip).limit(limit).all()
    if current_user.is_admin:
        return db.query(models.Order).offset(skip).limit(limit).all()
    return []

@app.get("/orders/{order_id}", response_model=schemas.Order)
async def read_order(order_id: int, db: Session = Depends(get_db), current_user: auth_models.User = Depends(get_current_user)):
    db_order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if not current_user.is_admin and (current_user.organization_id is None or current_user.organization_id != db_order.organization_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return db_order

@app.put("/orders/{order_id}", response_model=schemas.Order)
async def update_order(order_id: int, order: schemas.OrderCreate, db: Session = Depends(get_db), current_user: auth_models.User = Depends(get_current_user)):
    db_order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if not current_user.is_admin and (current_user.organization_id is None or current_user.organization_id != db_order.organization_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    db.query(models.OrderItem).filter(models.OrderItem.order_id == order_id).delete()
    
    total_price = 0.0
    for item_data in order.items:
        product = auth_crud.get_product(db, item_data.item_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Product with ID {item_data.item_id} not found")
            
        if not current_user.is_admin and product.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail=f"Access denied for product with ID {item_data.item_id}")
        
        item_price = product.price
        
        db_item = models.OrderItem(
            order_id=db_order.id,
            item_id=item_data.item_id,
            quantity=item_data.quantity,
            price=item_price
        )
        db.add(db_item)
        
        item_total = item_price * item_data.quantity
        total_price += item_total
    
    db_order.total_price = total_price
    
    db.commit()
    db.refresh(db_order)
    return db_order

@app.delete("/orders/{order_id}", response_model=bool)
async def delete_order(order_id: int, db: Session = Depends(get_db), current_user: auth_models.User = Depends(get_current_user)):
    db_order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if not current_user.is_admin and (current_user.organization_id is None or current_user.organization_id != db_order.organization_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    db.query(models.OrderItem).filter(models.OrderItem.order_id == order_id).delete()
    
    db.delete(db_order)
    db.commit()
    
    return True

@app.post("/register/", response_model=auth_schemas.User)
async def register_user(user: auth_schemas.UserCreate, db: Session = Depends(get_db)):
    return auth_crud.create_user(db=db, user=user)

@app.post("/login/", response_model=auth_schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(auth_models.User).filter(auth_models.User.username == form_data.username).first()
    
    if not user or not user.verify_password(form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    refresh_token, _ = create_refresh_token(db, user.id)
    
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@app.post("/refresh/", response_model=auth_schemas.Token)
async def refresh_access_token(refresh_request: auth_schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    if not is_valid_refresh_token(db, refresh_request.refresh_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = get_user_from_refresh_token(db, refresh_request.refresh_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "refresh_token": refresh_request.refresh_token, "token_type": "bearer"}

@app.post("/logout/")
async def logout(refresh_request: auth_schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    success = revoke_refresh_token(db, refresh_request.refresh_token)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid refresh token"
        )
    
    return {"message": "Successfully logged out"}

@app.get("/users/me/", response_model=auth_schemas.User)
async def read_users_me(current_user: auth_models.User = Depends(get_current_user)):
    return current_user


@app.post("/products/", response_model=schemas.Product)
async def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db), current_user: auth_models.User = Depends(get_current_user)):
    try:
        if not current_user.is_admin:
            if current_user.organization_id is None:
                raise HTTPException(status_code=403, detail="You must belong to an organization to create products")
            product.organization_id = current_user.organization_id
        else:
            organization = auth_crud.get_organization(db, product.organization_id)
            if not organization:
                raise HTTPException(status_code=400, detail=f"Organization with ID {product.organization_id} does not exist")
        
        return auth_crud.create_product(db=db, product=product)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error creating product: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred while creating the product: {str(e)}")

@app.get("/products/", response_model=List[schemas.Product])
async def read_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: auth_models.User = Depends(get_current_user)):
    if current_user.organization_id:
        return auth_crud.get_products_by_organization(db, organization_id=current_user.organization_id, skip=skip, limit=limit)
    if current_user.is_admin:
        return db.query(models.Product).offset(skip).limit(limit).all()
    return []

@app.get("/products/{product_id}", response_model=schemas.Product)
async def read_product(product_id: int, db: Session = Depends(get_db), current_user: auth_models.User = Depends(get_current_user)):
    db_product = auth_crud.get_product(db, product_id=product_id)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if not current_user.is_admin and current_user.organization_id != db_product.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return db_product

@app.put("/products/{product_id}", response_model=schemas.Product)
async def update_product(product_id: int, product: schemas.ProductCreate, db: Session = Depends(get_db), current_user: auth_models.User = Depends(get_current_user)):
    try:
        db_product = auth_crud.get_product(db, product_id=product_id)
        if db_product is None:
            raise HTTPException(status_code=404, detail="Product not found")
            
        if not current_user.is_admin and current_user.organization_id != db_product.organization_id:
            raise HTTPException(status_code=403, detail="You can only update products from your organization")
            
        if not current_user.is_admin:
            if current_user.organization_id is None:
                raise HTTPException(status_code=403, detail="You must belong to an organization to update products")
            product.organization_id = current_user.organization_id
        else:
            organization = auth_crud.get_organization(db, product.organization_id)
            if not organization:
                raise HTTPException(status_code=400, detail=f"Organization with ID {product.organization_id} does not exist")
            
        return auth_crud.update_product(db=db, product_id=product_id, product_data=product)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating product: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred while updating the product: {str(e)}")

@app.delete("/products/{product_id}")
async def delete_product(product_id: int, db: Session = Depends(get_db), current_user: auth_models.User = Depends(get_current_user)):
    try:
        db_product = auth_crud.get_product(db, product_id=product_id)
        if db_product is None:
            raise HTTPException(status_code=404, detail="Product not found")
            
        if not current_user.is_admin and current_user.organization_id != db_product.organization_id:
            raise HTTPException(status_code=403, detail="You can only delete products from your organization")
        
        if not current_user.is_admin and current_user.organization_id is None:
            raise HTTPException(status_code=403, detail="You must belong to an organization to delete products")
            
        return auth_crud.delete_product(db=db, product_id=product_id)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting product: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred while deleting the product: {str(e)}")

# @app.put("/users/{user_id}/organization/{organization_id}", response_model=auth_schemas.User)
# async def assign_user_to_organization(user_id: int, organization_id: int, db: Session = Depends(get_db), current_user: auth_models.User = Depends(get_current_user)):
#     if not current_user.is_admin:
#         raise HTTPException(status_code=403, detail="Only admin users can assign users to organizations")
#     return auth_crud.update_user_organization(db=db, user_id=user_id, organization_id=organization_id)


@app.get("/")
async def main_page():
    return JSONResponse(status_code=200, content={"status": "test app is working!"})


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=6000, reload=True, forwarded_allow_ips="*")