import io
from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, status
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
import json
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import timedelta

import crud, models, schemas
import auth_crud, auth_models, auth_schemas
from auth_utils import (create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES,
                       create_refresh_token, is_valid_refresh_token, get_user_from_refresh_token,
                       revoke_refresh_token, revoke_all_user_tokens)
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)
auth_models.Base.metadata.create_all(bind=engine)

load_dotenv()

items_data = {
    "espresso": {
        "id": 1, 
        "size": ["M"]
    },
    "americano": {
        "id": 2, 
        "size": ["S", "M", "L"]
    },
    "cappuccino": {
        "id": 3, 
        "size": ["S", "M", "L"]
    },
    "latte": {
        "id": 4, 
        "size": ["M", "L"]
    },
    "raf": {
        "id": 5, 
        "size": ["S", "M", "L"]
    },
    "flat_white": {
        "id": 6, 
        "size": ["M"]
    },
    "mocha": {
        "id": 7, 
        "size": ["L"]
    },
    "lemon_tea": {
        "id": 8, 
        "size": ["S", "M", "L"]
    },
    "ginger_tea": {
        "id": 9, 
        "size": ["S", "M", "L"]
    },
    "sea_buckthorn": {
        "id": 10, 
        "size": ["S", "M", "L"]
    },
    "cranberry": {
        "id": 11, 
        "size": ["S", "M", "L"]
    },
    "raspberry_berry": {
        "id": 12, 
        "size": ["S", "M", "L"]
    },
    "cocoa": {
        "id": 13, 
        "size": ["L"]
    },
    "hot_chocolate": {
        "id": 14, 
        "size": ["L"]
    },
    "iced_americano": {
        "id": 15, 
        "size": ["M", "L"]
    },
    "iced_cappuccino": {
        "id": 16, 
        "size": ["M", "L"]
    },
    "iced_latte": {
        "id": 17, 
        "size": ["M", "L"]
    },
    "iced_raf": {
        "id": 18, 
        "size": ["M", "L"]
    },
    "frappuccino": {
        "id": 19, 
        "size": ["M", "L"]
    },
    "mojito_classic": {
        "id": 20, 
        "size": ["M", "L"]
    },
    "mojito_energy": {
        "id": 21, 
        "size": ["M", "L"]
    },
    "mojito": {
        "id": 22, 
        "size": ["M", "L"]
    },
    "iced_tea": {
        "id": 23, 
        "size": ["M", "L"]
    },
    "dairy_milkshake": {
        "id": 24, 
        "size": ["M", "L"]
    },
    "chocolate_milkshake": {
        "id": 25, 
        "size": ["M", "L"]
    },
    "banana_milkshake": {
        "id": 26, 
        "size": ["M", "L"]
    },
    "milkshake_alt": {
        "id": 27, 
        "size": ["M", "L"]
    },
    "cup_of_icecream": {
        "id": 28,
        "size": ["L", "S"]
    },
    "wafers_of_icecream": {
        "id": 28,
        "size": ["L", "S"]
    },
    "0.5_kg_icecream": {
        "id": 29,
        "size": ["S"]
    }
}


GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", None)

client = genai.Client(api_key=GOOGLE_API_KEY)

class PromptRequest(BaseModel):
    text: str

def process_audio(audio_bytes, mime_type, prompt):
    response = client.models.generate_content(
            model='gemini-2.0-flash',
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origin_regex=r"https?://.*"
)

allowed_file_types = ["audio/wav", "audio/mp3", "audio/aiff", "audio/aac", "audio/ogg", "audio/flac", "audio/x-wav", "audio/mpeg"]

@app.post("/stt")
async def transcribe_audio(audio: UploadFile = File(None)):
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
        

