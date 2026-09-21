#include <M5Unified.h>

const lgfx::v1::U8g2font* FontJP=&fonts::lgfxJapanGothic_20;

#define display M5.Display
M5Canvas canvas(&M5.Display);

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

// === ラズパイ連携用に追加した変数 ===
int totalAmount = 0; 
// パルス回数(coinNo)に対応する金額の設定 (※お使いのコインセレクターの設定に合わせて後で調整可能です)
const int coinValues[MaxCoinKinds] = {0, 100, 50, 10, 0}; 
// ===================================

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
    M5.begin();
    Serial.begin(115200);
    initCoin();

    // 音声機能はラズパイに任せるため無効化
    // if(!initLfsWav()){ ... }

    M5.Lcd.setRotation(1);
    canvas.setColorDepth(2);
    canvas.setFont(FontJP);
    canvas.createSprite(display.width(), display.height());
    canvas.setTextSize(1);
    canvas.setPaletteColor(1, ORANGE);
    
    xTaskCreatePinnedToCore(CoinTask, "CoinTask", 4096, NULL, 1, &hCoinTask, 0);
}

int cCounter[MaxCoinKinds];

void loop() {
    // === ラズパイからのリセット信号受信処理 ===
    if (Serial.available() > 0) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();
        if (cmd == "RESET") {
            totalAmount = 0; // 合計金額を0に戻す
            Serial.println("0"); // リセット完了をラズパイに通知
        }
    }

    // === コイン投入時の処理 ===
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
            
            // playLfsWav(wfn[cn]); // M5側の音声はオフ
        }
    }
    
    if(M5.BtnA.wasPressed()){
        totalAmount = 0;
        Serial.println("0"); // 手動リセット時もラズパイに0を送信
        for(uint8_t i = 0; i < MaxCoinKinds; i++){
            cCounter[i]=0;
        }
    }
    
    if(M5.BtnB.wasPressed()){
        csDisable=!csDisable;
        digitalWrite(csdPin,csDisable);
    }
    
    M5.update();
    canvas.fillSprite(0);
    canvas.drawString("合計金額:", 10, 5);
    
    // 画面に合計金額を大きく表示
    canvas.setCursor(10, 30);
    canvas.setTextSize(2);
    canvas.printf("%d Yen", totalAmount);
    canvas.setTextSize(1);
    
    canvas.pushSprite(0, 0);
    delay(50);
}