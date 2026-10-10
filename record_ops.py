# -*- coding: utf-8 -*-
"""
منطق إنشاء السجلات المشترك بين الواجهات القديمة وواجهات المزارع والمزامنة.

كل عملية إنشاء سجل جديد تحجز معرفها الفريد أولاً عبر claim_operation() في
tenancy.py (فحص الحد والتعليق مع الحجز في معاملة واحدة)، ثم ينشأ السجل
ويرتبط به. بهذا لا تُحتسب أي عملية مرتين ولا تُنشأ سجلات مكررة حتى مع
تزامن الطلبات، وإعادة المحاولة بعد فشل الاتصال تعيد السجل نفسه.
"""
import uuid
from datetime import datetime, date as date_type

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
import schemas
import tenancy
from tenancy import BlockedError  # يعاد تصديره لتظل الواجهات تستخدم record_ops.BlockedError


def _find_by_op(db: Session, farm_id: int, client_uuid: str):
    """يجلب السجل الموجود مسبقاً لعملية مكررة (نفس المعرف الفريد) إن أمكن.

    عند سباق طلبات متزامنة قد يُقرأ الحجز قبل أن يربط الطلب الفائز السجل به،
    لذا نعيد المحاولة قليلاً قبل الاعتراف بأن السجل غير متاح بعد.
    """
    import time
    op = None
    for attempt in range(4):
        op = db.query(models.Operation).filter(
            models.Operation.farm_id == farm_id,
            models.Operation.client_uuid == client_uuid,
        ).first()
        if op is None or op.record_id:
            break
        if attempt < 3:
            time.sleep(0.15)
            db.rollback()  # تحديث نظرة الجلسة عن آخر حالة مثبتة
    if not op or not op.record_id:
        return None
    table = {
        "workers": models.Worker, "advances": models.Advance,
        "merchants": models.Merchant, "merchant_transactions": models.MerchantTransaction,
        "crop_sales": models.CropSale, "qat_sales": models.QatSale, "expenses": models.Expense,
    }.get(op.record_table)
    if table is None:
        return None
    return db.query(table).filter(table.id == op.record_id, table.farm_id == farm_id).first()


def _tx_date(d):
    return d.isoformat() if isinstance(d, (datetime, date_type)) else (d or "")


def create_worker(db: Session, farm: models.Farm, data: dict,
                  client_uuid: str = None, enforce_limit: bool = True):
    client_uuid = client_uuid or str(uuid.uuid4())
    if not tenancy.claim_operation(db, farm.id, client_uuid, "worker", "workers",
                                   enforce_limit=enforce_limit, farm=farm):
        return _find_by_op(db, farm.id, client_uuid), False

    worker_data = dict(data)
    if worker_data.get("balance", 0) == 0:
        worker_data["balance"] = worker_data.get("pay_amount", 0)
    db_worker = models.Worker(farm_id=farm.id, **worker_data)
    db.add(db_worker)
    db.commit()
    db.refresh(db_worker)
    tenancy.attach_record_id(db, farm.id, client_uuid, db_worker.id)
    return db_worker, True


def create_advance(db: Session, farm: models.Farm, worker_id: int, data: dict,
                   client_uuid: str = None, enforce_limit: bool = True):
    client_uuid = client_uuid or str(uuid.uuid4())
    # عزل بيانات المزارع: السلفة تُسجل فقط على عامل يخص نفس المزرعة
    db_worker = db.query(models.Worker).filter(
        models.Worker.id == worker_id, models.Worker.farm_id == farm.id
    ).first()
    if not db_worker:
        raise HTTPException(status_code=404, detail="العامل غير موجود في هذه المزرعة")
    if not tenancy.claim_operation(db, farm.id, client_uuid, "advance", "advances",
                                   enforce_limit=enforce_limit, farm=farm):
        return _find_by_op(db, farm.id, client_uuid), False

    db_advance = models.Advance(farm_id=farm.id, worker_id=worker_id, **data)
    db.add(db_advance)
    db_worker.balance -= data.get("amount", 0)
    db.commit()
    db.refresh(db_advance)
    tenancy.attach_record_id(db, farm.id, client_uuid, db_advance.id)
    return db_advance, True


def create_merchant(db: Session, farm: models.Farm, data: dict,
                    client_uuid: str = None, enforce_limit: bool = True):
    client_uuid = client_uuid or str(uuid.uuid4())
    if not tenancy.claim_operation(db, farm.id, client_uuid, "merchant", "merchants",
                                   enforce_limit=enforce_limit, farm=farm):
        return _find_by_op(db, farm.id, client_uuid), False

    db_merchant = models.Merchant(farm_id=farm.id, **data)
    db.add(db_merchant)
    db.commit()
    db.refresh(db_merchant)
    tenancy.attach_record_id(db, farm.id, client_uuid, db_merchant.id)
    return db_merchant, True


