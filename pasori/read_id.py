import nfc
import re
import time
import csv
import os
import json
import subprocess
import serial
from datetime import datetime

# === 基本設定 ===
STUDENT_ID_PATTERN = re.compile(r'[A-Z]{2}\d{5}')
CSV_FILE = "visit_history.csv"
SUBSCRIBERS_FILE = "subscribers.json"

# 音声ファイルのパス
WAV_SUCCESS = "sound/thank_you.wav"
WAV_RETRY = "sound/retouch.wav"
WAV_RESET = "sound/reset.wav"
WAV_PAY = "sound/pay.wav"

# M5StickCとの通信設定
SERIAL_PORT = '/dev/ttyACM0'
SERIAL_BAUD = 115200

# グローバル変数
current_amount = 0
last_coin_time = 0
ser = None

def play_sound(file_path):
    if os.path.exists(file_path):
        subprocess.Popen(["aplay", "-D", "plughw:2,0", "-q", file_path], stderr=subprocess.DEVNULL)

def load_subscribers():
    if os.path.exists(SUBSCRIBERS_FILE):
        with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_subscribers(data):
    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def log_to_csv(student_id, item_name):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "StudentID", "Item"])
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([now, student_id, item_name])

def check_serial():
    global current_amount, last_coin_time
    
    if current_amount > 0:
        elapsed_time = time.time() - last_coin_time
        if elapsed_time >= 30.0:
            print("\n⏳ 30秒経過。金額をリセットします。")
            play_sound(WAV_RESET)
            if ser and ser.is_open:
                ser.write(b"TIMEOUT\n")  # TIMEOUTコマンドを送信
            current_amount = 0
            print("\n次の学生証をタッチしてください...")

    if ser and ser.in_waiting > 0:
        try:
            lines = ser.readlines()
            last_line = lines[-1].decode('utf-8', errors='ignore').strip()
            
            if last_line.isdigit():
                new_amount = int(last_line)
                if new_amount != current_amount:
                    current_amount = new_amount
                    last_coin_time = time.time()
                    print(f"💰 現在の投入合計: {current_amount}円")
        except Exception as e:
            pass
    return False

def on_connect(tag):
    global current_amount
    print("\nカード情報を処理しています...")
    
    try:
        data = "\n".join(tag.dump())
        match = STUDENT_ID_PATTERN.search(data)
        
        if match:
            student_id = match.group()
            print(f"🎉 読み取り成功！ 学生番号: 【 {student_id} 】")
            subscribers = load_subscribers()

            if current_amount == 0:
                if student_id in subscribers:
                    subscribers[student_id]["used_count"] += 1
                    count = subscribers[student_id]["used_count"]
                    sub_wav = f"sound/{count}.wav"
                    
                    if count >= 10:
                        print(f"🎊 10杯目に到達！サブスク自動解除。")
                        del subscribers[student_id]
                        save_subscribers(subscribers)
                        play_sound(sub_wav)
                        log_to_csv(student_id, f"サブスク {count}杯目(満了)")
                    else:
                        save_subscribers(subscribers)
                        play_sound(sub_wav)
                        log_to_csv(student_id, f"サブスク {count}杯目")
                    
                    # 画面に「〇杯目」と表示させる
                    if ser and ser.is_open:
                        ser.write(f"SUB:{count}\n".encode())
                else:
                    play_sound(WAV_PAY)
                    # 未登録時は「再度カードタッチ」とは少し意味が違うため、今は画面変更なし（またはRETRY）
                    if ser and ser.is_open:
                        ser.write(b"RETRY\n")

            elif current_amount == 300 and student_id not in subscribers:
                print(f"🎊 新規サブスク登録完了！")
                subscribers[student_id] = {"used_count": 1}
                save_subscribers(subscribers)
                play_sound("sound/1.wav")
                log_to_csv(student_id, "新規登録(300円)・1杯目")
                
                if ser and ser.is_open:
                    ser.write(b"SUB:1\n") # 登録時も1杯目と表示
                current_amount = 0

            else:
                print(f"🪙 通常決済成功: {current_amount}円")
                log_to_csv(student_id, f"通常決済({current_amount}円)")
                play_sound(WAV_SUCCESS)
                
                if ser and ser.is_open:
                    ser.write(b"NORMAL\n") # 通常決済のメッセージ表示
                current_amount = 0

        else:
            print("⚠️ 学生番号なし")
            play_sound(WAV_RETRY)
            if ser and ser.is_open:
                ser.write(b"RETRY\n") # 再タッチを促すメッセージ

    except Exception as e:
        print("⚠️ 読み取りエラー")
        play_sound(WAV_RETRY)
        if ser and ser.is_open:
            ser.write(b"RETRY\n")

    return True

# === メイン処理 ===
try:
    ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=0.1)
    print("✅ M5StickCと接続完了")
except Exception as e:
    print(f"⚠️ エラー: シリアルポート({SERIAL_PORT})が開けません。")

try:
    with nfc.ContactlessFrontend('usb') as clf:
        while True:
            result = clf.connect(rdwr={'on-connect': on_connect}, terminate=check_serial)
            if result is False: break
            time.sleep(1.5)
except Exception as e:
    print(f"システムエラー: {e}")
finally:
    if ser and ser.is_open: ser.close()