# WEB Wake-on-lan

### introduction
본 프로젝트는 wake-on-lan 기능을 웹에서 사용할수 있게 구현한 토이 프로젝트 입니다.     
리눅스와 윈도우가 별도의 SSD에 설치된 하나의 데스크톱이 있습니다. 리눅스는 개발 테스트 용도로, 윈도우는 게임용도로 사용하고 있는데 데스크톱이 책상아래에 있어서 허리를 굽혀서 전원을 켜야 하는데요. 이게 은근 귀찮아서 웹인터페이스로 wake-on-lan 을 구현해 보았습니다. 웹 상에서 쉘 커맨드를 실행하는 구조이기 때문에 보안을 위해 on/off시 google otp 인증을 추가 하였습니다.

![setup_otp](static/img/setup-otp_web_wakeonlan.png)
![web_wakeonlan](static/img/web_wakeonlan_screen.png)


### 주의사항
- WIFI는 wake-on-lan을 지원하지 않습니다. 테스크톱은 유선 LAN으로 연결되어 있어야 합니다.
- OS에서 wake-on-lan 설정을 해야 합니다. 저는 리눅스가 윈도우보다 익숙해서 리눅스 상에서 진행했습니다.(설정은 구글링 참조)

### hardware
* Raspberry Pi Zero 2W

