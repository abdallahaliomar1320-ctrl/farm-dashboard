import os
import shutil
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
import tenancy
import record_ops
from database import SessionLocal, engine
from admin_api import router as admin_router
from admin_ui import router as admin_ui_router

tenancy.run_migrations()

app = FastAPI(title="إدارة عمال المزرعة")

app.include_router(admin_router)
app.include_router(admin_ui_router)

DEFAULT_FARM_ID = 1


def get_default_farm(db: Session):
    farm = db.query(models.Farm).filter(models.Farm.id == DEFAULT_FARM_ID).first()
    if farm is None:
        raise HTTPException(status_code=500, detail="المزرعة الافتراضية غير مهيأة")
    return farm

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# API Endpoints
@app.get("/api/workers/", response_model=List[schemas.Worker])
def read_workers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    workers = db.query(models.Worker).filter(
        models.Worker.farm_id == DEFAULT_FARM_ID
    ).offset(skip).limit(limit).all()
    return workers

@app.post("/api/workers/", response_model=schemas.Worker)
def create_worker(worker: schemas.WorkerCreate, db: Session = Depends(get_db)):
    farm = get_default_farm(db)
    db_worker, _created = record_ops.create_worker(db, farm, worker.model_dump())
    return db_worker

@app.put("/api/workers/{worker_id}", response_model=schemas.Worker)
def update_worker(worker_id: int, worker: schemas.WorkerCreate, db: Session = Depends(get_db)):
    db_worker = db.query(models.Worker).filter(
        models.Worker.id == worker_id, models.Worker.farm_id == DEFAULT_FARM_ID
    ).first()
    if db_worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    for key, value in worker.model_dump().items():
        setattr(db_worker, key, value)
    
    db.commit()
    db.refresh(db_worker)
    return db_worker

@app.delete("/api/workers/{worker_id}")
def delete_worker(worker_id: int, db: Session = Depends(get_db)):
    db_worker = db.query(models.Worker).filter(
        models.Worker.id == worker_id, models.Worker.farm_id == DEFAULT_FARM_ID
    ).first()
    if db_worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    db.delete(db_worker)
    db.commit()
    return {"message": "Worker deleted"}

@app.post("/api/workers/{worker_id}/advances/", response_model=schemas.Advance)
def create_advance(worker_id: int, advance: schemas.AdvanceCreate, db: Session = Depends(get_db)):
    farm = get_default_farm(db)
    db_advance, _created = record_ops.create_advance(
        db, farm, worker_id, advance.model_dump())
    return db_advance

@app.delete("/api/advances/{advance_id}")
def delete_advance(advance_id: int, db: Session = Depends(get_db)):
    db_advance = db.query(models.Advance).filter(
        models.Advance.id == advance_id, models.Advance.farm_id == DEFAULT_FARM_ID
    ).first()
    if db_advance is None:
        raise HTTPException(status_code=404, detail="Advance not found")
    
    db_worker = db.query(models.Worker).filter(models.Worker.id == db_advance.worker_id).first()
    if db_worker:
        db_worker.balance += db_advance.amount
        
    db.delete(db_advance)
    db.commit()
    db.commit()
    return {"message": "Advance deleted"}

# --- MERCHANTS API ---
@app.get("/api/merchants/", response_model=List[schemas.Merchant])
def read_merchants(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Merchant).filter(
        models.Merchant.farm_id == DEFAULT_FARM_ID
    ).offset(skip).limit(limit).all()

@app.post("/api/merchants/", response_model=schemas.Merchant)
def create_merchant(merchant: schemas.MerchantCreate, db: Session = Depends(get_db)):
    farm = get_default_farm(db)
    db_merchant, _created = record_ops.create_merchant(db, farm, merchant.model_dump())
    return db_merchant

@app.put("/api/merchants/{merchant_id}", response_model=schemas.Merchant)
def update_merchant(merchant_id: int, merchant: schemas.MerchantCreate, db: Session = Depends(get_db)):
    db_merchant = db.query(models.Merchant).filter(
        models.Merchant.id == merchant_id, models.Merchant.farm_id == DEFAULT_FARM_ID
    ).first()
    if not db_merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    for key, value in merchant.model_dump().items():
        setattr(db_merchant, key, value)
    db.commit()
    db.refresh(db_merchant)
    return db_merchant

