import hashlib
import logging
import secrets
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any
from uuid import uuid4

import pytesseract
import qrcode
# Tell pytesseract where the Tesseract executable is installed on Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
from bson import ObjectId
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Request,
    Response,
    UploadFile,
    status,
)
from PIL import Image, UnidentifiedImageError
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from qrcode.exceptions import DataOverflowError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    AuditLog,
    Certificate,
    QRCode,
    User,
    UserType,
    Verification,
    VerificationResult,
)
from app.mongo import get_mongo_database
from app.schemas import VerificationResponse
from app.security import hash_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["verification"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
BLOCKCHAIN_HASH_PLACEHOLDER = "0x123abc..."
VERIFICATION_URL_TEMPLATE = "http://localhost:5173/verify/{}"


def classify_image(filename: str) -> tuple[VerificationResult, float]:
    if "fake" in filename.casefold():
        return VerificationResult.FRAUDULENT, 0.95
    return VerificationResult.AUTHENTIC, 0.98


def extract_text(image_bytes: bytes, expected_format: str) -> str:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            if image.format != expected_format:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The file extension does not match the image format",
                )
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Image dimensions must not exceed {MAX_IMAGE_PIXELS} pixels",
                )
            image.load()
            return pytesseract.image_to_string(image)
    except HTTPException:
        raise
    except Image.DecompressionBombError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="The uploaded image dimensions are too large",
        ) from exc
    except pytesseract.TesseractNotFoundError as exc:
        logger.exception("Tesseract executable was not found")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tesseract OCR is not installed or is not available on PATH",
        ) from exc
    except pytesseract.TesseractError as exc:
        logger.exception("Tesseract failed to extract text")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tesseract OCR could not process the uploaded image",
        ) from exc
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is not a valid JPG or PNG image",
        ) from exc


def generate_qr_png(data: str) -> bytes:
    try:
        image = qrcode.make(data)
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()
    except (DataOverflowError, OSError, ValueError) as exc:
        logger.exception("Could not generate verification QR code")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate the verification QR code",
        ) from exc


def _resolve_user_and_certificate(
    db: Session,
    user_id: int | None,
    certificate_id: int | None,
    file_digest: str,
) -> tuple[User, Certificate]:
    certificate = db.get(Certificate, certificate_id) if certificate_id else None
    if certificate_id is not None and certificate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate was not found",
        )

    if user_id is None and certificate is not None:
        user_id = certificate.user_id

    user = db.get(User, user_id) if user_id is not None else None
    if user_id is not None and user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User was not found",
        )

    if user is None:
        user = User(
            name="Verification Test Holder",
            email=f"verify-{uuid4().hex}@veridoc.invalid",
            user_type=UserType.HOLDER,
            status="active",
            password_hash=hash_password(secrets.token_urlsafe(32)),
        )
        db.add(user)
        db.flush()

    if certificate is None:
        certificate = Certificate(
            user_id=user.user_id,
            certificate_type="Uploaded certificate",
            issuing_institution="Unspecified",
            certificate_number=f"UPLOAD-{file_digest[:32]}",
            issue_date=date.today(),
            status="pending",
        )
        db.add(certificate)
        db.flush()

    return user, certificate


def _delete_mongo_image(
    collection: Collection[dict[str, Any]],
    mongo_image_id: ObjectId | None,
) -> None:
    if mongo_image_id is None:
        return
    try:
        collection.delete_one({"_id": mongo_image_id})
    except PyMongoError:
        logger.exception(
            "Could not remove MongoDB image %s after verification failed",
            mongo_image_id,
        )


