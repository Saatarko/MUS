import sys

import numpy as np
from PyQt6 import uic
from datetime import datetime
from PyQt6.QtCore import QSize, pyqtSignal, QTimer, Qt, QStringListModel
from PyQt6.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import QMainWindow, QTableWidgetItem, QStyle, QMessageBox, QTableWidget, QFileDialog
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout,
    QPushButton, QLabel
)
from PyQt6.QtGui import QColor, QBrush

from Parser.parser import parse_1c_table, pre_parser, normalize_1c_table, normalize_columns
from database import Database
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

import qdarkstyle

import logging

style = QApplication.style()
LAST_WINDOW_POS = None



logging.basicConfig(
    filename="mus_error.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def resource_path(relative_path):
    import sys, os
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def center_window(window):
    global LAST_WINDOW_POS

    geo = window.frameGeometry()

    if LAST_WINDOW_POS:
        # 👉 двигаем центр окна в сохранённую точку
        geo.moveCenter(LAST_WINDOW_POS)
        window.move(geo.topLeft())
        return

    # 👉 стандартный центр экрана
    screen = window.screen()
    screen_geometry = screen.availableGeometry()

    geo.moveCenter(screen_geometry.center())
    window.move(geo.topLeft())

class BaseWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._first_show = True

    def showEvent(self, event):
        super().showEvent(event)

        if self._first_show:
            center_window(self)
            self._first_show = False

    def moveEvent(self, event):
        super().moveEvent(event)

        global LAST_WINDOW_POS

        if not self._first_show:
            geo = self.frameGeometry()
            LAST_WINDOW_POS = geo.center()  # 👉 сохраняем центр

class BaseWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._first_show = True

    def showEvent(self, event):
        super().showEvent(event)

        if self._first_show:
            center_window(self)
            self._first_show = False

    def moveEvent(self, event):
        super().moveEvent(event)

        global LAST_WINDOW_POS

        if not self._first_show:
            geo = self.frameGeometry()
            LAST_WINDOW_POS = geo.center()  # 👉 сохраняем центр

class MainWindow(BaseWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi(resource_path("gui/main.ui"), self)
        # uic.loadUi("gui/main.ui", self)
        center_window(self)

        # подключаем кнопку
        self.btn_start.clicked.connect(self.open_firm_window)
        self.btn_exit.clicked.connect(self.close)
        self.btn_edit_acc_desc.clicked.connect(self.open_acc_desc_window)

        self.path  = self.text_db.text().strip()

        self.setFixedSize(self.size())

    def open_firm_window(self):
        self.firm_window = FirmWindow(self.path)
        self.firm_window.show()

        self.close()  # закрываем текущее окно

    def open_acc_desc_window(self):
        self.acc_desc_window = AccountDescWindow(self.path)
        self.acc_desc_window.show()

        self.close()  # закрываем текущее окно


class Edit_Firm(BaseWidget):

    firm_edit = pyqtSignal()


    def __init__(self, db, id):
        super().__init__()
        uic.loadUi(resource_path("gui/edit_firm.ui"), self)
        center_window(self)

        self.id = id

        name = db.get_firm(self.id)
        self.name = name["name"]

        self.text_edit_firm.setText(self.name)

        self.db = db
        # подключаем кнопку
        self.btn_edit_firm.clicked.connect(self.edit_firm)

        self.btn_exit_edit_firm.clicked.connect(self.close)

        self.setFixedSize(self.size())


    def edit_firm(self):

        new_firm = self.text_edit_firm.text().strip()

        if not new_firm:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Поле с названием пустое. Добавление отменено"
            )
            return

        success, error = self.db.update_firm(self.id, new_firm)

        if success:
            self.firm_edit.emit()
            self.close()
        else:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Такое название уже существует"
            )


class Add_Cheks(BaseWidget):
    checks_add = pyqtSignal()

    def __init__(self, db, firm_id):
        super().__init__()
        uic.loadUi(resource_path("gui/create_checks.ui"), self)
        center_window(self)

        self.db = db
        self.firm_id = firm_id

        self.spin_materiality.setMinimum(0)
        self.spin_materiality.setMaximum(1_000_000_000)
        self.spin_materiality.setDecimals(2)

        # Уровни риска
        risks = [
            "низкий",
            "средний",
            "высокий",
            "проверка сплошным порядком",
        ]

        self.Risk_create_check.addItems(risks)

        # подключаем кнопку
        self.btn_checks_create.clicked.connect(self.add)
        self.btn_checks_back.clicked.connect(self.close)

        self.setFixedSize(self.size())

    def add(self):

        period  = self.text_period_checks.text().strip()

        materiality = self.spin_materiality.value()

        risk = self.Risk_create_check.currentText()

        if not period or not materiality:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Не все поля заполнены"
            )
            return

        self.db.add_check(self.firm_id, period, risk, materiality)
        self.checks_add.emit()
        self.close()

class Edit_Checks(BaseWidget):

    check_edit = pyqtSignal()


    def __init__(self, db, check_id):
        super().__init__()
        uic.loadUi(resource_path("gui/edit_checks.ui"), self)
        center_window(self)

        self.db = db

        self.check_id = check_id

        self.spin_materiality_edit.setMinimum(0)
        self.spin_materiality_edit.setMaximum(1_000_000_000)
        self.spin_materiality_edit.setDecimals(2)

        temp = self.db.get_one_checks(self.check_id)

        self.period = temp["period"][0]
        self.materiality = temp["materiality"][0]
        self.created_at = temp["created_at"][0]

        self.risk = temp["risk"][0]

        # Уровни риска
        risks = [
            "низкий",
            "средний",
            "высокий",
            "проверка сплошным порядком",
        ]

        self.Risk_edit_check.addItems(risks)
        self.Risk_edit_check.setCurrentText(self.risk)

        self.text_period_checks_edit.setText(self.period)

        self.spin_materiality_edit.setValue(self.materiality)

        self.btn_checks_edit_back.clicked.connect(self.close)
        # подключаем кнопку
        self.btn_checks_create_edit.clicked.connect(self.edit)

        self.setFixedSize(self.size())


    def edit(self):

        period  = self.text_period_checks_edit.text().strip()

        materiality = self.spin_materiality_edit.value()

        risk = self.Risk_edit_check.currentText()

        if not period or not materiality:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Не все поля заполнены!"
            )
            return

        self.db.update_check(self.check_id, period, risk, materiality)
        self.check_edit.emit()
        self.close()