# --- CROP SALES API ---
@app.get("/api/crop_sales/", response_model=List[schemas.CropSale])
def read_crop_sales(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.CropSale).filter(
        models.CropSale.farm_id == DEFAULT_FARM_ID
    ).order_by(models.CropSale.date.desc()).offset(skip).limit(limit).all()

@app.post("/api/crop_sales/", response_model=schemas.CropSale)
def create_crop_sale(sale: schemas.CropSaleCreate, db: Session = Depends(get_db)):
    farm = get_default_farm(db)
    db_sale, _created = record_ops.create_crop_sale(db, farm, sale.model_dump())
    return db_sale

@app.delete("/api/crop_sales/{sale_id}")
def delete_crop_sale(sale_id: int, db: Session = Depends(get_db)):
    db_sale = db.query(models.CropSale).filter(
        models.CropSale.id == sale_id, models.CropSale.farm_id == DEFAULT_FARM_ID
    ).first()
    if db_sale is None:
        raise HTTPException(status_code=404, detail="Sale not found")
        
    if db_sale.remaining_amount > 0 and db_sale.merchant_id:
        db_merchant = db.query(models.Merchant).filter(models.Merchant.id == db_sale.merchant_id).first()
        if db_merchant:
            db_merchant.balance -= db_sale.remaining_amount
            description = f"متبقي من قيمة بيع {db_sale.quantity} {db_sale.unit} {db_sale.crop_name}"
            transaction = db.query(models.MerchantTransaction).filter(
                models.MerchantTransaction.merchant_id == db_merchant.id,
                models.MerchantTransaction.amount == db_sale.remaining_amount,
                models.MerchantTransaction.transaction_type == "debt",
                models.MerchantTransaction.description == description
            ).first()
            if transaction:
                db.delete(transaction)

    db.delete(db_sale)
    db.commit()
    return {"message": "Crop sale deleted"}

# --- QAT SALES API ---
@app.get("/api/qat_sales/", response_model=List[schemas.QatSale])
def read_qat_sales(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.QatSale).filter(
        models.QatSale.farm_id == DEFAULT_FARM_ID
    ).order_by(models.QatSale.date.desc()).offset(skip).limit(limit).all()

@app.post("/api/qat_sales/", response_model=schemas.QatSale)
def create_qat_sale(sale: schemas.QatSaleCreate, db: Session = Depends(get_db)):
    farm = get_default_farm(db)
    db_sale, _created = record_ops.create_qat_sale(db, farm, sale.model_dump())
    return db_sale

@app.delete("/api/qat_sales/{sale_id}")
def delete_qat_sale(sale_id: int, db: Session = Depends(get_db)):
    db_sale = db.query(models.QatSale).filter(
        models.QatSale.id == sale_id, models.QatSale.farm_id == DEFAULT_FARM_ID
    ).first()
    if db_sale is None:
        raise HTTPException(status_code=404, detail="Sale not found")
        
    if db_sale.remaining_amount > 0 and db_sale.merchant_id:
        db_merchant = db.query(models.Merchant).filter(models.Merchant.id == db_sale.merchant_id).first()
        if db_merchant:
            db_merchant.balance -= db_sale.remaining_amount
            description = f"متبقي من قيمة بيع {db_sale.quantity} {db_sale.unit} {db_sale.qat_type}"
            transaction = db.query(models.MerchantTransaction).filter(
                models.MerchantTransaction.merchant_id == db_merchant.id,
                models.MerchantTransaction.amount == db_sale.remaining_amount,
                models.MerchantTransaction.transaction_type == "debt",
                models.MerchantTransaction.description == description
            ).first()
            if transaction:
                db.delete(transaction)

    db.delete(db_sale)
    db.commit()
    return {"message": "Qat sale deleted"}

# --- EXPENSES API ---
@app.get("/api/expenses/", response_model=List[schemas.Expense])
def read_expenses(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Expense).filter(
        models.Expense.farm_id == DEFAULT_FARM_ID
    ).order_by(models.Expense.date.desc()).offset(skip).limit(limit).all()

@app.post("/api/expenses/", response_model=schemas.Expense)
def create_expense(expense: schemas.ExpenseCreate, db: Session = Depends(get_db)):
    farm = get_default_farm(db)
    db_expense, _created = record_ops.create_expense(db, farm, expense.model_dump())
    return db_expense

