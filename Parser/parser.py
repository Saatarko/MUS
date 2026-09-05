import pandas as pd
from pathlib import Path

from collections import Counter
from collections import Counter
import pandas as pd


def normalize_1c_table(
    df_raw: pd.DataFrame,
    header_row: int,
    end_row: int,
    analyze_rows: int = 20,
) -> pd.DataFrame:

    df = df_raw.copy()

    # ---------------------------------------------------------
    # 1. Берём только строки после шапки
    # ---------------------------------------------------------

    # data = df.iloc[header_row + 1:].copy()

    # ---------------------------------------------------------
    # 2. Ограничиваем реальным номером последней строки
    # ---------------------------------------------------------

    data = df[
        (df["№ строки"] > header_row) &
        (df["№ строки"] <= end_row)
        ].copy()

    # ---------------------------------------------------------
    # 3. Анализируем первые строки
    # ---------------------------------------------------------

    patterns = []

    for _, row in data.head(analyze_rows).iterrows():

        filled_columns = tuple(
            col
            for col, value in row.items()
            if col != "№ строки"
            and pd.notna(value)
            and str(value).strip()
            and str(value).strip().lower() != "nan"
        )

        if filled_columns:
            patterns.append(filled_columns)

    if not patterns:
        raise ValueError(
            "Не удалось определить структуру табличной области."
        )

    pattern_counter = Counter(patterns)

    # Основной шаблон:
    # сначала максимальное количество заполненных колонок,
    # затем частота появления
    main_pattern = max(
        pattern_counter,
        key=lambda pattern: (
            len(pattern),
            pattern_counter[pattern]
        )
    )

    print("\n========== 1C STRUCTURE ==========\n")
    print(f"Шапка: строка {header_row}")
    print(f"Последняя строка данных: {end_row}")
    print(f"Фактически обработано строк: {len(data)}")
    print(f"Основной шаблон: {list(main_pattern)}")
    print(f"Количество колонок в шаблоне: {len(main_pattern)}")

    print("\nШаблоны первых строк:")

    for pattern, count in pattern_counter.most_common():
        print(
            f"{count:>2} раз | "
            f"{list(pattern)}"
        )

    print("\n==================================\n")

    # ---------------------------------------------------------
    # 4. Собираем логические записи
    # ---------------------------------------------------------

    records = []
    current = None

    for _, row in data.iterrows():

        filled_columns = tuple(
            col
            for col, value in row.items()
            if col != "№ строки"
            and pd.notna(value)
            and str(value).strip()
            and str(value).strip().lower() != "nan"
        )

        # print(
        #     f"Строка {row['№ строки']}: "
        #     f"pattern={list(filled_columns)}, "
        #     f"main={list(main_pattern)}, "
        #     f"match={filled_columns == main_pattern}"
        # )
        #
        # print(
        #     f"Строка {row['№ строки']}: "
        #     f"{list(filled_columns)} "
        #     f"{'<<< NEW' if filled_columns == main_pattern else ''}"
        # )

        # Новая логическая запись
        main_set = set(main_pattern)

        pattern_set = set(filled_columns)

        similarity = (
                len(pattern_set & main_set) / len(main_set)
        )

        is_main = similarity >= 0.7

        if is_main:
            if current is not None:
                records.append(current)

                if is_main and filled_columns != main_pattern:
                    print(
                        f"Строка {row['№ строки']}: "
                        f"вариант основного паттерна "
                        f"{list(filled_columns)}, "
                        f"{similarity:.1%} → NEW"
                    )

            current = row.copy()
            continue


        # Продолжение предыдущей записи
        if current is None:
            continue

        for col in df.columns:

            if col == "№ строки":
                continue

            value = row[col]

            if pd.isna(value):
                continue

            value = str(value).strip()

            if not value or value.lower() == "nan":
                continue

            current_value = current[col]

            if pd.isna(current_value):

                current[col] = value

            else:

                current_value = str(current_value).strip()

                if not current_value:
                    current[col] = value
                else:
                    current[col] = (
                        f"{current_value} {value}"
                    )

    # Добавляем последнюю запись
    if current is not None:
        records.append(current)

    result = (
        pd.DataFrame(records)
        .reset_index(drop=True)
    )
    #
    # print("\n========== NORMALIZED 1C TABLE ==========\n")
    # print(result.head(10).to_string(index=False))
    # print("\n==========================================\n")

    return result

