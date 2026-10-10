from pydantic import BaseModel
from typing import List, Optional
from datetime import date

class AdvanceBase(BaseModel):
    amount: float
    notes: Optional[str] = None
    date: date

class AdvanceCreate(AdvanceBase):
    pass

class Advance(AdvanceBase):
    id: int
    worker_id: int

    class Config:
        from_attributes = True

class WorkerBase(BaseModel):
    name: str
    phone: str
    start_date: date
    end_date: Optional[date] = None
    job: str
    pay_type: str
    pay_amount: float
    balance: float = 0.0

class WorkerCreate(WorkerBase):
    pass

class Worker(WorkerBase):
    id: int
    advances: List[Advance] = []

    class Config:
        from_attributes = True

class MerchantBase(BaseModel):
    name: str
    phone: Optional[str] = None
    merchant_type: str = "مقوت"
    balance: float = 0.0

class MerchantCreate(MerchantBase):
    pass

class Merchant(MerchantBase):
    id: int
    balance: float

    class Config:
        from_attributes = True

class MerchantTransactionBase(BaseModel):
    amount: float
    transaction_type: str
    description: str
    date: str

class MerchantTransactionCreate(MerchantTransactionBase):
    merchant_id: int

class MerchantTransaction(MerchantTransactionBase):
    id: int
    merchant_id: int

    class Config:
        from_attributes = True

class CropSaleBase(BaseModel):
    crop_name: str
    unit: str
    quantity: float
    price_per_unit: float
    total_price: float
    payment_type: Optional[str] = None
    paid_amount: float
    remaining_amount: float
    merchant_id: Optional[int] = None
    date: date

class CropSaleCreate(CropSaleBase):
    pass

class CropSale(CropSaleBase):
    id: int
    merchant: Optional[Merchant] = None

    class Config:
        from_attributes = True

class QatSaleBase(BaseModel):
    qat_type: str
    unit: str
    quantity: float
    total_price: float
    merchant_id: Optional[int] = None
    payment_type: Optional[str] = None
    paid_amount: float
    remaining_amount: float
    date: date
    notes: Optional[str] = None

class QatSaleCreate(QatSaleBase):
    pass

class QatSale(QatSaleBase):
    id: int
    merchant: Optional[Merchant] = None

    class Config:
        from_attributes = True

class ExpenseBase(BaseModel):
    category: str
    amount: float
    date: date
    notes: Optional[str] = None

class ExpenseCreate(ExpenseBase):
    pass

class Expense(ExpenseBase):
    id: int

    class Config:
        from_attributes = True