# --- DASHBOARD STATS ---
@app.get("/api/stats/")
def get_dashboard_stats(db: Session = Depends(get_db)):
    # Calculate totals
    total_crop_sales = sum([s.paid_amount for s in db.query(models.CropSale).filter(
        models.CropSale.farm_id == DEFAULT_FARM_ID).all()])
    total_qat_sales = sum([s.paid_amount for s in db.query(models.QatSale).filter(
        models.QatSale.farm_id == DEFAULT_FARM_ID).all()])
    total_revenue = total_crop_sales + total_qat_sales
    
    total_salaries = sum([w.pay_amount for w in db.query(models.Worker).filter(
        models.Worker.farm_id == DEFAULT_FARM_ID).all()])
    total_advances = sum([a.amount for a in db.query(models.Advance).filter(
        models.Advance.farm_id == DEFAULT_FARM_ID).all()])
    total_operational = sum([e.amount for e in db.query(models.Expense).filter(
        models.Expense.farm_id == DEFAULT_FARM_ID).all()])
    total_expenses = total_salaries + total_advances + total_operational
    
    merchant_payments = sum([t.amount for t in db.query(models.MerchantTransaction).filter(
        models.MerchantTransaction.farm_id == DEFAULT_FARM_ID,
        models.MerchantTransaction.transaction_type == 'payment').all()])
    total_cash_in = total_revenue + merchant_payments
    total_cash_out = total_advances + total_operational
    cash_box = total_cash_in - total_cash_out
    
    net_profit = total_revenue - total_expenses
    zakat = total_qat_sales * 0.05 # 5% of Qat sales
    
    return {
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "cash_box": cash_box,
        "qat_zakat": zakat
    }

@app.get("/api/reports/")
def get_reports_data(db: Session = Depends(get_db), category: str = "all", start_date: str = None, end_date: str = None):
    # Base queries
    q_crop = db.query(models.CropSale).filter(models.CropSale.farm_id == DEFAULT_FARM_ID)
    q_qat = db.query(models.QatSale).filter(models.QatSale.farm_id == DEFAULT_FARM_ID)
    q_exp = db.query(models.Expense).filter(models.Expense.farm_id == DEFAULT_FARM_ID)
    q_sal = db.query(models.Worker).filter(models.Worker.farm_id == DEFAULT_FARM_ID)
    
    # Apply date filters
    if start_date:
        s_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        q_crop = q_crop.filter(models.CropSale.date >= start_date)
        q_qat = q_qat.filter(models.QatSale.date >= start_date)
        q_exp = q_exp.filter(models.Expense.date >= s_date)
    
    if end_date:
        e_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        q_crop = q_crop.filter(models.CropSale.date <= end_date)
        q_qat = q_qat.filter(models.QatSale.date <= end_date)
        q_exp = q_exp.filter(models.Expense.date <= e_date)
        
    # Apply category filters for revenue
    total_crop_sales = sum([s.paid_amount for s in q_crop.all()]) if category in ["all", "crops"] else 0
    total_qat_sales = sum([s.paid_amount for s in q_qat.all()]) if category in ["all", "qat"] else 0
    
    total_revenue = total_crop_sales + total_qat_sales
    
    
    # Salary & Advances (also general, filter them by date? Workers don't have date. Advances do.)
    q_adv = db.query(models.Advance)
    if start_date:
        q_adv = q_adv.filter(models.Advance.date >= s_date)
    if end_date:
        q_adv = q_adv.filter(models.Advance.date <= e_date)
        
    total_advances = sum([a.amount for a in q_adv.all()])
    total_operational = sum([e.amount for e in q_exp.all()])
    
    # If date is filtered, maybe salaries shouldn't be counted full? 
    # For simplicity, we just take total_operational + total_advances as expenses for the period.
    total_expenses = total_operational + total_advances
    if not start_date and not end_date:
        total_salaries = sum([w.pay_amount for w in q_sal.all()])
        total_expenses += total_salaries
        
    net_profit = total_revenue - total_expenses
    zakat = (total_qat_sales * 0.05) if category in ["all", "qat"] else 0
    
    # Debts
    q_merchants = db.query(models.Merchant).filter(models.Merchant.farm_id == DEFAULT_FARM_ID)
    if category == "qat":
        q_merchants = q_merchants.filter(models.Merchant.merchant_type == 'مقوت')
    elif category == "crops":
        q_merchants = q_merchants.filter(models.Merchant.merchant_type == 'تاجر محاصيل')
        
    total_debts = sum([m.balance for m in q_merchants.all()])
    
    # Calculate quantities
    crop_qty = sum([s.quantity for s in q_crop.all()]) if category in ["all", "crops"] else 0
    qat_qty = sum([s.quantity for s in q_qat.all()]) if category in ["all", "qat"] else 0

    # Calculate Cash Box
    q_payments = db.query(models.MerchantTransaction).filter(
        models.MerchantTransaction.farm_id == DEFAULT_FARM_ID,
        models.MerchantTransaction.transaction_type == 'payment')
    if start_date:
        q_payments = q_payments.filter(models.MerchantTransaction.date >= start_date)
    if end_date:
        q_payments = q_payments.filter(models.MerchantTransaction.date <= end_date)
    total_payments = sum([t.amount for t in q_payments.all()])
    
    cash_box = total_revenue + total_payments - (total_operational + total_advances)
    
    return {
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "total_debts": total_debts,
        "cash_box": cash_box,
        "qat_zakat": zakat,
        "crop_qty": crop_qty,
        "qat_qty": qat_qty
    }

