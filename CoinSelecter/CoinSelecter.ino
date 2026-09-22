#include <M5Unified.h>

const lgfx::v1::U8g2font* FontJP=&fonts::lgfxJapanGothic_20;

#define display M5.Display
M5Canvas canvas(&M5.Display);

// ユーザー環境に合わせた正しいピン設定
uint8_t coinPin=36;
uint8_t csdPin=26;
volatile int8_t coinNo=-1;
volatile bool bCoin=false;
const int coinPulseTimeout = 105;
const int coinPulseInterval = 10;
#define MaxCoinKinds 5

#define initCoin() {pinMode(coinPin, INPUT_PULLUP);pinMode(csdPin, OUTPUT);digitalWrite(csdPin,false);}
#define disableCoin() digitalWrite(csdPin,true)
#define enableCoin() digitalWrite(csdPin,false)
#define readCoin() (digitalRead(coinPin)==0)

TaskHandle_t hCoinTask;
bool csDisable = false;

// === ラズパイ連携用の変数 ===
int totalAmount = 0; 
const int coinValues[MaxCoinKinds] = {0, 100, 50, 10, 0}; 

// === 画面フィードバック用の変数 ===
bool isMessageShowing = false;
unsigned long messageEndTime = 0;
String currentMessage = "";
int currentMsgColor = TFT_WHITE;

// コインカウント用のバックグラウンド処理（元のまま）
void CoinTask(void *pvParameters){
  int cnt=0;
  while(1){
    if(readCoin()){
        disableCoin();
        if(bCoin) Serial.printf("E\n");
        cnt=0;
        while(readCoin()){
            delay(coinPulseInterval);
            if((++cnt)>(coinPulseTimeout/coinPulseInterval)) break;
        }
        coinNo++;
        cnt=0;
    }
    if(bCoin) cnt=0;
    else if(coinNo>=0) cnt++;
    
    if(cnt>(1+coinPulseTimeout/coinPulseInterval)){
        bCoin = true;
        cnt=0;
        enableCoin();
    }
    delay(coinPulseInterval);
  }
}

void setup() {
    auto cfg = M5.config();
    M5.begin(cfg);
    Serial.begin(115200);
    Serial.setTimeout(10); // コイン読み取りフリーズ防止のため追加

    initCoin();

    M5.Display.setRotation(1); // 横向き
    
    // カラー表現を豊かにするため、元のsetColorDepth(2)を削除しデフォルト設定を使用
    canvas.createSprite(display.width(), display.height());
    canvas.setFont(FontJP);
    
    xTaskCreatePinnedToCore(CoinTask, "CoinTask", 4096, NULL, 1, &hCoinTask, 0);
}

int cCounter[MaxCoinKinds];

void loop() {
    // === 1. ラズパイからのコマンド受信処理 ===
    if (Serial.available() > 0) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();
        
        if (cmd.startsWith("SUB:")) {
            String countStr = cmd.substring(4);
            currentMessage = "Sub: " + countStr;
            currentMsgColor = TFT_GREEN;
            isMessageShowing = true;
            messageEndTime = millis() + 5000;
            totalAmount = 0;
        } else if (cmd == "NORMAL") {
            currentMessage = "Thank You!";
            currentMsgColor = TFT_GREEN;
            isMessageShowing = true;
            messageEndTime = millis() + 5000;
            totalAmount = 0;
        } else if (cmd == "RETRY") {
            currentMessage = "Touch Again";
            currentMsgColor = TFT_RED;
            isMessageShowing = true;
            messageEndTime = millis() + 5000;
        } else if (cmd == "TIMEOUT") {
            currentMessage = "Timeout:\nResetting";
            currentMsgColor = TFT_ORANGE;
            isMessageShowing = true;
            messageEndTime = millis() + 5000;
            totalAmount = 0;
        } else if (cmd == "RESET") {
            totalAmount = 0;
            isMessageShowing = false;
        }
    }

    // === 2. メッセージ表示の5秒タイムアウト判定 ===
    if (isMessageShowing && millis() > messageEndTime) {
        isMessageShowing = false;
    }

    // === 3. コイン投入時の処理（元のまま） ===
    if(bCoin){
        int cn=coinNo;
        vTaskSuspend(hCoinTask);
        bCoin=false;
        coinNo=-1;
        vTaskResume(hCoinTask);
        
        if((cn>=0)&&(cn<MaxCoinKinds)){
            cCounter[cn]++;
            
            // 金額を加算してラズパイに送信
            totalAmount += coinValues[cn];
            Serial.println(totalAmount);
            
            // コインが入った瞬間、メッセージを解除して金額画面に戻す
            isMessageShowing = false;
        }
    }
    
    // === ボタン操作処理（元のまま） ===
    if(M5.BtnA.wasPressed()){
        totalAmount = 0;
        Serial.println("0"); 
        isMessageShowing = false;
        for(uint8_t i = 0; i < MaxCoinKinds; i++){
            cCounter[i]=0;
        }
    }
    
    if(M5.BtnB.wasPressed()){
        csDisable=!csDisable;
        digitalWrite(csdPin,csDisable);
    }
    
    M5.update();
    
    // === 4. 画面描画 ===
    canvas.fillSprite(TFT_BLACK);
    
    if (isMessageShowing) {
        // メッセージ表示（英語）
        canvas.setTextSize(2);
        canvas.setTextColor(currentMsgColor); // 緑や赤など状態に応じた色
        canvas.setCursor(10, 20);
        canvas.println(currentMessage);
    } else {
        // 通常の金額表示（「合計金額」は元の日本語フォントを活かしています）
        canvas.setTextSize(1);
        canvas.setTextColor(TFT_WHITE);
        canvas.drawString("合計金額:", 10, 5);
        
        canvas.setCursor(10, 30);
        canvas.setTextSize(2);
        canvas.printf("%d Yen", totalAmount);
    }
    
    canvas.pushSprite(0, 0);
    delay(50);
}