class ResultWindow(BaseWindow):

    def __init__(self, db, firm_id, check_id, acc_id, name):
        super().__init__()
        uic.loadUi(resource_path("gui/results.ui"), self)
        center_window(self)

        self.db = db

        self.firm_id = firm_id
        self.check_id = check_id

        self.acc_id = acc_id

        self.name = name

        # подключаем кнопку
        self.text_result_name.setText(self.name)

        self.load_preview_table()

        self.btn_result_back.clicked.connect(self.open_data)

        self.btn_calc_result.clicked.connect(self.calc_result)

        self.btn_save_xmls.clicked.connect(self.save_excel)

        self.setFixedSize(self.size())

    def calc_result(self):

        self.db.clear_results(self.acc_id)
        self.db.run_mus(self.check_id, self.acc_id, self.name)
        self.load_preview_table()

    def open_data(self):
        self.close()
        # тут откроешь окно проверок
        self.open_data_win = DataWindow(self.db, self.firm_id, self.check_id, self.acc_id)
        self.open_data_win.show()

    def save_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить файл",
            "",
            "Excel Files (*.xlsx)"
        )

        if path:
            if not path.endswith(".xlsx"):
                path += ".xlsx"

            self.export_to_excel(path)

    def export_to_excel(self, path):

        # ============================================================
        # 1. Получаем данные
        # ============================================================

        firm = self.db.get_firm(self.firm_id)
        check = self.db.get_one_checks(self.check_id)
        acc_desc = self.db.get_acc_desc_by_name(self.name)

        firm_name = firm["name"]

        period = check["period"][0]
        materiality = check["materiality"][0]

        risk = check["risk"][0]

        account_name = acc_desc["name"][0]
        account_description = acc_desc["description"][0]

        # ============================================================
        # 2. Параметры MUS
        # ============================================================

        params = [
            ("PM", self.PM),
            ("n", self.n),
            ("h", self.h),
            ("Покрытие (%)", self.coverage),
            ("Итого", self.total),
            ("Наибольшая сумма", self.high_value_sum),
            ("MUS сумма", self.mus_sum),
            ("Тестовая сумма", self.test_sum),
            ("Сообщения", self.messages)
        ]

        # ============================================================
        # 3. Итоговая выборка
        # ============================================================

        df = self.df.copy()

        df.columns = [
            "Номер документа",
            "Дата",
            "Примечание",
            "Сумма",
            "Причина"
        ]

        # ============================================================
        # 4. Создаём Excel
        # ============================================================

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(
                writer,
                sheet_name="MUS",
                index=False,
                startrow=12
            )

        wb = load_workbook(path)

        # ============================================================
        # 5. Лист 1 — Информация
        # ============================================================

        ws_info = wb.create_sheet("Информация", 0)

        # --- ширина колонок
        ws_info.column_dimensions["A"].width = 40
        ws_info.column_dimensions["B"].width = 35
        ws_info.column_dimensions["C"].width = 4

        ws_info.column_dimensions["D"].width = 30
        ws_info.column_dimensions["E"].width = 30
        ws_info.column_dimensions["F"].width = 30
        ws_info.column_dimensions["G"].width = 30
        ws_info.column_dimensions["H"].width = 30

        # ============================================================
        # 6. Стили
        # ============================================================

        title_font = Font(
            bold=True,
            size=18
        )

        label_font = Font(
            bold=True,
            size=12
        )

        value_font = Font(
            size=12
        )

        description_font = Font(
            size=11
        )

        border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin")
        )

        center = Alignment(
            horizontal="center",
            vertical="center"
        )

        left = Alignment(
            horizontal="left",
            vertical="center"
        )

        description_alignment = Alignment(
            horizontal="left",
            vertical="top",
            wrap_text=True
        )

        # ============================================================
        # 7. Заголовок
        # ============================================================

        ws_info.merge_cells("A1:H1")

        ws_info["A1"] = "Информация о проверке"
        ws_info["A1"].font = title_font
        ws_info["A1"].alignment = center

        ws_info.row_dimensions[1].height = 35

        # ============================================================
        # 8. Левая часть — информация о проверке
        # ============================================================

        ws_info["A3"] = "Организация"
        ws_info["A4"] = "Период проверки"
        ws_info["A5"] = "Уровень существенности"
        ws_info["A6"] = "Риск"

        for cell in ["A3", "A4", "A5", "A6"]:
            ws_info[cell].font = label_font
            ws_info[cell].alignment = left

        ws_info["B3"] = firm_name
        ws_info["B4"] = period
        ws_info["B5"] = materiality
        ws_info["B6"] = risk

        for cell in ["B3", "B4", "B5", "B6"]:
            ws_info[cell].font = value_font
            ws_info[cell].alignment = left
            ws_info[cell].border = border

        # ============================================================
        # 9. Правая часть — счёт
        # ============================================================

        ws_info["D3"] = "Счёт"
        ws_info["D3"].font = label_font
        ws_info["D3"].alignment = left

        ws_info.merge_cells("E3:H3")

        ws_info["E3"] = account_name
        ws_info["E3"].font = value_font
        ws_info["E3"].alignment = left

        for row in ws_info["E3:H3"][0]:
            row.border = border

        # ============================================================
        # 10. Описание счёта
        # ============================================================

        ws_info["D5"] = "Описание"
        ws_info["D5"].font = label_font
        ws_info["D5"].alignment = left

        # Большое поле под текст требований Аудиторской палаты
        ws_info.merge_cells("D6:H10")

        ws_info["D6"] = account_description
        ws_info["D6"].font = description_font
        ws_info["D6"].alignment = description_alignment

        # Рамка вокруг объединённого поля
        for row in ws_info["D6:H10"]:
            for cell in row:
                cell.border = border

        # Высота строк под описание
        for row in range(6, 11):
            ws_info.row_dimensions[row].height = 55

        ws_info["D13"] = "Выполнение:"
        ws_info["D13"].font = label_font
        ws_info["D13"].alignment = left

        # Объединение полей под выполнение
        ws_info.merge_cells("E13:F18")

        # Рамка вокруг объединённого поля
        for row in ws_info["E13:F18"]:
            for cell in row:
                cell.border = border

        # Высота строк под описание
        for row in range(13, 19):
            ws_info.row_dimensions[row].height = 15

        # Объединение полей под выполнение
        ws_info.merge_cells("G13:H18")

        # Рамка вокруг объединённого поля
        for row in ws_info["G13:H18"]:
            for cell in row:
                cell.border = border

        # Высота строк под описание
        for row in range(13, 19):
            ws_info.row_dimensions[row].height = 15

        ws_info["D19"] = "Выводы:"
        ws_info["D19"].font = label_font
        ws_info["D19"].alignment = left

        # Объединение полей под выводы
        ws_info.merge_cells("E19:H21")

        # Рамка вокруг объединённого поля
        for row in ws_info["E19:H21"]:
            for cell in row:
                cell.border = border

        # Высота строк под выводы
        for row in range(19, 22):
            ws_info.row_dimensions[row].height = 15

        ws_info["D22"] = "Выполнил:"
        ws_info["D22"].font = label_font
        ws_info["D22"].alignment = left

        # Объединение полей под выполнение
        ws_info.merge_cells("E22:H24")

        # Рамка вокруг объединённого поля
        for row in ws_info["E22:H24"]:
            for cell in row:
                cell.border = border

        # Высота строк под выполнение
        for row in range(22, 25):
            ws_info.row_dimensions[row].height = 30

        # ============================================================
        # 11. Лист MUS
        # ============================================================

        ws = wb["MUS"]

        bold = Font(bold=True, size=12)
        header_font = Font(bold=True)

        center = Alignment(
            horizontal="center",
            vertical="center"
        )

        wrap = Alignment(
            wrap_text=True,
            vertical="top"
        )

        fill_high = PatternFill(
            "solid",
            fgColor="C6EFCE"
        )

        fill_mus = PatternFill(
            "solid",
            fgColor="FFF2CC"
        )

        # ============================================================
        # 12. Заголовок MUS
        # ============================================================

        ws["A1"] = "Результаты MUS выборки"
        ws["A1"].font = Font(
            bold=True,
            size=14
        )

        # ============================================================
        # 13. Параметры MUS
        # ============================================================

        row = 3

        for name, value in params:
            ws[f"A{row}"] = name
            ws[f"B{row}"] = value

            ws[f"A{row}"].font = bold

            row += 1

        # ============================================================
        # 14. Шапка таблицы
        # ============================================================

        header_row = 13

        for col in range(1, ws.max_column + 1):
            cell = ws.cell(
                row=header_row,
                column=col
            )

            cell.font = header_font
            cell.alignment = center

        # ============================================================
        # 15. Подсветка строк
        # ============================================================

        for row in range(
                header_row + 1,
                ws.max_row + 1
        ):

            reason = ws.cell(
                row=row,
                column=5
            ).value

            if reason == "Выше уровня существенности":

                for col in range(
                        1,
                        ws.max_column + 1
                ):
                    ws.cell(
                        row=row,
                        column=col
                    ).fill = fill_high

            elif reason == "Выборка MUS":

                for col in range(
                        1,
                        ws.max_column + 1
                ):
                    ws.cell(
                        row=row,
                        column=col
                    ).fill = fill_mus

        # ============================================================
        # 16. Перенос текста в примечании
        # ============================================================

        for row in range(
                header_row + 1,
                ws.max_row + 1
        ):
            ws.cell(
                row=row,
                column=3
            ).alignment = wrap

        # ============================================================
        # 17. Автоширина колонок
        # ============================================================

        for col in ws.columns:

            max_length = 0

            col_letter = get_column_letter(
                col[0].column
            )

            for cell in col:

                if cell.value is not None:
                    max_length = max(
                        max_length,
                        len(str(cell.value))
                    )

            ws.column_dimensions[
                col_letter
            ].width = min(
                max_length + 2,
                50
            )

        # ============================================================
        # 18. Закрепление шапки
        # ============================================================

        ws.freeze_panes = "A14"

        # ============================================================
        # 19. Фильтр
        # ============================================================

        ws.auto_filter.ref = (
            f"A{header_row}:E{ws.max_row}"
        )

        # ============================================================
        # 20. Сохраняем
        # ============================================================

        wb.save(path)

    def load_preview_table(self):

        temp = self.db.get_results(self.acc_id)



        if temp:

            temp_risk = self.db.get_one_checks(self.check_id)

            self.risk = temp_risk["risk"][0]

            self.PM = temp['PM']
            self.n = temp['n']
            self.h = temp['h']
            self.coverage = temp['coverage']
            self.total = temp['total']
            self. high_value_sum= temp['high_value_sum']
            self.mus_sum = temp['mus_sum']
            self.test_sum= temp['test_sum']
            self.messages = temp['messages']
            self.df= temp['sample']


            self.table_results.setRowCount(self.df.shape[0])
            self.table_results.setColumnCount(self.df.shape[1])

            # заголовки
            self.table_results.setHorizontalHeaderLabels([
                "Номер документа",
                "Дата",
                "Примечание",
                "Сумма",
                "Причина"
            ])

            self.table_results.setColumnWidth(0, 150)
            self.table_results.setColumnWidth(1, 150)
            self.table_results.setColumnWidth(2, 300)
            self.table_results.setColumnWidth(3, 150)
            self.table_results.setColumnWidth(4, 150)

            # заполнение
            for row_idx in range(self.df.shape[0]):
                for col_idx in range(self.df.shape[1]):
                    value = self.df.iat[row_idx, col_idx]

                    item = QTableWidgetItem(str(value))
                    self.table_results.setItem(row_idx, col_idx, item)

            # read-only
            self.table_results.setEditTriggers(
                QTableWidget.EditTrigger.NoEditTriggers
            )
            self.table_results.verticalHeader().setVisible(False)

            layout1 = self.widget_results.layout()
            layout2 = self.widget_results_2.layout()
            layout3 = self.widget_results_3.layout()

            while layout1.rowCount():
                layout1.removeRow(0)
            while layout2.rowCount():
                layout2.removeRow(0)
            while layout3.rowCount():
                layout3.removeRow(0)

            layout1.addRow("Риск:", QLabel(f"{self.risk}"))
            layout1.addRow("PM:", QLabel(f"{self.PM:.2f}"))
            layout1.addRow("n:", QLabel(f"{self.n:,.2f}"))
            layout1.addRow("h:", QLabel(f"{self.h:,.2f}"))
            layout1.addRow("Покрытие:", QLabel(f"{self.coverage:.2%}"))

            layout2.addRow("Итого:", QLabel(f"{self.total:,.2f}"))
            layout2.addRow("Наибольшая сумма:", QLabel(f"{self.high_value_sum:,.2f}"))
            layout2.addRow("MUS сумма:", QLabel(f"{self.mus_sum:,.2f}"))
            layout2.addRow("Тестовая сумма:", QLabel(f"{self.test_sum:,.2f}"))

            msg_label = QLabel("".join(self.messages))
            msg_label.setWordWrap(True)
            msg_label.setStyleSheet("color: red;")

            layout3.addRow("Сообщение:", msg_label)