@app.get("/api/backup/")
def get_backup():
    if os.path.exists("farm.db"):
        return FileResponse("farm.db", media_type="application/octet-stream", filename="farm.db")
    raise HTTPException(status_code=404, detail="Database file not found")

@app.post("/api/restore/")
def restore_backup(file: UploadFile = File(...)):
    with open("farm.db", "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"message": "Database restored successfully"}

from datetime import datetime

@app.post("/api/close_season/")
def close_season(db: Session = Depends(get_db)):
    # Backup current DB
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"farm_archive_{timestamp}.db"
    if os.path.exists("farm.db"):
        shutil.copy("farm.db", backup_name)

    # Clear data of the default farm only (تعليق/أرشفة المزرعة الافتراضية لا يمس بيانات المزارع الأخرى)
    db.query(models.Advance).filter(models.Advance.farm_id == DEFAULT_FARM_ID).delete()
    db.query(models.CropSale).filter(models.CropSale.farm_id == DEFAULT_FARM_ID).delete()
    db.query(models.QatSale).filter(models.QatSale.farm_id == DEFAULT_FARM_ID).delete()
    db.query(models.Expense).filter(models.Expense.farm_id == DEFAULT_FARM_ID).delete()

    # Reset balances
    workers = db.query(models.Worker).filter(models.Worker.farm_id == DEFAULT_FARM_ID).all()
    for w in workers:
        w.balance = w.pay_amount # Reset balance to original pay_amount (no advances)

    merchants = db.query(models.Merchant).filter(models.Merchant.farm_id == DEFAULT_FARM_ID).all()
    for m in merchants:
        m.balance = 0.0

    db.commit()
    return {"message": "Season closed and archived successfully"}


# Mount Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_index():
    return FileResponse("static/index.html")

@app.get("/api/merchants/{merchant_id}/transactions/", response_model=List[schemas.MerchantTransaction])
def get_merchant_transactions(merchant_id: int, db: Session = Depends(get_db)):
    transactions = db.query(models.MerchantTransaction).filter(
        models.MerchantTransaction.merchant_id == merchant_id,
        models.MerchantTransaction.farm_id == DEFAULT_FARM_ID
    ).order_by(models.MerchantTransaction.id.desc()).all()
    return transactions

@app.post("/api/merchants/{merchant_id}/payments/", response_model=schemas.MerchantTransaction)
def add_merchant_payment(merchant_id: int, transaction: schemas.MerchantTransactionCreate, db: Session = Depends(get_db)):
    farm = get_default_farm(db)
    db_transaction, _created = record_ops.create_merchant_payment(
        db, farm, merchant_id, transaction.model_dump())
    return db_transaction

@app.delete("/api/merchants/{merchant_id}/payments/{transaction_id}")
def delete_merchant_payment(merchant_id: int, transaction_id: int, db: Session = Depends(get_db)):
    db_transaction = db.query(models.MerchantTransaction).filter(
        models.MerchantTransaction.id == transaction_id,
        models.MerchantTransaction.merchant_id == merchant_id,
        models.MerchantTransaction.farm_id == DEFAULT_FARM_ID
    ).first()
    
    if db_transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    if db_transaction.transaction_type == "payment":
        db_merchant = db.query(models.Merchant).filter(models.Merchant.id == merchant_id).first()
        if db_merchant:
            db_merchant.balance += db_transaction.amount
            
    db.delete(db_transaction)
    db.commit()
    return {"message": "Payment deleted"}