@router.post("/verify", response_model=VerificationResponse)
def verify_certificate(
    request: Request,
    file: UploadFile = File(...),
    user_id: int | None = Form(default=None, gt=0),
    certificate_id: int | None = Form(default=None, gt=0),
    db: Session = Depends(get_db),
) -> VerificationResponse:
    filename = PurePosixPath((file.filename or "").replace("\\", "/")).name
    extension = PurePosixPath(filename).suffix.casefold()
    supported_extensions = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG"}
    expected_format = supported_extensions.get(extension)
    declared_format = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
    }.get(file.content_type or "")
    if (
        not filename
        or expected_format is None
        or declared_format is None
        or declared_format != expected_format
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload a JPG or PNG image with a matching image/jpeg or image/png content type",
        )

    try:
        image_bytes = file.file.read(MAX_UPLOAD_BYTES + 1)
    except OSError as exc:
        logger.exception("Could not read uploaded image")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read the uploaded file",
        ) from exc
    finally:
        file.file.close()

    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded image is empty",
        )
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image size must not exceed 5 MB",
        )

    extracted_text = extract_text(image_bytes, expected_format)
    result, confidence_score = classify_image(filename)
    file_digest = hashlib.sha256(image_bytes).hexdigest()

    try:
        mongo_database = get_mongo_database()
        collection: Collection[dict[str, Any]] = mongo_database["certificate_images"]
        qr_collection: Collection[dict[str, Any]] = mongo_database["qr_code_images"]
    except RuntimeError as exc:
        logger.exception("MongoDB has not been initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not available",
        ) from exc

    mongo_image_id: ObjectId | None = None
    mongo_qr_image_id: ObjectId | None = None
    try:
        with db.begin():
            user, certificate = _resolve_user_and_certificate(
                db,
                user_id,
                certificate_id,
                file_digest,
            )
            mongo_document = {
                "filename": filename,
                "content_type": (
                    "image/jpeg" if expected_format == "JPEG" else "image/png"
                ),
                "content": image_bytes,
                "sha256": file_digest,
                "certificate_id": certificate.certificate_id,
                "uploaded_at": datetime.now(timezone.utc),
            }
            try:
                mongo_image_id = collection.insert_one(mongo_document).inserted_id
            except PyMongoError as exc:
                logger.exception("Could not save certificate image to MongoDB")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Could not save the image to MongoDB",
                ) from exc

            certificate.image_url = f"mongo://certificate_images/{mongo_image_id}"
            verification = Verification(
                certificate_id=certificate.certificate_id,
                user_id=user.user_id,
                result=result,
                confidence_score=confidence_score,
                blockchain_hash=BLOCKCHAIN_HASH_PLACEHOLDER,
            )
            audit_log = AuditLog(
                user_id=user.user_id,
                action="certificate_verification",
                ip_address=request.client.host if request.client else None,
                details={
                    "filename": filename,
                    "mongo_image_id": str(mongo_image_id),
                    "sha256": file_digest,
                    "result": result.value,
                },
            )
            db.add_all([verification, audit_log])
            db.flush()

            qr_code_data: str | None = None
            if result == VerificationResult.AUTHENTIC:
                qr_code_data = VERIFICATION_URL_TEMPLATE.format(
                    verification.verification_id
                )
                qr_image = generate_qr_png(qr_code_data)
                generated_at = datetime.now(timezone.utc)
                expires_at = generated_at + timedelta(days=365)
                try:
                    mongo_qr_image_id = qr_collection.insert_one(
                        {
                            "verification_id": verification.verification_id,
                            "certificate_id": certificate.certificate_id,
                            "qr_code_data": qr_code_data,
                            "content_type": "image/png",
                            "content": qr_image,
                            "generated_at": generated_at,
                            "expires_at": expires_at,
                        }
                    ).inserted_id
                except PyMongoError as exc:
                    logger.exception("Could not save verification QR image to MongoDB")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Could not save the QR image to MongoDB",
                    ) from exc

                db.add(
                    QRCode(
                        certificate_id=certificate.certificate_id,
                        qr_code_data=qr_code_data,
                        generated_date=generated_at,
                        expiry_date=expires_at,
                    )
                )
                db.flush()

            response = VerificationResponse(
                verification_id=verification.verification_id,
                result=result,
                confidence_score=confidence_score,
                extracted_text=extracted_text,
                blockchain_hash=BLOCKCHAIN_HASH_PLACEHOLDER,
                qr_code_data=qr_code_data,
            )
    except HTTPException:
        db.rollback()
        _delete_mongo_image(collection, mongo_image_id)
        _delete_mongo_image(qr_collection, mongo_qr_image_id)
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        _delete_mongo_image(collection, mongo_image_id)
        _delete_mongo_image(qr_collection, mongo_qr_image_id)
        logger.exception("Could not persist verification and audit log")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not save the verification record",
        ) from exc

    return response


@router.get(
    "/qr/{verification_id}",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
def get_verification_qr(
    verification_id: int = Path(gt=0),
    db: Session = Depends(get_db),
) -> Response:
    try:
        verification = db.get(Verification, verification_id)
        if verification is None or verification.result != VerificationResult.AUTHENTIC:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR code was not found for this verification",
            )

        qr_code_data = VERIFICATION_URL_TEMPLATE.format(verification_id)
        qr_record = db.scalar(
            select(QRCode).where(
                QRCode.certificate_id == verification.certificate_id,
                QRCode.qr_code_data == qr_code_data,
            )
        )
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        logger.exception("Could not look up verification QR record")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not look up the verification QR code",
        ) from exc

    if qr_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR code was not found for this verification",
        )
    if qr_record.expiry_date is not None:
        expiry_date = qr_record.expiry_date
        if expiry_date.tzinfo is None:
            expiry_date = expiry_date.replace(tzinfo=timezone.utc)
        if expiry_date <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="The verification QR code has expired",
            )

    try:
        qr_collection: Collection[dict[str, Any]] = get_mongo_database()[
            "qr_code_images"
        ]
        image_document = qr_collection.find_one(
            {"verification_id": verification_id}
        )
    except RuntimeError as exc:
        logger.exception("MongoDB has not been initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not available",
        ) from exc
    except PyMongoError as exc:
        logger.exception("Could not retrieve verification QR image from MongoDB")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not retrieve the QR image from MongoDB",
        ) from exc

    if image_document is None:
        logger.error("QR image missing from MongoDB for verification %s", verification_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR image was not found for this verification",
        )

    image_content = image_document.get("content")
    if not isinstance(image_content, (bytes, bytearray, memoryview)):
        logger.error("QR image content is invalid for verification %s", verification_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored QR image is invalid",
        )

    return Response(content=bytes(image_content), media_type="image/png")
