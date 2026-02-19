import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

def send_gmail_notification(subject: str, body: str, success: bool = True):
    """
    Gmail SMTP를 사용하여 알림 이메일을 전송합니다.
    환경 변수 GMAIL_USER, GMAIL_APP_PASSWORD가 설정되어 있어야 합니다.
    """
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")
    gmail_to = os.environ.get("GMAIL_TO", gmail_user) # 수신자가 없으면 발신자에게 전송

    if not gmail_user or not gmail_password:
        # 로컬 테스트 시 로그만 남김
        # print("⚠️ 환경 변수 'GMAIL_USER' 또는 'GMAIL_APP_PASSWORD'가 설정되지 않았습니다.")
        return

    # KST 시간 계산
    kst = timezone(timedelta(hours=9))
    now_kst = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")

    # 이메일 구성
    msg = MIMEMultipart()
    msg['From'] = gmail_user
    msg['To'] = gmail_to
    msg['Subject'] = f"{'[성공]' if success else '[실패]'} {subject} ({now_kst})"

    # 메일 본문 (HTML)
    html_body = f"""
    <html>
      <body>
        <h2>🎙️ NotebookLM Podcast Agent Alert</h2>
        <p><b>Time:</b> {now_kst}</p>
        <p><b>Status:</b> {'✅ Success' if success else '❌ Failure'}</p>
        <hr>
        <pre style="font-family: monospace; background-color: #f4f4f4; padding: 10px;">
{body}
        </pre>
        <p>This is an automated message from your Cloud Automation Agent.</p>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_body, 'html'))

    try:
        # Gmail SMTP 서버 연결 (TLS)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user, gmail_password)
        text = msg.as_string()
        server.sendmail(gmail_user, gmail_to, text)
        server.quit()
        print("✅ Gmail 알림 전송 완료")
    except Exception as e:
        print(f"❌ Gmail 알림 전송 실패: {e}")

if __name__ == "__main__":
    send_gmail_notification("Test Notification", "This is a test email from Podcast Agent.", success=True)
