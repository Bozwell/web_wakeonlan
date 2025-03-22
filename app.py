from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import subprocess
import os
import pyotp
import secrets
import qrcode
from io import BytesIO
import base64
import json
import time
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # 세션 암호화를 위한 비밀 키

load_dotenv('.env')

# 설정값 (실제 사용 시 수정 필요)
SSH_USER = os.getenv('SSH_USER')
REMOTE_HOST = os.getenv('REMOTE_HOST')
SHUTDOWN_COMMAND = "sudo shutdown -P now"
WAKEONLAN_MAC = os.getenv('WAKEONLAN_MAC') # 데스크톱의 MAC 주소로 변경 필요


# 설정 파일 경로
CONFIG_FILE = "app_config.json"

def load_config():
    """설정 파일 로드"""
    default_config = {
        "otp_setup_complete": False, 
        "otp_secret": None,
        "power_state": "off",  # 기본값은 꺼짐 상태
        "last_updated": int(time.time())
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"설정 파일 로드 오류: {e}")
    return default_config

def save_config(config):
    """설정 파일 저장"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        return True
    except Exception as e:
        print(f"설정 파일 저장 오류: {e}")
        return False

# 초기 설정 로드
APP_CONFIG = load_config()

def check_power_state():
    """실제 컴퓨터 전원 상태 확인 (핑 명령 사용)"""
    try:
        # ping 명령으로 컴퓨터 상태 확인 (1번 ping, 1초 타임아웃)
        cmd = f"ping -c 1 -W 1 {REMOTE_HOST}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            # 핑 응답이 있으면 켜진 상태
            return "on"
        else:
            # 핑 응답이 없으면 꺼진 상태
            return "off"
    except Exception as e:
        print(f"전원 상태 확인 오류: {e}")
        # 오류 발생 시 저장된 상태 반환
        return APP_CONFIG.get("power_state", "off")

@app.route('/')
def index():
    # OTP가 설정되어 있지 않으면 설정 페이지로 이동
    if not APP_CONFIG.get("otp_setup_complete", False):
        return redirect(url_for('setup_otp'))
    
    # 현재 전원 상태 확인
    power_state = check_power_state()
    
    # 상태가 변경되었으면 저장
    if power_state != APP_CONFIG.get("power_state"):
        APP_CONFIG["power_state"] = power_state
        APP_CONFIG["last_updated"] = int(time.time())
        save_config(APP_CONFIG)
    
    return render_template('index.html', power_state=power_state)

@app.route('/power-state')
def get_power_state():
    """API로 현재 전원 상태 반환"""
    power_state = check_power_state()
    
    # 상태가 변경되었으면 저장
    if power_state != APP_CONFIG.get("power_state"):
        APP_CONFIG["power_state"] = power_state
        APP_CONFIG["last_updated"] = int(time.time())
        save_config(APP_CONFIG)
    
    return jsonify({
        "power_state": power_state,
        "last_updated": APP_CONFIG.get("last_updated")
    })

@app.route('/setup-otp', methods=['GET', 'POST'])
def setup_otp():
    if request.method == 'POST':
        otp_code = request.form.get('otp_code')
        otp_secret = session.get('temp_otp_secret')
        
        if not otp_secret:
            return render_template('setup_otp.html', error="세션이 만료되었습니다. 다시 시도해주세요.")
        
        # OTP 코드 검증
        totp = pyotp.TOTP(otp_secret)
        if totp.verify(otp_code):
            # OTP 설정 저장
            APP_CONFIG["otp_setup_complete"] = True
            APP_CONFIG["otp_secret"] = otp_secret
            save_config(APP_CONFIG)
            
            # 세션에서 임시 OTP 비밀 키 제거
            session.pop('temp_otp_secret', None)
            session.pop('qr_code', None)
            
            return redirect(url_for('index'))
        else:
            return render_template('setup_otp.html', 
                                  qr_code=session.get('qr_code'), 
                                  error="잘못된 OTP 코드입니다. 다시 시도해주세요.")
    
    # 이미 설정되어 있는 경우 메인 페이지로 리다이렉트
    if APP_CONFIG.get("otp_setup_complete", False):
        return redirect(url_for('index'))
    
    # 새 OTP 비밀 키 생성
    otp_secret = pyotp.random_base32()
    session['temp_otp_secret'] = otp_secret
    
    # QR 코드 생성
    totp = pyotp.TOTP(otp_secret)
    provisioning_url = totp.provisioning_uri(name="데스크톱 전원 제어", issuer_name="Desktop Power Controller")
    
    qr = qrcode.make(provisioning_url)
    buffered = BytesIO()
    qr.save(buffered)
    qr_code_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    # QR 코드를 세션에 저장
    session['qr_code'] = qr_code_base64
    
    return render_template('setup_otp.html', qr_code=qr_code_base64)

@app.route('/reset-otp', methods=['GET'])
def reset_otp():
    """OTP 설정 초기화 (개발 및 문제 해결용)"""
    APP_CONFIG["otp_setup_complete"] = False
    APP_CONFIG["otp_secret"] = None
    save_config(APP_CONFIG)
    
    # 세션 데이터도 초기화
    session.pop('temp_otp_secret', None)
    session.pop('qr_code', None)
    
    return redirect(url_for('setup_otp'))

@app.route('/power', methods=['POST'])
def power_control():
    power_state = request.json.get('state')
    otp_code = request.json.get('otp_code')
    
    # OTP 코드 검증
    otp_secret = APP_CONFIG.get("otp_secret")
    if not otp_secret:
        return jsonify({"status": "error", "message": "OTP가 설정되지 않았습니다."})
    
    totp = pyotp.TOTP(otp_secret)
    if not totp.verify(otp_code):
        return jsonify({"status": "error", "message": "잘못된 OTP 코드입니다."})
    
    if power_state == 'off':
        try:
            # 이미 꺼져 있는지 확인
            current_state = check_power_state()
            if current_state == "off":
                return jsonify({"status": "success", "message": "컴퓨터가 이미 꺼져 있습니다."})
            
            # SSH로 원격 종료 명령 실행
            cmd = f"ssh {SSH_USER}@{REMOTE_HOST} '{SHUTDOWN_COMMAND}'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                # 상태 업데이트
                APP_CONFIG["power_state"] = "off"
                APP_CONFIG["last_updated"] = int(time.time())
                save_config(APP_CONFIG)
                return jsonify({"status": "success", "message": "컴퓨터 종료 명령을 보냈습니다."})
            else:
                return jsonify({"status": "error", "message": f"종료 오류: {result.stderr}"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"에러 발생: {str(e)}"})
    
    elif power_state == 'on':
        try:
            # 이미 켜져 있는지 확인
            current_state = check_power_state()
            if current_state == "on":
                return jsonify({"status": "success", "message": "컴퓨터가 이미 켜져 있습니다."})
            
            # Wake-on-LAN 패킷 전송 (wakeonlan 패키지 필요)
            cmd = f"wakeonlan {WAKEONLAN_MAC}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                # 상태 업데이트 (실제로는 부팅 시간이 필요하므로 바로 업데이트하지 않음)
                # 나중에 index나 power-state API 호출 시 실제 상태 확인됨
                return jsonify({
                    "status": "success", 
                    "message": "전원 켜기 명령을 보냈습니다. 부팅이 완료되기까지 잠시 기다려주세요."
                })
            else:
                return jsonify({"status": "error", "message": f"전원 켜기 오류: {result.stderr}"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"에러 발생: {str(e)}"})
    
    return jsonify({"status": "error", "message": "잘못된 요청입니다."})

if __name__ == '__main__':
    # 서버 실행
    app.run(host='0.0.0.0', port=5000, debug=False)