def normalize_columns(
    df: pd.DataFrame,
    anomaly_threshold: int = 5,
):

    df = df.copy()

    # "№ строки" — технический столбец
    data_columns = [
        col
        for col in df.columns
        if col != "№ строки"
    ]

    # ---------------------------------------------------------
    # 1. Полностью пустые столбцы
    # ---------------------------------------------------------

    empty_columns = [
        col
        for col in data_columns
        if df[col].isna().all()
    ]

    if empty_columns:

        print(
            "Удаляем полностью пустые столбцы:",
            empty_columns
        )

        df = df.drop(
            columns=empty_columns
        )

    # ---------------------------------------------------------
    # 2. Анализируем оставшиеся столбцы
    # ---------------------------------------------------------

    data_columns = [
        col
        for col in df.columns
        if col != "№ строки"
    ]

    print("\n========== COLUMN ANALYSIS ==========\n")

    anomalies = []

    for col in data_columns:

        filled_count = df[col].notna().sum()
        nan_count = df[col].isna().sum()

        print(
            f"Колонка {col}: "
            f"NaN = {nan_count}, "
            f"заполнено = {filled_count}"
        )

        # -----------------------------------------------------
        # Редкие значения → аномалия
        # -----------------------------------------------------

        if 0 < filled_count <= anomaly_threshold:

            rows = (
                df.loc[
                    df[col].notna(),
                    "№ строки"
                ]
                .astype(int)
                .tolist()
            )

            anomalies.append({
                "column": col,
                "rows": rows,
                "count": filled_count,
            })

    print("\n=====================================\n")

    # ---------------------------------------------------------
    # 3. Ищем кандидатов на объединение
    #
    #    Редкие значения НЕ объединяем.
    # ---------------------------------------------------------

    candidate_columns = [
        col
        for col in data_columns
        if (
            df[col].isna().sum() > 0
            and df[col].notna().sum() > anomaly_threshold
        )
    ]

    print(
        "Кандидаты на объединение:",
        candidate_columns
    )

    # ---------------------------------------------------------
    # 4. Объединяем кандидатов с левым столбцом
    # ---------------------------------------------------------

    columns_to_drop = []

    for col in candidate_columns:

        col_index = data_columns.index(col)

        if col_index == 0:
            continue

        left_col = data_columns[col_index - 1]

        print(
            f"Объединяем: {col} -> {left_col}"
        )

        left = df[left_col]
        right = df[col]

        df[left_col] = (
            left.fillna("")
            .astype(str)
            .str.strip()
            + " "
            + right.fillna("")
            .astype(str)
            .str.strip()
        ).str.strip()

        columns_to_drop.append(col)

    # ---------------------------------------------------------
    # 5. Удаляем присоединённые столбцы
    # ---------------------------------------------------------

    if columns_to_drop:

        df = df.drop(
            columns=columns_to_drop
        )

    # ---------------------------------------------------------
    # 6. Формируем сообщение об аномалиях
    # ---------------------------------------------------------

    if anomalies:

        anomaly_rows = sorted({
            row
            for anomaly in anomalies
            for row in anomaly["rows"]
        })

        message = anomaly_rows

    else:

        message = None

    # print("\n========== NORMALIZED COLUMNS ==========\n")
    # print(df.head(10).to_string(index=False))

    if message:
        print(
            "\nАНОМАЛИИ:",
            message
        )
    else:
        print(
            "\nАНОМАЛИЙ НЕ ОБНАРУЖЕНО"
        )

    print("\n=========================================\n")

    return df, message

def pre_parser(file_path: str, sheet_name=0):

    ext = Path(file_path).suffix.lower()

    if ext in [".xlsx", ".xlsm"]:
        df_raw = pd.read_excel(
            file_path,
            header=None,
            sheet_name=sheet_name,
            engine="openpyxl"
        )

    elif ext == ".xls":
        df_raw = pd.read_excel(
            file_path,
            header=None,
            sheet_name=sheet_name,
            engine="xlrd"
        )

    elif ext == ".csv":
        df_raw = pd.read_csv(
            file_path,
            header=None
        )

    else:
        raise ValueError(f"Неподдерживаемый формат файла: {ext}")

    df_raw.insert(
        0,
        "№ строки",
        range(1, len(df_raw) + 1)
    )

    return df_raw

