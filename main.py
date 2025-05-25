import io
from fastapi import FastAPI, File, UploadFile, Depends, HTTPException
import os
from fastapi.responses import JSONResponse
import filetype
from google import genai
from google.genai import types
from dotenv import load_dotenv
from pydantic import BaseModel
import uvicorn
import re
import json
from typing import List, Optional
from sqlalchemy.orm import Session

import crud, models, schemas
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

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
    "milkshake": {
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


app = FastAPI(title="Order Automation API")

allowed_file_types = ["audio/wav", "audio/mp3", "audio/aiff", "audio/aac", "audio/ogg", "audio/flac", "audio/x-wav", "audio/mpeg"]

@app.post("/stt")
async def transcribe_audio(audio: UploadFile = File(None)):
    try:
        if audio is None:
            return JSONResponse(status_code=400, content={"success": {}, "error": {"description": {"Please upload a file!"}}})
        
        contents = await audio.read()
        kind = filetype.guess(contents)

        if kind is None or kind.mime not in allowed_file_types:
            return JSONResponse(status_code=400, content={"success": {}, "error": {"description": f"Invalid file type. Only following audio files are accepted {allowed_file_types}."}})
        
        prompt = "Extract text from audio, conversation might happen only in three language uzbek, english, and russian. Print text in uzbek"
        extracted_text = process_audio(contents, kind.mime, prompt)
        
        return JSONResponse(status_code=200, content={"success": {"result": extracted_text}, "error": {}})
    
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": {}, "error": {"description": e}})
        

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

    
@app.post("/orders/", response_model=schemas.Order)
async def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    return crud.create_order(db=db, order=order)

@app.get("/orders/", response_model=List[schemas.Order])
async def read_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    orders = crud.get_orders(db, skip=skip, limit=limit)
    return orders

@app.get("/orders/{order_id}", response_model=schemas.Order)
async def read_order(order_id: int, db: Session = Depends(get_db)):
    db_order = crud.get_order(db, order_id=order_id)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order

@app.put("/orders/{order_id}", response_model=schemas.Order)
async def update_order(order_id: int, order: schemas.OrderCreate, db: Session = Depends(get_db)):
    db_order = crud.update_order(db, order_id=order_id, order=order)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order

@app.delete("/orders/{order_id}", response_model=bool)
async def delete_order(order_id: int, db: Session = Depends(get_db)):
    result = crud.delete_order(db, order_id=order_id)
    if not result:
        raise HTTPException(status_code=404, detail="Order not found")
    return result

@app.get("/")
async def main_page():
    return JSONResponse(status_code=200, content={"status": "test app is working!"})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=6000)