class DataWindow(BaseWindow):


    def __init__(self, db, firm_id,check_id, acc_id,):
        super().__init__()
        uic.loadUi(resource_path("gui/data.ui"), self)
        center_window(self)

        self.db = db

        self.firm_id = firm_id
        self.check_id = check_id

        self.acc_id = acc_id

        temp = self.db.get_accounts_byid(self.acc_id)
        name = self.db.get_acc_desc_byid(
            int(temp['acc_desc_id'][0])
        )

        self.name = name['name'][0]
        # подключаем кнопку
        self.text_data_account_name.setText(self.name)


        self.btn_data_exit_acc.clicked.connect(self.open_acc)

        self.btn_raw_entity.clicked.connect(self.open_entity)

        self.btn_result.clicked.connect(self.open_result)

        self.setFixedSize(self.size())

    def open_result(self):
        self.close()
        # тут откроешь окно проверок
        self.open_result_win = ResultWindow(self.db, self.firm_id, self.check_id, self.acc_id, self.name)
        self.open_result_win.show()


    def open_acc(self):
        self.close()
        # тут откроешь окно проверок
        self.open_checks = AccountWindow(self.db, self.firm_id, self.check_id)
        self.open_checks.show()

    def open_entity(self):
        self.close()
        # тут откроешь окно проверок
        self.open_entity_win = EntityWindow(self.db, self.firm_id, self.check_id, self.acc_id, self.name)
        self.open_entity_win.show()


