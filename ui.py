import cv2
from PyQt5.QtWidgets import (QWidget, QLabel, QVBoxLayout,
                             QHBoxLayout, QPushButton, QProgressBar, QFrame,
                             QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap, QColor

# Импортируем вычислительное ядро из соседнего файла engine.py
from engine import VideoThread


class PostureApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ErgoVision - Предиктивная система контроля осанки")
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.resize(950, 580)
        self.init_ui()

        self.thread = VideoThread()
        self.thread.update_ui_signal.connect(self.refresh)
        self.thread.start()

    def init_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #0B0F19; 
                color: #E5E7EB;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel#Header {
                font-size: 28px;
                font-weight: 900;
                color: #F3E8FF; 
                letter-spacing: 1px;
            }
            QLabel#SubHeader {
                font-size: 14px;
                color: #9CA3AF;
            }
            QPushButton {
                background-color: #3B82F6; 
                color: white;
                border-radius: 8px;
                font-weight: bold;
                padding: 14px 20px;
                font-size: 15px;
            }
            QPushButton:hover { background-color: #2563EB; }
            QPushButton:pressed { background-color: #1D4ED8; }
            QProgressBar {
                border: none;
                border-radius: 8px;
                text-align: center;
                background-color: #1F2937;
                color: #ffffff;
                font-weight: bold;
                height: 28px;
            }
            QFrame#Card {
                background-color: #111827; 
                border: 1px solid #1F2937;
                border-radius: 12px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(20)

        # 1. Шапка (Header)
        header_layout = QHBoxLayout()
        title = QLabel("ErgoVision")
        title.setObjectName("Header")

        # Эффект неонового свечения
        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(25)
        glow.setColor(QColor("#A855F7"))
        glow.setOffset(0, 0)
        title.setGraphicsEffect(glow)

        subtitle = QLabel("Предиктивная система геймифицированного контроля осанки (MVP)")
        subtitle.setObjectName("SubHeader")

        header_vbox = QVBoxLayout()
        header_vbox.addWidget(title)
        header_vbox.addWidget(subtitle)
        header_layout.addLayout(header_vbox)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # 2. Основной контент
        content_layout = QHBoxLayout()
        content_layout.setSpacing(25)

        # Левая колонка
        left_col = QVBoxLayout()
        self.vid_lbl = QLabel()
        self.vid_lbl.setFixedSize(480, 360)
        self.vid_lbl.setStyleSheet("border: 2px solid #1F2937; border-radius: 12px; background-color: #111827;")
        self.vid_lbl.setAlignment(Qt.AlignCenter)
        left_col.addWidget(self.vid_lbl)

        self.btn_c = QPushButton("⚡ КАЛИБРОВАТЬ ЭТАЛОН (0.8с)")
        self.btn_c.clicked.connect(self.do_cal)
        left_col.addWidget(self.btn_c)

        left_col.addStretch()
        content_layout.addLayout(left_col)

        # Правая колонка
        right_col = QVBoxLayout()
        right_col.setSpacing(15)

        status_card = QFrame()
        status_card.setObjectName("Card")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(20, 20, 20, 20)

        lbl_stat_title = QLabel("ТЕКУЩИЕ ПОКАЗАТЕЛИ:")
        lbl_stat_title.setStyleSheet("color: #9CA3AF; font-size: 12px; font-weight: bold;")
        status_layout.addWidget(lbl_stat_title)

        self.stat_lbl = QLabel("ЗАПУСК...")
        self.stat_lbl.setStyleSheet("font-size: 34px; font-weight: 900; color: #3B82F6;")
        self.stat_lbl.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.stat_lbl)
        right_col.addWidget(status_card)

        hp_card = QFrame()
        hp_card.setObjectName("Card")
        hp_layout = QVBoxLayout(hp_card)
        hp_layout.setContentsMargins(20, 20, 20, 20)

        lbl_hp_title = QLabel("УРОВЕНЬ ЗДОРОВЬЯ (HP):")
        lbl_hp_title.setStyleSheet("color: #9CA3AF; font-size: 12px; font-weight: bold;")
        hp_layout.addWidget(lbl_hp_title)

        self.hp = QProgressBar()
        hp_layout.addWidget(self.hp)
        right_col.addWidget(hp_card)

        self.quest_box = QFrame()
        self.quest_box.setObjectName("Card")
        q_lay = QVBoxLayout(self.quest_box)
        q_lay.setContentsMargins(20, 20, 20, 20)

        self.q_title = QLabel("ИГРОВАЯ СЕССИЯ")
        self.q_title.setStyleSheet("color: #8B5CF6; font-weight: bold; font-size: 16px;")
        self.q_desc = QLabel("Ожидание активации алгоритмов компьютерного зрения...")
        self.q_desc.setStyleSheet("font-size: 14px; color: #D1D5DB;")
        self.q_desc.setWordWrap(True)

        q_lay.addWidget(self.q_title)
        q_lay.addWidget(self.q_desc)
        right_col.addWidget(self.quest_box)

        self.err_lbl = QLabel("")
        self.err_lbl.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 14px;")
        self.err_lbl.setAlignment(Qt.AlignCenter)
        right_col.addWidget(self.err_lbl)

        right_col.addStretch()
        content_layout.addLayout(right_col)
        main_layout.addLayout(content_layout)

    def do_cal(self):
        self.thread.calibrate()

    def refresh(self, frame, status, hp, is_work, timer, err):
        h, w, ch = frame.shape
        q_img = QImage(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).data, w, h, ch * w, QImage.Format_RGB888)
        self.vid_lbl.setPixmap(QPixmap.fromImage(q_img))

        self.stat_lbl.setText(status)
        self.hp.setValue(int(hp))

        color = "#10B981" if hp > 60 else "#F59E0B" if hp > 30 else "#EF4444"
        self.hp.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; border-radius: 8px; }}")

        if is_work:
            self.stat_lbl.setStyleSheet("color: #F59E0B; font-size: 34px; font-weight: 900;")
            self.q_title.setText("🔥 КВЕСТ: РАЗМИНКА ПОЯСНИЦЫ!")
            self.q_title.setStyleSheet("color: #F59E0B; font-weight: bold; font-size: 16px;")
            self.q_desc.setText(
                f"Откиньтесь назад или потянитесь вверх!\\nНаграда: Ускоренное восстановление HP.\\nОсталось секунд: {timer}")
        else:
            s_color = "#10B981" if ("ОТЛИЧНО" in status or "ПОТЯГУШКИ" in status) else "#EF4444"
            self.stat_lbl.setStyleSheet(f"color: {s_color}; font-size: 34px; font-weight: 900;")
            self.q_title.setText("АКТИВНЫЙ МОНИТОРИНГ")
            self.q_title.setStyleSheet("color: #8B5CF6; font-weight: bold; font-size: 16px;")
            self.q_desc.setText("Держите спину ровно, чтобы копить здоровье. Если устали — сделайте потягушки руками.")

        self.err_lbl.setText("СЯДЬТЕ РОВНО И СМОТРИТЕ В КАМЕРУ ДЛЯ КАЛИБРОВКИ!" if err else "")

    def closeEvent(self, event):
        self.thread.stop()
        event.accept()