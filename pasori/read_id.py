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
WAV_FILE = "thank_you.wav"

# M5StickCとの通信設定 (※環境によって /dev/ttyUSB0 や /dev/ttyACM0 に変わります)
SERIAL_PORT = '/dev/ttyACM0'
SERIAL_BAUD = 115200

# グローバル変数（現在の投入金額を保持）
current_amount = 0
ser = None

def play_sound(file_path):
    if os.path.exists(file_path):
        subprocess.Popen(["aplay", "-D", "plughw:2,0", "-q", file_path], stderr=subprocess.DEVNULL)
    else:
        print("⚠️ 音声ファイルが見つかりません")

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
    """カード待ち受け中に0.1秒ごとに呼ばれ、M5Stickから金額データを受信する"""
    global current_amount
    if ser and ser.in_waiting > 0:
        try:
            # 溜まっているデータを全て読み取り、最後の行を取得
            lines = ser.readlines()
            last_line = lines[-1].decode('utf-8', errors='ignore').strip()
            
            # 受信データが数字であれば金額を更新
            if last_line.isdigit():
                current_amount = int(last_line)
                print(f"💰 現在の投入合計: {current_amount}円")
        except Exception as e:
            pass
    # Falseを返すことで、カードの待ち受け(clf.connect)を継続させる
    return False

def on_connect(tag):
    global current_amount
    print("\nカード情報を処理しています...")
    data = "\n".join(tag.dump())
    match = STUDENT_ID_PATTERN.search(data)
    
    if match:
        student_id = match.group()
        print(f"🎉 読み取り成功！ 学生番号: 【 {student_id} 】")

        subscribers = load_subscribers()

        # === 決済ルールの判定（金額に応じた分岐） ===
        if current_amount == 0:
            if student_id in subscribers:
                # サブスク利用処理
                subscribers[student_id]["used_count"] += 1
                save_subscribers(subscribers)
                count = subscribers[student_id]["used_count"]
                
                print(f"☕️ サブスク決済成功: {count}杯目")
                play_sound(WAV_FILE)
                log_to_csv(student_id, f"コーヒー（サブスク {count}杯目）")
            else:
                # サブスク未登録者が0円でタッチした場合
                print("⚠️ サブスク未登録です。お金を投入してからタッチしてください。")
                # 将来ここにエラー音再生を追加
        else:
            # 通常決済処理 (1円以上の投入がある場合)
            print(f"🪙 通常決済成功: {current_amount}円分を購入しました")
            log_to_csv(student_id, f"通常決済({current_amount}円)")
            # 成功音を鳴らす
            play_sound(WAV_FILE)

        # どちらの決済が成功した場合も、M5Stickにリセット信号を送付し、ラズパイ内の金額も0に戻す
        if current_amount > 0 or (current_amount == 0 and student_id in subscribers):
            if ser and ser.is_open:
                ser.write(b"RESET\n")
            current_amount = 0

    else:
        print("\n⚠️ 学生番号が見つかりませんでした。")
        
    return True


# === メイン処理 ===
print("システム起動。M5StickCと接続しています...")
try:
    # M5StickCとの通信ポートを開く
    ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=0.1)
    print("✅ M5StickCとの通信準備完了！")
except Exception as e:
    print(f"⚠️ エラー: シリアルポート({SERIAL_PORT})が開けません。")
    print("M5StickCがUSBで接続されているか確認してください。")

print("========================================")
print("学生証をタッチして決済を開始してください")
print("========================================")

try:
    with nfc.ContactlessFrontend('usb') as clf:
        while True:
            # terminate=check_serial で、待ち受け中もM5Stickからのデータを受信
            result = clf.connect(rdwr={'on-connect': on_connect}, terminate=check_serial)
            
            if result is False:
                print("\n\n🛑 管理者操作により、システムを安全に終了しました。")
                break
            
            time.sleep(1.5)
            print("\n次の学生証をタッチしてください...")

except Exception as e:
    print(f"エラーが発生しました: {e}")
finally:
    # プログラム終了時にUSBポートを安全に閉じる
    if ser and ser.is_open:
        ser.close()