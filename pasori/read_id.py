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
WAV_SUCCESS = "sound/thank_you.wav"  # 通常決済用
WAV_RETRY = "sound/retouch.wav"      # エラー時用
WAV_RESET = "sound/reset.wav"        # タイムアウト時用
WAV_PAY = "sound/pay.wav"            # 未登録者の0円タッチ用

# M5StickCとの通信設定 (※ご自身の環境に合わせて変更してください)
SERIAL_PORT = '/dev/ttyACM0'
SERIAL_BAUD = 115200

# グローバル変数
current_amount = 0
last_coin_time = 0
ser = None

def play_sound(file_path):
    if os.path.exists(file_path):
        subprocess.Popen(["aplay", "-D", "plughw:2,0", "-q", file_path], stderr=subprocess.DEVNULL)
    else:
        print(f"⚠️ 音声ファイルが見つかりません: {file_path}")

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
            print("\n⏳ 30秒間タッチされなかったため、投入金額をリセットします。")
            play_sound(WAV_RESET)
            if ser and ser.is_open:
                ser.write(b"RESET\n")
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
                    
                    # 再生する音声ファイル名を杯数から動的に生成 (例: sound/3.wav)
                    sub_wav = f"sound/{count}.wav"
                    
                    # === 10杯目の自動解除処理 ===
                    if count >= 10:
                        print(f"☕️ サブスク決済成功: {count}杯目")
                        print("🎊 10杯目に到達しました！サブスクリプションを終了（自動解除）します。")
                        
                        del subscribers[student_id]
                        save_subscribers(subscribers)
                        
                        play_sound(sub_wav)  # 10.wav を再生
                        log_to_csv(student_id, f"コーヒー（サブスク {count}杯目・満了）")
                    else:
                        save_subscribers(subscribers)
                        print(f"☕️ サブスク決済成功: {count}杯目")
                        play_sound(sub_wav)  # 1.wav〜9.wav を再生
                        log_to_csv(student_id, f"コーヒー（サブスク {count}杯目）")
                else:
                    print("⚠️ サブスク未登録です。300円を投入してからタッチしてください。")
                    play_sound(WAV_PAY)  # retouch.wavからpay.wavに変更

            elif current_amount == 300 and student_id not in subscribers:
                # === 新規登録処理（1杯目としてカウント） ===
                print(f"🎊 新規サブスク登録完了！ようこそ、【 {student_id} 】さん！")
                
                subscribers[student_id] = {"used_count": 1}
                save_subscribers(subscribers)
                
                play_sound("sound/1.wav")  # 登録時も1杯目なので 1.wav を再生
                log_to_csv(student_id, "サブスク新規登録(300円)・1杯目")
                
                if ser and ser.is_open:
                    ser.write(b"RESET\n")
                current_amount = 0

            else:
                print(f"🪙 通常決済成功: {current_amount}円分を購入しました")
                log_to_csv(student_id, f"通常決済({current_amount}円)")
                play_sound(WAV_SUCCESS)  # 通常の現金決済は thank_you.wav
                
                if ser and ser.is_open:
                    ser.write(b"RESET\n")
                current_amount = 0

        else:
            print("⚠️ 学生番号が見つかりませんでした。もう一度正しくタッチしてください。")
            play_sound(WAV_RETRY)

    except Exception as e:
        print("⚠️ 読み取りエラーが発生しました。もう一度しっかりタッチしてください。")
        play_sound(WAV_RETRY)

    return True

# === メイン処理 ===
print("システム起動。M5StickCと接続しています...")
try:
    ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=0.1)
    print("✅ M5StickCとの通信準備完了！")
except Exception as e:
    print(f"⚠️ エラー: シリアルポート({SERIAL_PORT})が開けません。")

print("========================================")
print("学生証をタッチして決済を開始してください")
print("========================================")

try:
    with nfc.ContactlessFrontend('usb') as clf:
        while True:
            result = clf.connect(rdwr={'on-connect': on_connect}, terminate=check_serial)
            
            if result is False:
                print("\n\n🛑 管理者操作により、システムを安全に終了しました。")
                break
            
            time.sleep(1.5)
            print("\n次の学生証をタッチしてください...")

except Exception as e:
    print(f"システムエラーが発生しました: {e}")
finally:
    if ser and ser.is_open:
        ser.close()