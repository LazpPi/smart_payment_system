import nfc
import re
import time
import csv
import os
import json
import subprocess
import serial
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# === Firebase 初期化 ===
try:
    cred = credentials.Certificate("../firebase-key.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebaseへの接続が完了しました！")
except Exception as e:
    print(f"⚠️ Firebaseの初期化に失敗しました: {e}")
    db = None

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

def log_to_firestore(student_id, item_name):
    if db is None:
        return
    try:
        now = datetime.now(timezone.utc)
        # history コレクションに新しいドキュメントを追加
        db.collection("history").add({
            "timestamp": now,
            "student_id": student_id,
            "item": item_name
        })
        print("☁️ Firebaseへ履歴を送信しました。")
    except Exception as e:
        print(f"⚠️ Firebaseへの送信エラー: {e}")

def check_serial():
    global current_amount, last_coin_time
    
    # 30秒間放置によるタイムアウト処理
    if current_amount > 0:
        elapsed_time = time.time() - last_coin_time
        if elapsed_time >= 30.0:
            print("\n⏳ 30秒経過。金額をリセットします。")
            play_sound(WAV_RESET)
            if ser and ser.is_open:
                ser.write(b"TIMEOUT\n")  # M5StickCにTIMEOUTを表示させる
            current_amount = 0
            print("\n次の学生証をタッチしてください...")

    # M5StickCからのコイン投入データを受信
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
                        log_to_firestore(student_id, f"サブスク {count}杯目(満了)")
                    else:
                        save_subscribers(subscribers)
                        play_sound(sub_wav)
                        log_to_csv(student_id, f"サブスク {count}杯目")
                        log_to_firestore(student_id, f"サブスク {count}杯目")
                    
                    # M5StickCに「Sub: 〇」を表示させる
                    if ser and ser.is_open:
                        ser.write(f"SUB:{count}\n".encode())
                else:
                    print("⚠️ サブスク未登録です。300円を投入してからタッチしてください。")
                    play_sound(WAV_PAY)
                    if ser and ser.is_open:
                        ser.write(b"RETRY\n")

            elif current_amount == 300 and student_id not in subscribers:
                print(f"🎊 新規サブスク登録完了！")
                subscribers[student_id] = {"used_count": 1}
                save_subscribers(subscribers)
                play_sound("sound/1.wav")
                log_to_csv(student_id, "新規登録(300円)・1杯目")
                log_to_firestore(student_id, "新規登録(300円)・1杯目")
                
                if ser and ser.is_open:
                    ser.write(b"SUB:1\n") # 登録時も1杯目と表示
                current_amount = 0

            else:
                print(f"🪙 通常決済成功: {current_amount}円")
                log_to_csv(student_id, f"通常決済({current_amount}円)")
                log_to_firestore(student_id, f"通常決済({current_amount}円)")
                play_sound(WAV_SUCCESS)
                
                if ser and ser.is_open:
                    ser.write(b"NORMAL\n") # 「Thank You!」を表示
                current_amount = 0

        else:
            print("⚠️ 学生番号が見つかりませんでした。")
            play_sound(WAV_RETRY)
            if ser and ser.is_open:
                ser.write(b"RETRY\n")

    except Exception as e:
        print("⚠️ 読み取りエラーが発生しました。")
        play_sound(WAV_RETRY)
        if ser and ser.is_open:
            ser.write(b"RETRY\n")

    return True

# === メイン処理 ===
print("システム起動。M5StickCと接続しています...")
try:
    ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=0.1)
    print("✅ M5StickCと通信準備完了！")
except Exception as e:
    print(f"⚠️ エラー: シリアルポート({SERIAL_PORT})が開けません。")

print("========================================")
print("学生証をタッチして決済を開始してください")
print("========================================")

try:
    with nfc.ContactlessFrontend('usb') as clf:
        while True:
            result = clf.connect(rdwr={'on-connect': on_connect}, terminate=check_serial)
            if result is False: break
            time.sleep(1.5)
            print("\n次の学生証をタッチしてください...")
except Exception as e:
    print(f"システムエラーが発生しました: {e}")
finally:
    if ser and ser.is_open: ser.close()