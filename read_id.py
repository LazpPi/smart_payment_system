import nfc
import re

# 学生番号の正規表現パターン（大文字2桁＋数字5桁）
STUDENT_ID_PATTERN = re.compile(r'[A-Z]{2}\d{5}')

def on_connect(tag):
    print("カード情報を読み取っています...")
    
    # 全データを安全にテキスト化
    data = "\n".join(tag.dump())
    
    # 正規表現で学生番号を抽出
    match = STUDENT_ID_PATTERN.search(data)
    
    if match:
        student_id = match.group()
        print(f"\n🎉 読み取り成功！ 学生番号: 【 {student_id} 】")
    else:
        print("\n⚠️ 学生番号が見つかりませんでした。")
        
    return True

print("システム起動。学生証をタッチしてください...")
try:
    with nfc.ContactlessFrontend('usb') as clf:
        clf.connect(rdwr={'on-connect': on_connect})
except Exception as e:
    print(f"エラーが発生しました: {e}")
# Ctrl+C が押されたときの安全な終了処理
except KeyboardInterrupt:
    print("\n\n🛑 管理者操作により、システムを安全に終了しました。")