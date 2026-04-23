import sys
import cv2
import numpy as np
import csv
import time
import math

from PyQt5.QtCore import QThread, pyqtSignal

from mediapipe.python.solutions import pose as mp_pose
from mediapipe.python.solutions import drawing_utils as mp_drawing


class VideoThread(QThread):
    # Сигнал передает: кадр, текст статуса, HP, режим разминки, таймер разминки, ошибку калибровки
    update_ui_signal = pyqtSignal(np.ndarray, str, float, bool, int, bool)

    def __init__(self):
        super().__init__()
        self.running = True
        self.is_calibrated = False

        # Базовые параметры
        self.baseline_y = 0.0
        self.baseline_z = 0.0
        self.Z_THRESHOLD = 0.04
        self.Y_THRESHOLD = 0.025
        self.MAX_TILT = 0.055
        self.HAND_FACE_DIST = 0.12

        # Игровая механика
        self.MAX_HP = 100.0
        self.current_hp = self.MAX_HP
        self.is_workout_mode = False
        self.workout_start_time = 0
        self.last_workout_time = time.time()
        self.last_hp_update = time.time()

        self.HP_LOSS_RATE = 15.0
        self.HP_REGEN_RATE = 5.0

        self.WORKOUT_INTERVAL = 1200
        self.WORKOUT_DURATION = 20

        # Плавная быстрая калибровка
        self.is_calibrating = False
        self.calib_start_time = 0
        self.calib_duration = 0.8
        self.calib_y_buffer = []
        self.calib_z_buffer = []

        # Логирование (Dataset для ML)
        self.csv_filename = "posture_dataset.csv"
        self.LOG_INTERVAL = 1.0
        self.last_log_time = time.time()
        self._init_csv()

    def _init_csv(self):
        with open(self.csv_filename, mode='a', newline='') as f:
            if f.tell() == 0:
                writer = csv.writer(f)
                writer.writerow(['ts', 'n_y', 'n_z', 'sh_y', 'sh_z', 'dy', 'dz', 'status', 'hp'])

    def run(self):
        pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

        if sys.platform.startswith('win'):
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(0)

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.last_hp_update = time.time()

        while self.running and cap.isOpened():
            ret, frame = cap.read()
            if not ret: break

            now = time.time()
            dt = now - self.last_hp_update
            self.last_hp_update = now

            frame = cv2.flip(frame, 1)
            frame = cv2.resize(frame, (480, 360))
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = pose.process(img)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

            status = "ОЖИДАНИЕ"
            calib_err = False
            w_timer = 0

            if res.pose_landmarks:
                lm = res.pose_landmarks.landmark
                nose = lm[0]
                eye_l, eye_r = lm[1], lm[4]
                sh_l, sh_r = lm[11], lm[12]
                el_l, el_r = lm[13], lm[14]
                wr_l, wr_r = lm[15], lm[16]

                shoulder_tilt = abs(sh_l.y - sh_r.y)
                head_tilt = abs(eye_l.y - eye_r.y)
                self.is_ready = (shoulder_tilt < self.MAX_TILT) and (head_tilt < self.MAX_TILT)

                sh_y = (sh_l.y + sh_r.y) / 2
                sh_z = (sh_l.z + sh_r.z) / 2
                dy = sh_y - nose.y
                dz = nose.z - sh_z

                mp_drawing.draw_landmarks(img, res.pose_landmarks, mp_pose.POSE_CONNECTIONS)

                if self.is_calibrating:
                    if not self.is_ready:
                        calib_err = True
                        status = "ВЫРОВНЯЙТЕСЬ!"
                        self.calib_start_time = now
                        self.calib_y_buffer.clear()
                        self.calib_z_buffer.clear()
                    else:
                        calib_err = False
                        time_left = max(0.0, round(self.calib_duration - (now - self.calib_start_time), 1))
                        status = f"КАЛИБРОВКА... {time_left}с"
                        self.calib_y_buffer.append(dy)
                        self.calib_z_buffer.append(dz)

                        if now - self.calib_start_time >= self.calib_duration:
                            if self.calib_y_buffer:
                                self.baseline_y = float(np.median(self.calib_y_buffer))
                                self.baseline_z = float(np.median(self.calib_z_buffer))
                            self.is_calibrated = True
                            self.is_calibrating = False
                            self.current_hp = self.MAX_HP
                            self.last_workout_time = now

                elif not self.is_workout_mode and (now - self.last_workout_time > self.WORKOUT_INTERVAL):
                    if self.is_calibrated:
                        self.is_workout_mode = True
                        self.workout_start_time = now

                elif self.is_workout_mode:
                    elapsed = int(now - self.workout_start_time)
                    w_timer = self.WORKOUT_DURATION - elapsed
                    status = "РАЗМИНКА!"
                    if dy > self.baseline_y * 1.15:
                        self.current_hp = min(120.0, self.current_hp + self.HP_REGEN_RATE * 2 * dt)
                    if w_timer <= 0:
                        self.is_workout_mode = False
                        self.last_workout_time = now
                        self.current_hp = self.MAX_HP

                elif self.is_calibrated:
                    bad_z = dz < (self.baseline_z - self.Z_THRESHOLD)
                    bad_y = dy < (self.baseline_y - self.Y_THRESHOLD)
                    head_drop = dy < (self.baseline_y * 0.75)

                    arms_up = (el_l.y < sh_l.y) or (el_r.y < sh_r.y)

                    dist_l = math.hypot(wr_l.x - nose.x, wr_l.y - nose.y)
                    dist_r = math.hypot(wr_r.x - nose.x, wr_r.y - nose.y)
                    hand_on_face = (dist_l < self.HAND_FACE_DIST) or (dist_r < self.HAND_FACE_DIST)

                    if hand_on_face:
                        status = "РУКА У ЛИЦА!"
                        self.current_hp = max(0.0, self.current_hp - (self.HP_LOSS_RATE * 1.5) * dt)
                    elif bad_z:
                        status = "СУТУЛОСТЬ!"
                        self.current_hp = max(0.0, self.current_hp - self.HP_LOSS_RATE * dt)
                    elif arms_up:
                        status = "ПОТЯГУШКИ!"
                        self.current_hp = min(self.MAX_HP, self.current_hp + self.HP_REGEN_RATE * 2 * dt)
                    elif bad_y or head_drop:
                        status = "НИЗКО!" if head_drop else "СУТУЛОСТЬ!"
                        self.current_hp = max(0.0, self.current_hp - self.HP_LOSS_RATE * dt)
                    else:
                        status = "ОТЛИЧНО"
                        self.current_hp = min(self.MAX_HP, self.current_hp + self.HP_REGEN_RATE * dt)

                    if now - self.last_log_time >= self.LOG_INTERVAL:
                        with open(self.csv_filename, mode='a', newline='') as f:
                            status_code = 0
                            if "СУТУЛОСТЬ" in status:
                                status_code = 1
                            elif "НИЗКО" in status:
                                status_code = 2
                            elif "РУКА У ЛИЦА" in status:
                                status_code = 3
                            elif "ПОТЯГУШКИ" in status:
                                status_code = 4

                            csv.writer(f).writerow([round(now, 1), round(nose.y, 3), round(nose.z, 3),
                                                    round(sh_y, 3), round(sh_z, 3), round(dy, 3), round(dz, 3),
                                                    status_code, int(self.current_hp)])
                        self.last_log_time = now
                else:
                    status = "НУЖНА КАЛИБРОВКА"
                    if not self.is_ready:
                        calib_err = True

            self.update_ui_signal.emit(img, status, self.current_hp, self.is_workout_mode, w_timer, calib_err)

        cap.release()

    def calibrate(self):
        self.is_calibrating = True
        self.is_calibrated = False
        self.calib_start_time = time.time()
        self.calib_y_buffer.clear()
        self.calib_z_buffer.clear()

    def stop(self):
        self.running = False
        self.wait()