from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserType(str, Enum):
    HOLDER = "holder"
    VERIFIER = "verifier"
    ISSUER = "issuer"
    ADMIN = "admin"


class VerificationResult(str, Enum):
    AUTHENTIC = "authentic"
    SUSPICIOUS = "suspicious"
    FRAUDULENT = "fraudulent"


def enum_values(enum_class: type[Enum]) -> list[str]:
    return [member.value for member in enum_class]


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    id_number: Mapped[str | None] = mapped_column(String(100))
    user_type: Mapped[UserType] = mapped_column(
        SqlEnum(
            UserType,
            name="user_type",
            values_callable=enum_values,
        ),
        nullable=False,
        default=UserType.HOLDER,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    certificates: Mapped[list["Certificate"]] = relationship(back_populates="user")
    verifications: Mapped[list["Verification"]] = relationship(
        back_populates="user",
        foreign_keys="Verification.user_id",
    )


class Certificate(Base):
    __tablename__ = "certificates"

    certificate_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    certificate_type: Mapped[str] = mapped_column(String(200), nullable=False)
    issuing_institution: Mapped[str] = mapped_column(String(300), nullable=False)
    certificate_number: Mapped[str] = mapped_column(String(200), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="certificates")
    verifications: Mapped[list["Verification"]] = relationship(
        back_populates="certificate"
    )
    qr_codes: Mapped[list["QRCode"]] = relationship(back_populates="certificate")


class Institution(Base):
    __tablename__ = "institutions"

    institution_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(320), nullable=False)
    standards: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    templates: Mapped[list["Template"]] = relationship(back_populates="institution")


class Verification(Base):
    __tablename__ = "verifications"

    verification_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    certificate_id: Mapped[int] = mapped_column(
        ForeignKey("certificates.certificate_id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    verifier_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    verification_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    result: Mapped[VerificationResult] = mapped_column(
        SqlEnum(
            VerificationResult,
            name="verification_result",
            values_callable=enum_values,
        ),
        nullable=False,
    )
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    blockchain_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    certificate: Mapped[Certificate] = relationship(back_populates="verifications")
    user: Mapped[User] = relationship(
        back_populates="verifications",
        foreign_keys=[user_id],
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    action: Mapped[str] = mapped_column(String(200), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    ip_address: Mapped[str | None] = mapped_column(String(45))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class QRCode(Base):
    __tablename__ = "qr_codes"

    qr_code_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    certificate_id: Mapped[int] = mapped_column(
        ForeignKey("certificates.certificate_id"), nullable=False
    )
    qr_code_data: Mapped[str] = mapped_column(Text, nullable=False)
    generated_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    certificate: Mapped[Certificate] = relationship(back_populates="qr_codes")


class Template(Base):
    __tablename__ = "templates"

    template_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.institution_id"), nullable=False
    )
    certificate_type: Mapped[str] = mapped_column(String(200), nullable=False)
    security_features: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON)
    template_image: Mapped[str | None] = mapped_column(String(1000))
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    institution: Mapped[Institution] = relationship(back_populates="templates")


class Report(Base):
    __tablename__ = "reports"

    report_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    generated_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