def parse_1c_table(
    df_raw: pd.DataFrame,
    id_col: int,
    date_col: int,
    amount_col: int,
    start_row: int,
    end_row: int,
    extra_cols: list = None,
) -> pd.DataFrame:

    # 1. Берём реальные номера строк Excel.
    #    start_row — строка шапки,
    #    поэтому начинаем со следующей строки.
    df = df_raw[
        (df_raw["№ строки"] > start_row) &
        (df_raw["№ строки"] <= end_row)
    ].copy()

    # 2. Основные поля
    df["doc_id"] = df[id_col]
    df["date"] = df[date_col]
    df["amount"] = df[amount_col]

    # 3. Примечание
    if extra_cols:
        df["note"] = (
            df[extra_cols]
            .fillna("")
            .astype(str)
            .agg(" ".join, axis=1)
        )
    else:
        df["note"] = ""

    # 4. Очистка
    df["doc_id"] = (
        df["doc_id"]
        .astype(str)
        .str.strip()
    )

    df["date"] = (
        df["date"]
        .astype(str)
        .str.strip()
    )

    df["amount"] = (
        df["amount"]
        .astype(str)
        .str.replace(",", ".", regex=False)
        .str.replace(" ", "", regex=False)
    )

    df["amount"] = pd.to_numeric(
        df["amount"],
        errors="coerce"
    )

    # 5. Фильтрация
    df = df.dropna(
        subset=["doc_id", "amount", "date"]
    )

    df = df[
        ~df["doc_id"]
        .str.lower()
        .str.contains("итого", na=False)
    ]

    return (
        df[
            ["doc_id", "date", "amount", "note"]
        ]
        .reset_index(drop=True)
    )

def detect_table_area(df_raw: pd.DataFrame, scan_rows: int = 50):
    """
    Пытается определить строку шапки и начало табличных данных.
    Пока только диагностика — ничего не изменяет.
    """

    df = df_raw.copy()

    max_row = min(scan_rows, len(df))

    print("\n========== TABLE DETECTION ==========\n")

    for row_idx in range(max_row):
        row = df.iloc[row_idx]

        values = []
        for col_idx, value in enumerate(row):
            if pd.isna(value):
                continue

            value = str(value).strip()

            if value:
                values.append((col_idx, value))

        print(
            f"row {row_idx:>3}: "
            f"{len(values):>2} non-empty cells | "
            f"{values}"
        )

    print("\n=====================================\n")

def analyze_table_structure(
    df_raw: pd.DataFrame,
    header_row: int,
    rows_to_check: int = 20
):
    df = df_raw.copy()

    print("\n========== TABLE STRUCTURE ==========\n")

    for row_idx in range(
        header_row + 1,
        min(header_row + 1 + rows_to_check, len(df))
    ):
        row = df.iloc[row_idx]

        filled = []

        for col_idx, value in enumerate(row):
            # № строки не участвует в анализе
            if col_idx == 0:
                continue

            if pd.notna(value) and str(value).strip():
                filled.append(col_idx)

        print(
            f"row {row_idx:>3}: "
            f"{len(filled):>2} cells | "
            f"{filled}"
        )

    print("\n====================================\n")


from collections import Counter


def detect_structure(
    df_raw: pd.DataFrame,
    header_row: int,
    rows_to_check: int = 20,
):
    df = df_raw.copy()

    # Техническая колонка № строки не участвует
    data = df.iloc[
        header_row + 1:
        header_row + 1 + rows_to_check
    ]

    patterns = []

    for row_idx, row in data.iterrows():
        filled_columns = tuple(
            col_idx
            for col_idx, value in enumerate(row)
            if col_idx != 0
            and pd.notna(value)
            and str(value).strip()
        )

        if filled_columns:
            patterns.append((row_idx, filled_columns))

    counter = Counter(
        pattern
        for _, pattern in patterns
    )

    print("\n========== STRUCTURE ==========\n")

    for pattern, count in counter.most_common():
        print(
            f"{count:>2} раз | "
            f"колонки: {list(pattern)}"
        )

    print("\n--- ROWS ---\n")

    for row_idx, pattern in patterns:
        print(
            f"row {row_idx:>3}: "
            f"{list(pattern)}"
        )

    print("\n===============================\n")

    return counter