@app.post("/summarize_order")
async def text_summarization(data: PromptRequest):
    try:
        # prompt = f"Summarize the whole text and just return list of orders (quantity) that the customer ordered. Here is the text: {data}"
        prompt = f"""
                    Suhbatda mijoz va xodim o‘rtasidagi buyurtma jarayoni mavjud. Sizdan talab qilinadi:

                    🟢 Faqat **mijozning yakuniy va tasdiqlangan buyurtmalarini** aniqlang (suhbat oxirida mijoz nima buyurtma bergan bo‘lsa, o‘shani).
                    🔴 Mijoz suhbat davomida o‘zgartirgan yoki bekor qilgan buyurtmalarni hisobga olmang.

                    📋 Natijani faqat quyidagi formatda qaytaring:
                    
                    {{
                    "orders": {{
                        "nomi": {{
                        "miqdori": 2,
                        "hajmi": S}}
                    }}
                    }}

                    ❌ Agar suhbat buyurtma bilan bog‘liq bo‘lmasa yoki hech qanday yakuniy buyurtma bo‘lmasa, quyidagicha bo‘lsin:

                    {{
                    "orders": {{}}
                    }}

                    📌 Qoidalar:
                    - bu mahsulotlar nomi natijani manashu listdagi nomga asoslanib qaytar {list(items_data.keys())}
                    - mojito bu Biron mevali mohito yoki sirop qushilgan mohito
                    - Faqat mijozning buyurtmasi kerak, xodimning takliflari emas.
                    - Mijoz o‘zgartirgan yoki bekor qilgan narsalarni JSONga kiritmang.
                    - Hajmini S, M, L qilib qaytar
                    - Suhbat aralash tillarda bo‘lishi mumkin (o‘zbek, rus, ingliz) — barcha tillardagi buyurtmalarni tushunib, faqat tasdiqlanganlarini qaytaring.

                    - Faqat JSON formatni qaytaring. Hech qanday izoh yoki matn kerak emas.

                    Mana suhbat: {data}
                """

        
        summary = summarize_order(prompt)

        cleaned = re.sub(r"```json|```", "", summary).strip()

        try:
            orders_json = json.loads(cleaned)
        except json.JSONDecodeError:
            orders_json = {"orders": {}}

        # print(orders_json)

        orders = orders_json.get("orders", None)

        orders_data = []
        if orders is not None:
            for v, k in orders.items():
                item_name = v
                quantity = k["miqdori"]
                size = k["hajmi"]
                data = {"item_id": items_data[item_name]["id"], "quantity": quantity, "size": size if size in items_data[item_name]["size"] else None}
                orders_data.append(data)

        # print(orders_json)
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
    