class RawData(BaseWindow):

    def __init__(self, db, firm_id, check_id, acc_id, db_raw, name, header_row,end_row):
        super().__init__()
        uic.loadUi(resource_path("gui/raw.ui"), self)
        center_window(self)

        self.db = db
        self.firm_id = firm_id
        self.check_id = check_id
        self.acc_id = acc_id

        self.db_raw = db_raw

        self.name = name

        self.header_row = header_row
        self.end_row = end_row

        # подключаем кнопку
        self.text_raw_name_acc.setText(self.name)

        self.load_preview_table(self.db_raw)

        self.btn_raw_back.clicked.connect(self.open_entity)

        self.btn_raw_new_entity.clicked.connect(self.add_new_entity)

        self.btn_raw_preview.clicked.connect(self.apply_preview)

        self.setFixedSize(self.size())

    def validate_required_columns(
            self,
            df,
            doc_col,
            date_col,
            amount_col,
    ):
        data = df

        fields = {
            "Документ": doc_col,
            "Дата": date_col,
            "Сумма": amount_col,
        }

        errors = []

        for field_name, col in fields.items():

            # Колонка вообще не указана
            if col is None:
                errors.append(
                    f"{field_name}: колонка не указана"
                )
                continue

            # Указанной колонки нет в DataFrame
            if col not in data.columns:
                errors.append(
                    f"{field_name}: колонка {col} отсутствует"
                )
                continue

            # Проверяем пустые значения
            empty_mask = (
                    data[col].isna() |
                    (data[col].astype(str).str.strip() == "")
            )

            for row_num in data.loc[
                empty_mask, "№ строки"
            ]:
                errors.append(
                    f"{field_name}: "
                    f"пустая ячейка "
                    f"(строка № {int(row_num)}, "
                    f"колонка {col})"
                )

        return errors

    def _get_import_params(self):
        """
        Получает и проверяет параметры импорта из элементов интерфейса.

        Возвращает:
            first_row, last_row, doc_col, date_col, amount_col, note_cols

        или None, если параметры некорректны.
        """

        # Строки
        try:
            first_row = int(self.header_row)
            last_row = int(self.end_row)
        except ValueError:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Проверьте номера строк."
            )
            return None

        # Основные колонки
        doc_text = self.text_doc_id_col.text().strip()
        date_text = self.text_data_col.text().strip()
        amount_text = self.text_raw_amount.text().strip()

        try:
            doc_col = int(doc_text) if doc_text else None
            date_col = int(date_text) if date_text else None
            amount_col = int(amount_text) if amount_text else None
        except ValueError:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Номера основных колонок должны быть целыми числами."
            )
            return None

        # Дополнительные колонки
        try:
            note_cols = [
                int(x.strip())
                for x in self.text_note_list.text().split(",")
                if x.strip()
            ]
        except ValueError:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Номера колонок примечаний должны быть целыми числами."
            )
            return None

        # Проверяем обязательные колонки
        errors = self.validate_required_columns(
            self.db_raw,
            doc_col,
            date_col,
            amount_col,
        )

        if errors:
            QMessageBox.warning(
                self,
                "Ошибка данных",
                "\n".join(errors[:10])
            )
            return None

        return (
            first_row,
            last_row,
            doc_col,
            date_col,
            amount_col,
            note_cols,
        )

    def add_new_entity(self):
        params = self._get_import_params()

        if params is None:
            return

        (
            first_row,
            last_row,
            doc_col,
            date_col,
            amount_col,
            note_cols,
        ) = params

        result_df = parse_1c_table(
            self.db_raw,
            id_col=doc_col,
            date_col=date_col,
            amount_col=amount_col,
            start_row=first_row,
            end_row=last_row,
            extra_cols=note_cols
        )

        print("\n========== AFTER parse_1c_table ==========")
        print(f"Количество записей: {len(result_df)}")
        print(result_df.head(15).to_string(index=False))
        print("===========================================\n")

        self.db.insert_entries(self.acc_id, result_df)

        self.open_entity()



    def clear_colors(self, table):
        for row in range(table.rowCount()):
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item:
                    item.setBackground(QBrush())  # ✅ сброс
                    item.setForeground(QBrush())  # (если вдруг тоже менял)

    def apply_preview(self):
        self.clear_colors(self.table_raw_start)

        params = self._get_import_params()

        if params is None:
            return

        (
            first_row,
            last_row,
            doc_col,
            date_col,
            amount_col,
            note_cols,
        ) = params

        self.highlight_table(
            self.table_raw_start,
            self.head,
            first_row,
            last_row,
            {
                "doc": doc_col,
                "date": date_col,
                "amount": amount_col,
                "note": note_cols,
            }
        )

    def open_entity(self):
        self.close()

        self.open_entity_win = EntityWindow(self.db, self.firm_id, self.check_id, self.acc_id, self.name)
        self.open_entity_win.show()

    def load_preview_table(self, df):

        df = df.replace({np.nan: ""})
        self.head= df.head(50)

        self.table_raw_start.setRowCount(self.head.shape[0])
        self.table_raw_start.setColumnCount(self.head.shape[1])

        # заголовки
        self.table_raw_start.setHorizontalHeaderLabels(
            [str(col) for col in self.head.columns]
        )

        # заполнение
        for row_idx in range(self.head.shape[0]):
            for col_idx in range(self.head.shape[1]):
                value = self.head.iat[row_idx, col_idx]

                item = QTableWidgetItem(str(value))
                self.table_raw_start.setItem(row_idx, col_idx, item)

        # read-only
        self.table_raw_start.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.table_raw_start.verticalHeader().setVisible(False)



    def highlight_table(self, table, df_part, first_row, last_row, cols_map):

        col_positions = {
            col_name: idx
            for idx, col_name in enumerate(df_part.columns)
        }

        note_cols = cols_map.get("note", [])

        # 👉 цвет текста для тёмной темы
        text_color = QColor(220, 220, 220)

        for row_idx in range(df_part.shape[0]):
            real_row = df_part.iloc[row_idx, 0]

            if not (first_row <= real_row <= last_row):
                continue

            # --- doc/date/amount
            for key, color in [
                ("doc", QColor(80, 120, 80)),  # более тёмные цвета
                ("date", QColor(120, 120, 60)),
                ("amount", QColor(140, 100, 60)),
            ]:
                col_name = cols_map.get(key)

                if col_name in col_positions:
                    col_idx = col_positions[col_name]

                    item = table.item(row_idx, col_idx)
                    if item:
                        item.setBackground(QBrush(color))
                        item.setForeground(QBrush(text_color))  # 👈 фикс

            # --- note
            for col_name in note_cols:
                if col_name in col_positions:
                    col_idx = col_positions[col_name]

                    item = table.item(row_idx, col_idx)
                    if item:
                        item.setBackground(QBrush(QColor(100, 80, 140)))
                        item.setForeground(QBrush(text_color))  # 👈 фикс

