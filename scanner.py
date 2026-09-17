import nfc

def on_connect(tag):
    print("\n=== カード解析結果 ===")
    print(f"IDm: {tag.identifier.hex().upper()}")
    
    # FeliCa (学生証など) かどうかを判定
    if isinstance(tag, nfc.tag.tt3.Type3Tag):
        try:
            # カードの中にある「システムコード（大きなフォルダ）」の一覧を取得
            sys_codes = tag.request_system_code()
            print("発見されたシステムコード:")
            for sc in sys_codes:
                # 見やすく16進数（0x...）で表示
                print(f" - {hex(sc).upper().replace('X', 'x')}")
        except Exception as e:
            print(f"解析エラー: {e}")
    else:
        print("このカードはFeliCa形式ではありません。")
        
    print("======================")
    return True

print("学生証をタッチしたままにしてください...")
try:
    with nfc.ContactlessFrontend('usb') as clf:
        clf.connect(rdwr={'on-connect': on_connect})
except Exception as e:
    print(f"エラー: {e}")