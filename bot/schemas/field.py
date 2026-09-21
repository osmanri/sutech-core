"""
Pydantic v2 схемы данных для модуля полей и агрономического аудита FAO-56.
Все числовые значения объемов и дефицита строго округляются до 2 знаков.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


def quantize_2dp(value: Optional[float | Decimal | str | int]) -> Optional[Decimal]:
    """Строгое округление поливных метрик и дефицита до 2 знаков (Decimal 0.01)."""
    if value is None or value == "":
        return None
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def quantize_coord(value: Optional[float | Decimal | str | int]) -> Optional[Decimal]:
    """Точное квантование географических координат поля до 4 знаков (Decimal 0.0001)."""
    if value is None or value == "":
        return None
    return Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


class CropType(str, Enum):
    WHEAT = "wheat"
    COTTON = "cotton"
    CORN = "corn"
    ALFALFA = "alfalfa"
    MELON = "melon"
    TOMATO = "tomato"
    POTATO = "potato"
    OTHER = "other"


class IrrigationMethod(str, Enum):
    DRIP = "drip"
    SUBSURFACE = "subsurface"
    SPRINKLER = "sprinkler"
    PIVOT = "pivot"
    FURROW = "furrow"


class SoilType(str, Enum):
    SAND = "sand"
    LOAM = "loam"
    CLAY = "clay"


class IrrigationStatus(str, Enum):
    NORMAL = "deferred"       # Полив не требуется
    IRRIGATE = "irrigate"     # Достигнут порог полива
    CRITICAL = "critical"     # Критический стресс (дефицит > RAW)
    RICE = "rice"             # Режим затопления для риса


class FieldBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., min_length=1, max_length=100, description="Название поля")
    crop_type: CropType = Field(default=CropType.TOMATO, description="Культура")
    area_ha: Decimal = Field(..., gt=0, le=50000, description="Площадь в гектарах")
    irrigation_method: IrrigationMethod = Field(default=IrrigationMethod.DRIP, description="Способ полива")
    soil_type: SoilType = Field(default=SoilType.LOAM, description="Тип почвы")
    
    # Геопривязка: Атырау (Asia/Atyrau, UTC+5)
    latitude: Decimal = Field(default=Decimal("47.1167"), ge=-90, le=90, description="Широта")
    longitude: Decimal = Field(default=Decimal("51.8833"), ge=-180, le=180, description="Долгота")
    timezone: str = Field(default="Asia/Atyrau", description="Таймзона")

    @field_validator("area_ha", mode="before")
    @classmethod
    def validate_area(cls, v):
        return quantize_2dp(v)

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def validate_coords(cls, v):
        return quantize_coord(v)


class FieldCreate(FieldBase):
    planting_date: date = Field(default_factory=date.today, description="Дата сева/посадки")


class FieldUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    crop_type: Optional[CropType] = None
    area_ha: Optional[Decimal] = Field(None, gt=0, le=50000)
    irrigation_method: Optional[IrrigationMethod] = None
    soil_type: Optional[SoilType] = None
    latitude: Optional[Decimal] = Field(None, ge=-90, le=90)
    longitude: Optional[Decimal] = Field(None, ge=-180, le=180)

    @field_validator("area_ha", mode="before")
    @classmethod
    def validate_update_area(cls, v):
        return quantize_2dp(v)

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def validate_update_coords(cls, v):
        return quantize_coord(v)


class FieldResponse(FieldBase):
    id: int
    user_id: int
    planting_date: date
    accumulated_deficit_mm: Decimal = Field(default=Decimal("0.00"), description="Накопленный дефицит в мм")
    current_status: IrrigationStatus = Field(default=IrrigationStatus.NORMAL, description="Статус полива")
    recommended_volume_m3: Decimal = Field(default=Decimal("0.00"), description="Рекомендуемый поливной объем")

    @field_validator("accumulated_deficit_mm", "recommended_volume_m3", mode="before")
    @classmethod
    def validate_metrics(cls, v):
        return quantize_2dp(v) or Decimal("0.00")


class UnifiedJournalRecord(BaseModel):
    """
    Нормализованная запись журнала поливов и суточного водного баланса.
    Исключает дыры и неконсистентность схемы в CSV экспорте.
    """
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime = Field(..., description="Метка времени события")
    record_type: str = Field(..., description="'balance' или 'irrigation'")
    date_str: str = Field(..., description="Дата YYYY-MM-DD")
    timezone: str = Field(default="Asia/Atyrau")
    et0_mm: Optional[Decimal] = Field(None, description="Опорное испарение ET0")
    rain_mm: Optional[Decimal] = Field(None, description="Осадки")
    effective_rain_mm: Optional[Decimal] = Field(None, description="Эффективные осадки")
    etc_mm: Optional[Decimal] = Field(None, description="Водопотребление культуры ETc")
    deficit_before_mm: Decimal = Field(..., description="Дефицит до события")
    deficit_after_mm: Decimal = Field(..., description="Дефицит после события")
    status: str = Field(..., description="Статус баланса")
    net_m3: Optional[Decimal] = Field(None, description="Чистая потребность в воде")
    gross_m3: Optional[Decimal] = Field(None, description="Объем с учетом КПД полива")
    applied_m3: Optional[Decimal] = Field(None, description="Фактически поданный объем воды")
    source: str = Field(default="Open-Meteo / FAO-56")

    @field_validator(
        "et0_mm", "rain_mm", "effective_rain_mm", "etc_mm",
        "deficit_before_mm", "deficit_after_mm", "net_m3", "gross_m3", "applied_m3",
        mode="before"
    )
    @classmethod
    def format_all_numbers(cls, v):
        return quantize_2dp(v)
