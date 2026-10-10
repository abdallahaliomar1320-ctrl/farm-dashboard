from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base

class Farm(Base):
    __tablename__ = "farms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    contact_name = Column(String)
    contact_phone = Column(String)
    api_key = Column(String, unique=True, nullable=False, index=True)
    status = Column(String, default="active")  # active / suspended
    suspension_reason = Column(String)
    notes = Column(String)
    created_at = Column(String)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    status = Column(String, default="active")  # active / expired / cancelled
    start_date = Column(String)  # ISO date
    end_date = Column(String)    # ISO date
    price = Column(Float)
    currency = Column(String)
    payment_status = Column(String, default="pending")  # paid / pending (administrative tracking only)
    notes = Column(String)
    created_by = Column(String)
    created_at = Column(String)


class Operation(Base):
    __tablename__ = "operations"
    __table_args__ = (UniqueConstraint("farm_id", "client_uuid", name="uq_farm_client_uuid"),)

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    client_uuid = Column(String, nullable=False)
    op_type = Column(String, nullable=False)  # worker/advance/crop_sale/qat_sale/expense/merchant/merchant_payment
    record_table = Column(String)
    record_id = Column(Integer)
    month_key = Column(String, nullable=False, index=True)  # "YYYY-MM" بتوقيت النظام
    created_at = Column(String)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    entity = Column(String)
    entity_id = Column(String)
    reason = Column(String)
    details = Column(String)  # JSON
    created_at = Column(String)


class AppSettings(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True)  # دائماً 1
    free_ops_limit = Column(Integer, default=250)
    alert_threshold_1 = Column(Integer, default=200)
    alert_threshold_2 = Column(Integer, default=240)
    subscription_price = Column(Float)  # None حتى يضبطه المالك — لا يُخترع سعر
    subscription_currency = Column(String, default="YER")
    subscription_duration_days = Column(Integer, default=30)
    grace_period_days = Column(Integer, default=7)
    timezone = Column(String, default="Asia/Aden")
    updated_at = Column(String)
    updated_by = Column(String)


class Worker(Base):
    __tablename__ = "workers"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=True, index=True)
    name = Column(String, index=True)
    phone = Column(String)
    start_date = Column(Date)
    end_date = Column(Date, nullable=True)
    job = Column(String)
    pay_type = Column(String)
    pay_amount = Column(Float)
    balance = Column(Float, default=0.0)

    advances = relationship("Advance", back_populates="worker", cascade="all, delete-orphan")


class Advance(Base):
    __tablename__ = "advances"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=True, index=True)
    amount = Column(Float)
    notes = Column(String)
    date = Column(Date)
    worker_id = Column(Integer, ForeignKey("workers.id"))

    worker = relationship("Worker", back_populates="advances")


class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=True, index=True)
    name = Column(String, index=True)
    phone = Column(String, nullable=True)
    merchant_type = Column(String, default="مقوت")
    balance = Column(Float, default=0.0)

    qat_sales = relationship("QatSale", back_populates="merchant")
    crop_sales = relationship("CropSale", back_populates="merchant")
    transactions = relationship("MerchantTransaction", back_populates="merchant")

class MerchantTransaction(Base):
    __tablename__ = "merchant_transactions"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"))
    amount = Column(Float, default=0.0)
    transaction_type = Column(String) # 'debt' or 'payment'
    description = Column(String)
    date = Column(String)

    merchant = relationship("Merchant", back_populates="transactions")


class CropSale(Base):
    __tablename__ = "crop_sales"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=True, index=True)
    crop_name = Column(String, index=True)
    unit = Column(String)
    quantity = Column(Float)
    price_per_unit = Column(Float)
    total_price = Column(Float)
    payment_type = Column(String, nullable=True) # legacy
    paid_amount = Column(Float, default=0.0)
    remaining_amount = Column(Float, default=0.0)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=True)
    date = Column(Date)

    merchant = relationship("Merchant", back_populates="crop_sales")


class QatSale(Base):
    __tablename__ = "qat_sales"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=True, index=True)
    qat_type = Column(String, index=True) # بلوط، فراق، قمطه، قطل
    unit = Column(String) # كيلو / باغه
    quantity = Column(Float)
    total_price = Column(Float)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=True)
    payment_type = Column(String, nullable=True) # legacy
    paid_amount = Column(Float, default=0.0)
    remaining_amount = Column(Float, default=0.0)
    date = Column(Date)
    notes = Column(String, nullable=True)

    merchant = relationship("Merchant", back_populates="qat_sales")

class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=True, index=True)
    category = Column(String, index=True) # ديزل، أسمدة، صيانة معدات، أخرى
    amount = Column(Float)
    date = Column(Date)
    notes = Column(String, nullable=True)
