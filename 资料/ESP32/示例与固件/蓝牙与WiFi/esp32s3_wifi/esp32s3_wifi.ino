#include<WiFi.h>
const char* id="kuigenb666";   //定义两个字符串指针常量
const char* psw="12345678900";

void setup() {
  Serial.begin(115200);
  WiFi.begin(id,psw);
  while(WiFi.status()!=WL_CONNECTED){			//未连接上
    delay(500);
    Serial.println("正在连接...");
  }
  Serial.println("连接成功！");				//连接上
}
void loop(){							//空循环
}
