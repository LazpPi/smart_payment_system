import nfc
import re
import time
import csv
import os
import json
import subprocess
from datetime import datetime

# 学生番号の正規表現パターン（大文字2桁＋数字5桁）
STUDENT_ID_PATTERN = re.compile(r'[A-Z]{2}\d{5}')
# 保存するCSVファイルの名前
CSV_FILE = "visit_history.csv"
SUBSCRIBERS_FILE = "subscribers.json"
WAV_FILE = "thank_you.wav"

# aplayコマンドでwavファイルを再生する
def play_sound(file_path):
    if os.path.exists(file_path):
        # 処理を止めずに裏側で音声を流す(非同期再生)
        # stderr=subprocess.DEVNULL を追加し、スピーカーがない時のエラー表示を隠す
        subprocess.Popen(["aplay", "-D", "plughw:2,0", "-q", file_path], stderr=subprocess.DEVNULL)
    else:
        print("⚠️ 音声ファイルが見つかりません")

# サブスク登録者リストを読み込む
def load_subscribers():
    if os.path.exists(SUBSCRIBERS_FILE):
        with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {} # インデントを修正

# サブスク利用者リストを保存する
def save_subscribers(data): # 関数名のタイポ(seve -> save)を修正
    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# 学生番号と現在時刻をCSVに追記する関数
def log_to_csv(student_id, item_name):
    # ファイルの存在確認
    file_exists = os.path.isfile(CSV_FILE)

    # aモード(追記モード)でファイルを開く
    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # ファイルが新規作成された時のみ、1行目にヘッダーを書く
        if not file_exists:
            writer.writerow(["Timestamp", "StudentID", "Item"]) # ヘッダーにItemを追加
        
        # 現在の時刻を取得して書き込み
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([now, student_id, item_name]) # Item を item_name に修正

# 学生番号を読み取る関数
def on_connect(tag):
    print("カード情報を読み取っています...")
    
    # 全データを安全にテキスト化
    data = "\n".join(tag.dump())
    
    # 正規表現で学生番号を抽出
    match = STUDENT_ID_PATTERN.search(data)
    
    if match:
        student_id = match.group()
        print(f"\n🎉 読み取り成功！ 学生番号: 【 {student_id} 】")

        # サブスクリストの読み込み
        subscribers = load_subscribers()

        # 今後はM5Stickから入金額チェックが入る
        # 今回はテストとしてJSONに学生番号があればサブスク利用とする
        if student_id in subscribers:
            subscribers[student_id]["used_count"] += 1
            save_subscribers(subscribers) # カウント増やして上書き保存

            count = subscribers[student_id]["used_count"]
            print(f"☕️ サブスク利用: {count}杯目(テスト)") # scount を count に修正
            
            play_sound(WAV_FILE) # サブスク利用時に音を鳴らすよう移動
            log_to_csv(student_id, f"コーヒー（サブスク {count}杯目）")
        else:
            print("💰 通常決済（未登録）")
            log_to_csv(student_id, "通常決済(テスト)")

    else:
        print("\n⚠️ 学生番号が見つかりませんでした。")
        
    return True

print("システム起動。学生証をタッチしてください...")
try:
    with nfc.ContactlessFrontend('usb') as clf:
        while True:
            # connectの実行結果を変数 result に受け取る
            result = clf.connect(rdwr={'on-connect': on_connect})
            
            # Ctrl+Cが押されてキャンセルされた場合、result が False になる
            if result is False:
                print("\n\n🛑 管理者操作により、システムを安全に終了しました。")
                break  # while True の無限ループから脱出する
            
            time.sleep(1)
            print("\n次の学生証をタッチしてください")

except Exception as e:
    print(f"エラーが発生しました: {e}")