class EntityWindow(BaseWindow):

    def __init__(self, db, firm_id, check_id, acc_id, text_data_account_name):
        super().__init__()
        uic.loadUi(resource_path("gui/entity.ui"), self)
        center_window(self)

        self.db = db

        self.firm_id = firm_id
        self.check_id = check_id

        self.acc_id = acc_id

        self.name = text_data_account_name

        # подключаем кнопку
        self.text_entity_account_name.setText(self.name)

        self.load_entity()

        self.btn_entity_exit_to_data.clicked.connect(self.open_data)

        self.btn_entity_new_file.clicked.connect(self.load_file)

        self.btn_export_raw_data.clicked.connect(self.export_entity)

        self.setFixedSize(self.size())

        self.header_row_line.setMinimum(0)
        self.header_row_line.setMaximum(1_000_000_000)
        self.end_row_line.setMinimum(0)
        self.end_row_line.setMaximum(1_000_000_000)


    def load_file(self):



        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл",
            "",
            "Excel Files (*.xlsx *.xls *.xlsm *.csv)"
        )

        if not file_path:
            return

        header_row = self.header_row_line.value()
        end_row = self.end_row_line.value()

        if header_row <= 0 or end_row <= 0:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Укажите начальную и конечную строки."
            )
            return

        if end_row < header_row:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Конечная строка не может быть меньше начальной."
            )
            return

        try:

            df_raw = pre_parser(file_path)

            df_vertical = normalize_1c_table(
                df_raw,
                header_row=header_row,
                end_row=end_row,
            )

            # print("\n========== AFTER normalize_1c_table ==========")
            # print(f"Количество записей: {len(df_vertical)}")
            # print(
            #     df_vertical[
            #         ["№ строки", 1]
            #     ].head(15).to_string(index=False)
            # )
            # print("==============================================\n")
            #
            # print(
            #     df_vertical[
            #         ["№ строки", 1]
            #     ].tail(15).to_string(index=False)
            # )
            # print("==============================================\n")

            df_normalized, anomalies = normalize_columns(
                df_vertical,
                anomaly_threshold=5,
            )

            # print("\n========== AFTER normalize_columns ==========")
            # print(f"Количество записей: {len(df_normalized)}")
            # print(
            #     df_normalized[
            #         ["№ строки", 1]
            #     ].head(15).to_string(index=False)
            # )
            # print("=============================================\n")
            #
            # print(
            #     df_normalized[
            #         ["№ строки", 1]
            #     ].tail(15).to_string(index=False)
            # )
            # print("=============================================\n")

            if anomalies:
                reply = QMessageBox.question(
                    self,
                    "Обнаружена(ы) аномалия(и) ",
                    f"Строка(и) {anomalies}. Рекомендация проверить данные. Для продолжения загрузки и игонорирования предупреждения нажмите Да, для отмены нажмите нет",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

            else:
                reply = QMessageBox.question(
                    self,
                    "Аномалии не обнаружены",
                    f"Для продолжения загрузки нажмите Да, для отмены нажмите нет",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

            if reply == QMessageBox.StandardButton.Yes:


                self.close()

                self.open_new_entity = RawData(
                    self.db,
                    self.firm_id,
                    self.check_id,
                    self.acc_id,
                    df_normalized,
                    self.name,
                    header_row,
                    end_row,
                )

                self.open_new_entity.show()

        except Exception as e:
            logging.exception(
                "Ошибка при импорте файла: %s",
                file_path
            )

            QMessageBox.critical(
                self,
                "Ошибка импорта",
                f"Не удалось загрузить файл:\n\n{e}"
            )

    def export_entity(self):
        entries = self.db.get_entries(self.acc_id)

        if not entries:
            QMessageBox.information(
                self,
                "Экспорт",
                "Нет данных для экспорта."
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить результат",
            "",
            "Excel Files (*.xlsx)"
        )

        if file_path:
            if not file_path.endswith(".xlsx"):
                file_path += ".xlsx"

        if not file_path:
            return

        try:
            data = []

            for id, account_id, doc_id, date, amount, note in entries:
                data.append({
                    "Документ": doc_id,
                    "Дата": date,
                    "Сумма": amount,
                    "Примечание": note,
                })

            df = pd.DataFrame(data)

            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                df.to_excel(
                    writer,
                    sheet_name="Данные",
                    index=False
                )

            QMessageBox.information(
                self,
                "Экспорт",
                f"Данные успешно сохранены:\n{file_path}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка экспорта",
                f"Не удалось сохранить файл:\n{e}"
            )

    def open_data(self):
        self.close()
        # тут откроешь окно проверок
        self.open_data_win = DataWindow(self.db, self.firm_id, self.check_id, self.acc_id)
        self.open_data_win.show()

    def load_entity(self):
        entries = self.db.get_entries(self.acc_id)

        self.table_entitys.setRowCount(len(entries))
        self.table_entitys.setColumnCount(5)

        self.table_entitys.setHorizontalHeaderLabels([
            "", "Документ", "Дата", "Сумма", "Примечание"
        ])

        self.table_entitys.setColumnWidth(1, 155)
        self.table_entitys.setColumnWidth(2, 110)
        self.table_entitys.setColumnWidth(3, 110)
        self.table_entitys.setColumnWidth(4, 300)

        # Общая сумма
        total = sum(row[4] or 0 for row in entries)

        self.total.setText(f"{total:,.2f}".replace(",", " ").replace(".", ","))

        for row_idx, (id, account_id, doc_id, date, amount, note) in enumerate(entries):
            # --- ID (скрытый)
            self.table_entitys.setItem(
                row_idx, 0,
                QTableWidgetItem(str(id))
            )

            # --- Документ
            self.table_entitys.setItem(
                row_idx, 1,
                QTableWidgetItem(doc_id)
            )

            # --- Дата
            self.table_entitys.setItem(
                row_idx, 2,
                QTableWidgetItem(str(date))
            )

            # --- Сумма
            self.table_entitys.setItem(
                row_idx, 3,
                QTableWidgetItem(str(amount))
            )

            # --- Примечание
            self.table_entitys.setItem(
                row_idx, 4,
                QTableWidgetItem(note)
            )

        # скрываем колонку ID
        self.table_entitys.setColumnHidden(0, True)

        self.table_entitys.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )



class Edit_Acc(BaseWidget):

    edit_acc = pyqtSignal()

    def __init__(self, db, acc_id):
        super().__init__()
        uic.loadUi(resource_path("gui/edit_acc.ui"), self)
        center_window(self)

        self.db = db

        self.acc_id = acc_id

        temp  = self.db.get_accounts_byid(self.acc_id)
        acc_desc_id = temp['acc_desc_id'][0]
        temp = self.db.get_acc_desc_byid(int(acc_desc_id))

        self.name = temp['name'][0]

        # подключаем кнопку
        self.load_acc_desc()

        self.btn_account_edit.clicked.connect(self.edit_account)

        self.btn_account_edit_exit.clicked.connect(self.close)

        self.setFixedSize(self.size())

    def load_acc_desc(self):

        all_acc_desc = self.db.acc_descs()

        self.acc_desc_list_edit.clear()

        for acc_id, name, description in all_acc_desc:
            self.acc_desc_list_edit.addItem(name, acc_id)

    def edit_account(self):

        acc_desc_id = self.acc_desc_list_edit.currentData()

        if not acc_desc_id:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Поле с названием пустое. Добавление отменено"
            )
            return

        self.db.update_acc(id=self.acc_id, acc_desc_id=acc_desc_id)

        self.edit_acc.emit()
        self.close()