@app.post("/summarize_order_from_audio")
async def process_audio_file(audio: UploadFile = File(None)):
    try:
        if audio is None:
            return JSONResponse(status_code=400, content={"success": {}, "error": {"description": {"Please upload a file!"}}})
        
        contents = await audio.read()
        kind = filetype.guess(contents)
        print(kind.mime, "file type")
        print("file name", audio.filename)

        if kind is None or kind.mime not in allowed_file_types:
            return JSONResponse(status_code=400, content={"success": {}, "error": {"description": f"Invalid file type. Only following audio files are accepted {allowed_file_types}."}})
 
        prompt = f"""
                    Suhbatda mijoz va xodim o‘rtasida buyurtma jarayoni mavjud.

                    Sizdan talab qilinadi:

                    🟢 Faqat **mijozning yakuniy va tasdiqlangan buyurtmalarini** aniqlang (ya'ni suhbat oxirida mijoz nima buyurtma bergan bo‘lsa, faqat o‘sha mahsulotlar kiritilsin).
                    🔴 Suhbat davomida mijoz aytgan, lekin keyin o‘zgartirgan yoki bekor qilgan buyurtmalarni hisobga olmang.

                    📋 Natijani faqat quyidagi formatda JSON ko‘rinishida chiqaring:

                    {{
                        "orders": {{
                            "nomi": {{
                                "miqdori": <soni>,
                                "hajmi": "<S|M|L>"
                            }}
                        }}
                    }}

                    ❌ Agar suhbat buyurtma bilan bog‘liq bo‘lmasa yoki hech qanday yakuniy buyurtma bo‘lmasa, quyidagicha qaytaring:

                    {{
                        "orders": {{}}
                    }}

                    📌 Qoidalar:
                    - Mahsulot nomlari faqat quyidagi ro‘yxatdan bo‘lishi kerak: {list(items_data.keys())}

                    - mojito bu **biron mevali mohito** yoki **sirop qo‘shilgan mohito** degani — umumiy holda "mojito" deb yozing.
                    - Faqat mijoz tomonidan berilgan tasdiqlangan (yakuniy) buyurtmalarni qaytaring.
                    - Hajmlarni faqat `S`, `M`, `L` deb belgilang. Masalan, "katta", "small", "medium", "big", "kichik", "bolshoy" kabi so‘zlar mos ravishda `S`, `M`, `L` ga moslanadi.
                    - Suhbat har xil tillarda bo‘lishi mumkin (o‘zbek, rus, ingliz). Model barcha tillarni tushunishi kerak.
                    - **Faqat JSON qaytaring.** Hech qanday izoh yoki matn yozmang.

                    """

        summary = process_audio(contents, kind.mime, prompt)

        cleaned = re.sub(r"```json|```", "", summary).strip()

        try:
            orders_json = json.loads(cleaned)
        except json.JSONDecodeError:
            orders_json = {"orders": {}}

        # print(orders_json)

        orders = orders_json.get("orders", None)

        orders_data = []
        if orders is not None:
            for v, k in orders.items():
                item_name = v
                quantity = k["miqdori"]
                size = k["hajmi"]
                data = {"item_id": items_data[item_name]["id"], "quantity": quantity, "size": size if size in items_data[item_name]["size"] else None}
                orders_data.append(data)

        # print(orders_json)
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
    return crud.create_order(db=db, order=order)

@app.get("/orders/", response_model=List[schemas.Order])
async def read_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: auth_models.User = Depends(get_current_user)):
    orders = crud.get_orders(db, skip=skip, limit=limit)
    return orders

@app.get("/orders/{order_id}", response_model=schemas.Order)
async def read_order(order_id: int, db: Session = Depends(get_db), current_user: auth_models.User = Depends(get_current_user)):
    db_order = crud.get_order(db, order_id=order_id)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order

@app.put("/orders/{order_id}", response_model=schemas.Order)
async def update_order(order_id: int, order: schemas.OrderCreate, db: Session = Depends(get_db), current_user: auth_models.User = Depends(get_current_user)):
    db_order = crud.update_order(db, order_id=order_id, order=order)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order

@app.delete("/orders/{order_id}", response_model=bool)
async def delete_order(order_id: int, db: Session = Depends(get_db), current_user: auth_models.User = Depends(get_current_user)):
    result = crud.delete_order(db, order_id=order_id)
    if not result:
        raise HTTPException(status_code=404, detail="Order not found")
    return result

@app.post("/register", response_model=auth_schemas.User)
async def register_user(user: auth_schemas.UserCreate, db: Session = Depends(get_db)):
    return auth_crud.create_user(db=db, user=user)

@app.post("/login", response_model=auth_schemas.Token)
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

@app.post("/refresh", response_model=auth_schemas.Token)
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

@app.post("/logout")
async def logout(refresh_request: auth_schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    success = revoke_refresh_token(db, refresh_request.refresh_token)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid refresh token"
        )
    
    return {"message": "Successfully logged out"}

@app.get("/users/me", response_model=auth_schemas.User)
async def read_users_me(current_user: auth_models.User = Depends(get_current_user)):
    return current_user

@app.get("/")
async def main_page():
    return JSONResponse(status_code=200, content={"status": "test app is working!"})


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=6000, reload=True, forwarded_allow_ips="*")