def create_merchant_payment(db: Session, farm: models.Farm, merchant_id: int, data: dict,
                            client_uuid: str = None, enforce_limit: bool = True):
    client_uuid = client_uuid or str(uuid.uuid4())
    # عزل بيانات المزارع: الدفعة تُسجل فقط لتاجر يخص نفس المزرعة
    db_merchant = db.query(models.Merchant).filter(
        models.Merchant.id == merchant_id, models.Merchant.farm_id == farm.id
    ).first()
    if not db_merchant:
        raise HTTPException(status_code=404, detail="التاجر غير موجود في هذه المزرعة")
    if not tenancy.claim_operation(db, farm.id, client_uuid, "merchant_payment",
                                   "merchant_transactions",
                                   enforce_limit=enforce_limit, farm=farm):
        return _find_by_op(db, farm.id, client_uuid), False

    db_merchant.balance -= data.get("amount", 0)
    db_transaction = models.MerchantTransaction(
        farm_id=farm.id,
        merchant_id=merchant_id,
        amount=data.get("amount", 0),
        transaction_type="payment",
        description=data.get("description", ""),
        date=data.get("date", datetime.now().strftime("%Y-%m-%d")),
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    tenancy.attach_record_id(db, farm.id, client_uuid, db_transaction.id)
    return db_transaction, True


def _own_merchant(db: Session, farm: models.Farm, merchant_id):
    """يجلب التاجر إن كان من نفس المزرعة، وإلا يرفض (منع الوصول بتغيير المعرفات)."""
    if merchant_id is None:
        return None
    m = db.query(models.Merchant).filter(
        models.Merchant.id == merchant_id, models.Merchant.farm_id == farm.id
    ).first()
    if not m:
        raise HTTPException(status_code=404, detail="التاجر غير موجود في هذه المزرعة")
    return m


def create_crop_sale(db: Session, farm: models.Farm, data: dict,
                     client_uuid: str = None, enforce_limit: bool = True):
    client_uuid = client_uuid or str(uuid.uuid4())
    db_merchant = _own_merchant(db, farm, data.get("merchant_id"))
    if not tenancy.claim_operation(db, farm.id, client_uuid, "crop_sale", "crop_sales",
                                   enforce_limit=enforce_limit, farm=farm):
        return _find_by_op(db, farm.id, client_uuid), False

    db_sale = models.CropSale(farm_id=farm.id, **data)
    if db_sale.remaining_amount and db_sale.remaining_amount > 0 and db_merchant:
        db_merchant.balance += db_sale.remaining_amount
        description = (
            f"شراء {db_sale.quantity} {db_sale.unit} {db_sale.crop_name} بسعر "
            f"{db_sale.price_per_unit}. (الإجمالي: {db_sale.total_price}، المدفوع: {db_sale.paid_amount})"
        )
        db.add(models.MerchantTransaction(
            farm_id=farm.id,
            merchant_id=db_merchant.id,
            amount=db_sale.remaining_amount,
            transaction_type="debt",
            description=description,
            date=_tx_date(db_sale.date),
        ))
    db.add(db_sale)
    db.commit()
    db.refresh(db_sale)
    tenancy.attach_record_id(db, farm.id, client_uuid, db_sale.id)
    return db_sale, True


def create_qat_sale(db: Session, farm: models.Farm, data: dict,
                    client_uuid: str = None, enforce_limit: bool = True):
    client_uuid = client_uuid or str(uuid.uuid4())
    db_merchant = _own_merchant(db, farm, data.get("merchant_id"))
    if not tenancy.claim_operation(db, farm.id, client_uuid, "qat_sale", "qat_sales",
                                   enforce_limit=enforce_limit, farm=farm):
        return _find_by_op(db, farm.id, client_uuid), False

    db_sale = models.QatSale(farm_id=farm.id, **data)
    if db_sale.remaining_amount and db_sale.remaining_amount > 0 and db_merchant:
        db_merchant.balance += db_sale.remaining_amount
        description = (
            f"شراء {db_sale.quantity} {db_sale.unit} {db_sale.qat_type} بسعر "
            f"(الإجمالي: {db_sale.total_price}، المدفوع: {db_sale.paid_amount})"
        )
        db.add(models.MerchantTransaction(
            farm_id=farm.id,
            merchant_id=db_merchant.id,
            amount=db_sale.remaining_amount,
            transaction_type="debt",
            description=description,
            date=_tx_date(db_sale.date),
        ))
    db.add(db_sale)
    db.commit()
    db.refresh(db_sale)
    tenancy.attach_record_id(db, farm.id, client_uuid, db_sale.id)
    return db_sale, True


def create_expense(db: Session, farm: models.Farm, data: dict,
                   client_uuid: str = None, enforce_limit: bool = True):
    client_uuid = client_uuid or str(uuid.uuid4())
    if not tenancy.claim_operation(db, farm.id, client_uuid, "expense", "expenses",
                                   enforce_limit=enforce_limit, farm=farm):
        return _find_by_op(db, farm.id, client_uuid), False

    db_expense = models.Expense(farm_id=farm.id, **data)
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    tenancy.attach_record_id(db, farm.id, client_uuid, db_expense.id)
    return db_expense, True