class Create_acc(BaseWindow):

    acc_added = pyqtSignal()

    def __init__(self, db, firm_id, check_id):
        super().__init__()
        uic.loadUi(resource_path("gui/create_acc.ui"), self)
        center_window(self)

        self.db = db
        self.firm_id = firm_id

        self.check_id = check_id

        self.load_acc_desc()


        # подключаем кнопку
        self.btn_account_create.clicked.connect(self.create_account)

        self.btn_account_create_back_checks.clicked.connect(self.back_account)

        self.open_checks = AccountWindow(self.db, self.firm_id, check_id)


        self.setFixedSize(self.size())

    def back_account(self):

        self.close()

    def create_account(self):

        acc_desc_id = self.acc_desc_list.currentData()

        if acc_desc_id is None:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Выберите счет из списка"
            )
            return

        new_id, created = self.db.get_or_create_account(
            check_id=self.check_id,
            acc_desc_id=acc_desc_id
        )

        if created:
            self.acc_added.emit()
            self.close()
        else:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Такой счет уже существует"
            )

    def load_acc_desc(self):

        all_acc_desc = self.db.acc_descs()

        self.acc_desc_list.clear()

        for acc_id, name, description in all_acc_desc:
            self.acc_desc_list.addItem(name, acc_id)

class AccountWindow(BaseWindow):

    def __init__(self, db, firm_id, check_id):
        super().__init__()
        uic.loadUi(resource_path("gui/account.ui"), self)
        center_window(self)

        self.db = db
        self.firm_id = firm_id
        self.check_id = check_id

        name = db.get_firm(self.firm_id)
        self.firm_name = name["name"]

        self.text_account_name_firm.setText(self.firm_name)

        temp = self.db.get_one_checks(self.check_id)

        self.period = temp["period"][0]

        self.text_account_checks_name.setText(self.period)

        self.load_accounts()
        # подключаем кнопку

        self.btn_new_account.clicked.connect(self.open_create_account)

        self.table_accounts.cellDoubleClicked.connect(self.open_data)

        self.btn_accounts_exit_to_checks.clicked.connect(self.open_checks)

        self.setFixedSize(self.size())


    def open_create_account(self):
        self.create_account_win = Create_acc(self.db, self.firm_id, self.check_id)
        self.create_account_win.acc_added.connect(self.load_accounts)
        self.create_account_win.show()

    def open_data(self, row, column):

        acc_id_item = self.table_accounts.item(row, 0)

        if acc_id_item:
            acc_id = int(acc_id_item.text())

            self.close()
            # тут откроешь окно проверок
            self.open_data_win = DataWindow(self.db, self.firm_id, self.check_id, acc_id)
            self.open_data_win.show()


    def open_checks(self):

        self.close()
        self.open = CheckWindow(firm_id= self.firm_id, db =self.db)
        self.open.show()

    def edit_account(self, acc_id):
        self.edit = Edit_Acc(self.db, acc_id)
        self.edit.edit_acc.connect(self.load_accounts)
        self.edit.show()

    def delete_acc(self, acc_id):
        reply = QMessageBox.question(
            self,
            "Удаление",
            "Удалить проверку и ВСЕ связанные данные?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return
        else:
            self.db.delete_accounts(acc_id)
            self.load_accounts()

    def load_accounts(self):

        accounts = self.db.get_accounts(self.check_id)

        self.table_accounts.setRowCount(len(accounts))
        self.table_accounts.setColumnCount(4)

        self.table_accounts.setHorizontalHeaderLabels([
            "", "Название", "", ""
        ])

        self.table_accounts.setColumnWidth(1, 470)
        self.table_accounts.setColumnWidth(2, 30)
        self.table_accounts.setColumnWidth(3, 30)

        for row_idx, (id, name) in enumerate(accounts):
            # --- ID (скрытый)
            self.table_accounts.setItem(
                row_idx, 0,
                QTableWidgetItem(str(id))
            )

            # --- название из account_desc
            self.table_accounts.setItem(
                row_idx, 1,
                QTableWidgetItem(name)
            )

            btn_account_edit = QPushButton()
            btn_account_edit.setIcon(
                QIcon(resource_path("gui/icons/edit.png"))
            )
            btn_account_edit.clicked.connect(
                lambda _, fid=id: self.edit_account(fid)
            )

            btn_account_del = QPushButton()
            btn_account_del.setIcon(
                QIcon(resource_path("gui/icons/trash.png"))
            )
            btn_account_del.clicked.connect(
                lambda _, fid=id: self.delete_acc(fid)
            )

            btn_account_edit.setFixedSize(30, 30)
            btn_account_del.setFixedSize(30, 30)

            btn_account_edit.setIconSize(QSize(30, 30))
            btn_account_del.setIconSize(QSize(30, 30))

            self.table_accounts.setCellWidget(
                row_idx, 2, btn_account_edit
            )
            self.table_accounts.setCellWidget(
                row_idx, 3, btn_account_del
            )

        self.table_accounts.setColumnHidden(0, True)

        self.table_accounts.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

class CheckWindow(BaseWindow):

    def __init__(self, db, firm_id):
        super().__init__()
        uic.loadUi(resource_path("gui/checks.ui"), self)
        center_window(self)

        self.db = db
        self.firm_id = firm_id


        name = db.get_firm(self.firm_id )
        self.name = name["name"]

        self.text_name_firm.setText(self.name)

        self.load_checks()
        # подключаем кнопку
        self.btn_new_checks.clicked.connect(self.open_create_cheks)

        self.table_checks.cellDoubleClicked.connect(self.open_account)

        self.btn_checks_exit_to_firm.clicked.connect(self.open_firm)

        self.setFixedSize(self.size())


    def open_account(self, row, column):
        check_id_item = self.table_checks.item(row, 0)

        if check_id_item:
            check_id = int(check_id_item.text())

            self.close()
            # тут откроешь окно проверок
            self.open_checks = AccountWindow(self.db, self.firm_id, check_id)
            self.open_checks.show()


    def open_firm(self):

        self.close()
        self.firm_window = FirmWindow(db =self.db)
        self.firm_window.show()

    def open_create_cheks(self):
        self.create_cheks = Add_Cheks(self.db, self.firm_id)
        self.create_cheks.checks_add.connect(self.load_checks)
        self.create_cheks.show()

    def edit_checks(self, check_id):
        self.edit = Edit_Checks(self.db, check_id)
        self.edit.check_edit.connect(self.load_checks)
        self.edit.show()

    def delete_cheks(self, check_id):
        reply = QMessageBox.question(
            self,
            "Удаление",
            "Удалить проверку и ВСЕ связанные данные?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return
        else:
            self.db.delete_checks(check_id)
            self.load_checks()


    def load_checks(self):


        checks = self.db.get_checks(self.firm_id)

        self.table_checks.setRowCount(len(checks))
        self.table_checks.setColumnCount(7)

        self.table_checks.setHorizontalHeaderLabels([
            "", "Период", "Уровень сущест.", "Дата создания", "Риск","", ""
        ])

        self.table_checks.setColumnWidth(1, 150)
        self.table_checks.setColumnWidth(2, 150)
        self.table_checks.setColumnWidth(3, 100)
        self.table_checks.setColumnWidth(4, 100)
        self.table_checks.setColumnWidth(5, 30)
        self.table_checks.setColumnWidth(6, 30)

        for row_idx, (id, period, materiality, created_at, risk) in enumerate(checks):
            # --- ID (скрытый)
            self.table_checks.setItem(
                row_idx, 0,
                QTableWidgetItem(str(id))
            )

            # --- Периорд
            self.table_checks.setItem(
                row_idx, 1,
                QTableWidgetItem(period)
            )

            # --- Уровень
            self.table_checks.setItem(
                row_idx, 2,
                QTableWidgetItem(str(materiality))
            )
            # --- Дата
            self.table_checks.setItem(
                row_idx, 3,
                QTableWidgetItem(str(created_at)[:10])
            )
            # --- Риск
            self.table_checks.setItem(
                row_idx, 4,
                QTableWidgetItem(str(risk)[:10])
            )

            btn_checks_edit = QPushButton()
            btn_checks_edit.setIcon(QIcon(resource_path("gui/icons/edit.png")))
            btn_checks_edit.clicked.connect(lambda _, fid=id: self.edit_checks(fid))

            btn_checks_del = QPushButton()
            btn_checks_del.setIcon(QIcon(resource_path("gui/icons/trash.png")))
            btn_checks_del.clicked.connect(lambda _, fid=id: self.delete_cheks(fid))

            btn_checks_edit.setFixedSize(30, 30)
            btn_checks_del.setFixedSize(30, 30)

            btn_checks_edit.setIconSize(QSize(30, 30))
            btn_checks_del.setIconSize(QSize(30, 30))


            self.table_checks.setCellWidget(row_idx, 5, btn_checks_edit)
            self.table_checks.setCellWidget(row_idx, 6, btn_checks_del)

        # 👉 скрываем колонку ID
        self.table_checks.setColumnHidden(0, True)

        self.table_checks.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

class AccountDescWindow(BaseWindow):

    def __init__(self, path="audit.db", db=None):
        super().__init__()
        uic.loadUi(resource_path("gui/account_desc.ui"), self)
        center_window(self)

        if db:
            self.db = db
        else:
            self.db = Database(path=path)
            self.db.init_db()


        self.load_accounts_desc()
        # подключаем кнопку

        self.btn_new_account_desc.clicked.connect(self.open_create_account_desc)

        self.btn_accounts_exit_to_main.clicked.connect(self.open_mainwindow)

        self.setFixedSize(self.size())

    def open_mainwindow(self):
        self.open_mainwindow = MainWindow()
        self.open_mainwindow.show()

        self.close()  # закрываем текущее окно

    def open_create_account_desc(self):
        self.create_account_desc = Create_acc_desc(self.db)
        self.create_account_desc.acc_desc_added.connect(self.load_accounts_desc)
        self.create_account_desc.show()


    def edit_acc_desc(self, acc_id):
        self.edit = Edit_Acc_desc(self.db, acc_id)
        self.edit.edit_acc.connect(self.load_accounts_desc)
        self.edit.show()

    def delete_acc_desc(self, acc_id):

        reply = QMessageBox.question(
            self,
            "Удаление",
            "Удалить счет/реестр?",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        answer = self.db.delete_acc_desc(acc_id)

        if not answer:
            QMessageBox.warning(
                self,
                "Удаление невозможно",
                "Этот счет/реестр уже используется в проверке "
                "и не может быть удалён."
            )
            return

        self.load_accounts_desc()

    def load_accounts_desc(self):

        accounts_desc = self.db.acc_descs()

        self.table_accounts_desc.setRowCount(len(accounts_desc))
        self.table_accounts_desc.setColumnCount(5)

        self.table_accounts_desc.setHorizontalHeaderLabels([
            "", "Название", "Описание", "", ""
        ])

        self.table_accounts_desc.setColumnWidth(1, 170)
        self.table_accounts_desc.setColumnWidth(2, 370)
        self.table_accounts_desc.setColumnWidth(3, 30)
        self.table_accounts_desc.setColumnWidth(4, 30)

        for row_idx, (id, name, description) in enumerate(accounts_desc):
            # --- ID (скрытый)
            self.table_accounts_desc.setItem(
                row_idx, 0,
                QTableWidgetItem(str(id))
            )

            # --- Название
            self.table_accounts_desc.setItem(
                row_idx, 1,
                QTableWidgetItem(name)
            )

            # --- Описание
            self.table_accounts_desc.setItem(
                row_idx, 2,
                QTableWidgetItem(description)
            )

            btn_acc_desc_edit = QPushButton()
            btn_acc_desc_edit.setIcon(
                QIcon(resource_path("gui/icons/edit.png"))
            )
            btn_acc_desc_edit.clicked.connect(
                lambda _, fid=id: self.edit_acc_desc(fid)
            )

            btn_acc_desc_del = QPushButton()
            btn_acc_desc_del.setIcon(
                QIcon(resource_path("gui/icons/trash.png"))
            )
            btn_acc_desc_del.clicked.connect(
                lambda _, fid=id: self.delete_acc_desc(fid)
            )

            btn_acc_desc_edit.setFixedSize(30, 30)
            btn_acc_desc_del.setFixedSize(30, 30)

            btn_acc_desc_edit.setIconSize(QSize(30, 30))
            btn_acc_desc_del.setIconSize(QSize(30, 30))

            self.table_accounts_desc.setColumnHidden(0, True)

            self.table_accounts_desc.setCellWidget(
                row_idx, 3, btn_acc_desc_edit
            )
            self.table_accounts_desc.setCellWidget(
                row_idx, 4, btn_acc_desc_del
            )


class Create_acc_desc(BaseWindow):

    acc_desc_added = pyqtSignal()

    def __init__(self, db):
        super().__init__()
        uic.loadUi(resource_path("gui/create_acc_desc.ui"), self)
        center_window(self)

        self.db = db

        # подключаем кнопку
        self.btn_account_desc_create.clicked.connect(self.create_account)

        self.btn_account_desc_create_back.clicked.connect(self.back_account)

        self.setFixedSize(self.size())

    def back_account(self):

        self.close()


    def create_account(self):
        new_acc_name = self.text_account_desc_name.text().strip()
        new_acc_desc = self.text_account_desc.toPlainText().strip()

        if not new_acc_name:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Поле с названием пустое. Добавление отменено"
            )
            return

        new_id, created= self.db.get_or_create_acc_desc(name=new_acc_name, description=new_acc_desc)

        if created:
            self.acc_desc_added.emit()
            self.close()
        else:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Такой счет уже существует"
            )



class Edit_Acc_desc(BaseWidget):

    edit_acc = pyqtSignal()

    def __init__(self, db, acc_id):
        super().__init__()
        uic.loadUi(resource_path("gui/edit_acc_desc.ui"), self)
        center_window(self)

        self.db = db

        self.acc_id = acc_id

        temp  = self.db.get_acc_desc_byid(self.acc_id)
        name = temp['name'][0]
        desc = temp['description'][0]
        # подключаем кнопку
        self.text_account_desc_name_edit.setText(name)
        self.text_account_desc_edit.setPlainText(desc)

        self.btn_account_desc_edit.clicked.connect(self.edit_account)

        self.btn_account_desc_edit_back.clicked.connect(self.close)

        self.setFixedSize(self.size())


    def edit_account(self):
        new_acc_name = self.text_account_desc_name_edit.text().strip()
        new_acc_desc = self.text_account_desc_edit.toPlainText().strip()

        if not new_acc_name:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Поле с названием пустое. Добавление отменено"
            )
            return

        self.db.update_acc_desc(id=self.acc_id, name=new_acc_name, description=new_acc_desc)

        self.edit_acc.emit()
        self.close()



