"""
Сервис генерации и экспорта чистого агрономического журнала поля.
Гарантирует:
1. Квантование всех вещественных чисел строго до 2 знаков после запятой (исключение шума IEEE-754).
2. Нормализованную структуру CSV (отсутствие мусорных колонок ',,,,,,,,').
3. Кодировку UTF-8-BOM (utf-8-sig) для мгновенного корректного открытия в Excel на Windows.
4. Отдачу готового BufferedInputFile для aiogram 3.x.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from decimal import Decimal
from typing import Any, List

from aiogram.types import BufferedInputFile
from bot.schemas.field import UnifiedJournalRecord, quantize_2dp


class FieldExportService:
    """Сервис экспорта журнала полива и баланса влажности в CSV."""

    @staticmethod
    def _format_cell(value: Any) -> str:
        """Вспомогательное форматирование ячейки с гарантией 2 знаков после запятой."""
        if value is None or value == "":
            return "0.00"
        if isinstance(value, Decimal):
            return f"{value:.2f}"
        try:
            val_f = float(value)
            return f"{val_f:.2f}"
        except (ValueError, TypeError):
            return str(value)

    @classmethod
    def generate_journal_csv(cls, field_name: str, records: List[UnifiedJournalRecord]) -> io.BytesIO:
        """
        Создает чистый CSV-поток в памяти без висячих запятых и с понятными фермеру заголовками.
        """
        output = io.StringIO(newline="")
        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

        # 1. Метаданные отчета в шапке
        writer.writerow(["# ОТЧЕТ ПОЛЯ:", field_name])
        writer.writerow(["# ДАТА ФОРМИРОВАНИЯ:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        writer.writerow(["# ТАЙМЗОНА:", "Asia/Atyrau (UTC+5)"])
        writer.writerow([])

        # 2. Человекочитаемые нормализованные заголовки
        headers = [
            "Дата и время",
            "Тип записи",
            "Дата баланса",
            "Таймзона",
            "ET₀ (мм)",
            "Осадки (мм)",
            "Эфф. осадки (мм)",
            "ETc (мм)",
            "Дефицит ДО (мм)",
            "Дефицит ПОСЛЕ (мм)",
            "Статус",
            "Чистая потребность (м³)",
            "Валовый объем (м³)",
            "Полито факт (м³)",
            "Источник данных",
        ]
        writer.writerow(headers)

        # 3. Сортировка по хронологии
        sorted_records = sorted(records, key=lambda r: r.timestamp)

        # 4. Нормализованные строки: единый контракт колонок
        for rec in sorted_records:
            writer.writerow([
                rec.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "Расчет баланса" if rec.record_type == "balance" else "Факт полива",
                rec.date_str,
                rec.timezone,
                cls._format_cell(rec.et0_mm),
                cls._format_cell(rec.rain_mm),
                cls._format_cell(rec.effective_rain_mm),
                cls._format_cell(rec.etc_mm),
                cls._format_cell(rec.deficit_before_mm),
                cls._format_cell(rec.deficit_after_mm),
                rec.status,
                cls._format_cell(rec.net_m3),
                cls._format_cell(rec.gross_m3),
                cls._format_cell(rec.applied_m3),
                rec.source,
            ])

        # 5. Упаковка в UTF-8 с BOM сигнатурой
        csv_bytes = output.getvalue().encode("utf-8-sig")
        byte_stream = io.BytesIO(csv_bytes)
        byte_stream.seek(0)
        return byte_stream

    @classmethod
    def get_telegram_document(
        cls,
        field_id: int,
        field_name: str,
        records: List[UnifiedJournalRecord],
    ) -> BufferedInputFile:
        """
        Формирует объект BufferedInputFile для отправки через Telegram Bot API.
        """
        byte_stream = cls.generate_journal_csv(field_name, records)
        safe_name = "".join(c for c in field_name if c.isalnum() or c in ("-", "_")).strip()
        if not safe_name:
            safe_name = f"field_{field_id}"
        
        filename = f"su_tech_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        return BufferedInputFile(byte_stream.getvalue(), filename=filename)
