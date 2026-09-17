import nfc

def on_connect(tag):
    print("¥nカードを検知しました")
    # タグの中から周辺の固有のIDを取り出して大文字の文字列に変換
    idm = tag.identifier.hex().upper()
    print(f"あなたの学生証のIDm：{idm}")
    return True

print("システム起動完了")
print("PaSoRiに学生証をタッチしてください")

try:
    with nfc.ContactlessFrontend("usb") as clf:
        clf.connect(rdwr={"on-connect": on_connect})
except Exception as e:
    print(f"エラーが発生しました： {e}")
    print("PaSoRiが正しく接続されているか確認してください")