class Create_Firm(BaseWindow):

    firm_added = pyqtSignal()

    def __init__(self, db):
        super().__init__()
        uic.loadUi(resource_path("gui/create_firm.ui"), self)
        center_window(self)

        self.db = db
        # подключаем кнопку
        self.btn_create_firm.clicked.connect(self.create_firm)

        self.btn_exit_create_firm.clicked.connect(self.close)

        self.setFixedSize(self.size())

    def create_firm(self):
        new_firm = self.text_new_firm.text().strip()

        if not new_firm:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Поле с названием пустое. Добавление отменено"
            )
            return

        firm_id, created = self.db.get_or_create_firm(new_firm)

        if created:
            self.firm_added.emit()
            self.close()
        else:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Такая фирма уже существует"
            )



class FirmWindow(BaseWindow):
    def __init__(self, path="audit.db", db=None):
        super().__init__()
        uic.loadUi(resource_path("gui/firm.ui"), self)
        center_window(self)

        if db:
            self.db = db
        else:
            self.db = Database(path=path)
            self.db.init_db()


        self.load_firms()
        self.table_firms.cellDoubleClicked.connect(self.open_firm)
        self.btn_new_firm.clicked.connect(self.open_create_firm_window)

        self.btn_return_mainwindow.clicked.connect(self.return_mainwindow)

        # self.btn_search_firm.clicked.connect(self.search_firm)
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_search)

        # реакция на ввод
        self.text_search_firm.textChanged.connect(self.on_search_text_changed)
        self.btn_search_reset.clicked.connect(self.reset_search)

        self.setFixedSize(self.size())

    def return_mainwindow(self):
        self.open_mainwindow = MainWindow()
        self.open_mainwindow.show()

        self.close()  # закрываем текущее окно

    def reset_search(self):
        self.text_search_firm.clear()

    def on_search_text_changed(self):
        # перезапускаем таймер при каждом вводе
        self.search_timer.start(300)  # 300 мс

    def perform_search(self):
        query = self.text_search_firm.text().strip()
        self.load_firms(query=query)


    def load_firms(self, query=""):

        if query == "":
            firms = self.db.get_firms()
        else:
            firms = self.db.search_firms(query)

        self.table_firms.setRowCount(len(firms))
        self.table_firms.setColumnCount(4)

        self.table_firms.setHorizontalHeaderLabels([
            "", "Название", "", ""
        ])

        self.table_firms.setColumnWidth(1, 470)
        self.table_firms.setColumnWidth(2, 30)
        self.table_firms.setColumnWidth(3, 30)

        for row_idx, (firm_id, name) in enumerate(firms):
            # --- ID (скрытый)
            self.table_firms.setItem(
                row_idx, 0,
                QTableWidgetItem(str(firm_id))
            )

            # --- Название
            self.table_firms.setItem(
                row_idx, 1,
                QTableWidgetItem(name)
            )


            btn_edit = QPushButton()
            btn_edit.setIcon(QIcon(resource_path("gui/icons/edit.png")))

            btn_edit.clicked.connect(lambda _, fid=firm_id: self.edit_firm(fid))

            btn_del = QPushButton()
            btn_del.setIcon(QIcon(resource_path("gui/icons/trash.png")))
            btn_del.clicked.connect(lambda _, fid=firm_id: self.delete_firm(fid))

            btn_edit.setFixedSize(30, 30)
            btn_del.setFixedSize(30, 30)

            btn_edit.setIconSize(QSize(30, 30))
            btn_del.setIconSize(QSize(30, 30))


            self.table_firms.setCellWidget(row_idx, 2, btn_edit)
            self.table_firms.setCellWidget(row_idx, 3, btn_del)

        # 👉 скрываем колонку ID
        self.table_firms.setColumnHidden(0, True)

        self.table_firms.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

    def open_firm(self, row, column):
        firm_id_item = self.table_firms.item(row, 0)

        if firm_id_item:
            firm_id = int(firm_id_item.text())

            self.close()
            # тут откроешь окно проверок
            self.open_checks = CheckWindow(self.db, firm_id)
            self.open_checks.show()


    def edit_firm(self, firm_id):
        self.create_firm = Edit_Firm(self.db, firm_id)
        self.create_firm.firm_edit.connect(self.load_firms)
        self.create_firm.show()

    def delete_firm(self, firm_id):
        reply = QMessageBox.question(
            self,
            "Удаление",
            "Удалить фирму и ВСЕ связанные данные?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return
        else:
            self.db.delete_firm(firm_id)
            self.load_firms()



    def open_create_firm_window(self):
        self.create_firm = Create_Firm(self.db)
        self.create_firm.firm_added.connect(self.load_firms)
        self.create_firm.show()





if __name__ == "__main__":
    app = QApplication(sys.argv)

    app.setStyleSheet(qdarkstyle.load_stylesheet())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())