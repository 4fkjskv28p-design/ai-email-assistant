import requests
import time
from datetime import datetime
import re  # 提前导入，避免函数内重复导入
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import os
from dotenv import load_dotenv

load_dotenv()

# ========== 配置 ==========
API_KEY = os.getenv("DEEPSEEK_API_KEY")
URL = "https://api.deepseek.com/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}
MODEL = "deepseek-chat"
conversation_memory = {}

# ========== 邮件发送配置 ==========
SMTP_SERVER = "smtp.qq.com"        # 你的邮箱SMTP服务器地址
SMTP_PORT = 465                    # SSL加密端口
SENDER_EMAIL = os.getenv("MAIL_SENDER")  # 你的发件邮箱
AUTH_CODE = os.getenv("MAIL_AUTH_CODE")     # 上一步获取的授权码，不是密码！

if not API_KEY or not AUTH_CODE or not SENDER_EMAIL:
    raise ValueError("请在 .env 文件中设置 DEEPSEEK_API_KEY, QQ_MAIL_AUTH_CODE, QQ_MAIL_SENDER")
    

def send_email(receiver_email, subject, html_content):
    """
    发送一封HTML格式的邮件
    """
    # 1. 创建邮件对象
    message = MIMEMultipart('alternative')
    message['Subject'] = Header(subject, 'utf-8')
    message['From'] = SENDER_EMAIL
    message['To'] = receiver_email

    # 2. 将邮件正文（HTML格式）附加到邮件对象[reference:25]
    html_part = MIMEText(html_content, 'html', 'utf-8')
    message.attach(html_part)

    # 3. 发送邮件
    try:
        # 建立与SMTP服务器的安全连接
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            # 登录邮箱
            server.login(SENDER_EMAIL, AUTH_CODE)
            # 发送邮件
            server.sendmail(SENDER_EMAIL, receiver_email, message.as_string())
        print(f"✅ 邮件已成功发送至 {receiver_email}")
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")
        return False

# ========== 核心函数 ==========
def polish_email(raw_text, target_company, our_company):
    if not raw_text or not raw_text.strip():
        return "❗️输入内容为空，请提供需要润色的文本。"

    today = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")

    system_prompt = f"""
你是一位专业的商务邮件撰写助理。你的任务是将用户提供的非正式、口语化的描述，改写成一封正式、礼貌、结构清晰的商务邮件。

要求：
1. 邮件必须包含：称呼（请使用对方公司名称：{target_company}）、正文（清晰说明事项）、结束语（含感谢或期待回复）**严禁**缩写、省略或改动，直接写成“尊敬的{target_company}：”）
2. 署名（落款）**必须直接使用**我方公司名称：{our_company}，**严禁**使用"[您的姓名]""[职务]"或任何形式的占位符。
3. 邮件结尾的日期**必须使用**具体日期：{today}，**严禁**使用"[日期]"占位符。
4. 语气要专业、诚恳。
5. 如果用户提到延期、错误等问题，要恰当表达歉意，并提出解决方案。
6. 保持原意不变，语言精炼、有逻辑。
7. **绝对禁止**生成任何包含方括号`[ ]`的占位符文本。如果你觉得用户提供的信息不足以写出一封完整的邮件（例如缺少具体事项、收件人、原因等），**请不要尝试补全**，而是直接输出以下标准提示语，不要输出任何邮件正文：
   "❓ 您的描述比较简略，请补充以下信息以便我为您撰写邮件：收件人是谁？具体要沟通什么事情？有什么需要对方配合或注意的吗？"

【优秀示例】
用户输入：我们服务器故障，项目要延期两天，向客户道歉。
正确输出：
尊敬的创新互联科技：

您好！

关于贵公司与我方合作项目的交付进度，我们遗憾地通知您，因近期服务器出现技术故障，产品交付需延期两天。我们深知延期会给您带来不便，对此深表歉意。技术团队正在全力抢修，并确保在调整后的时间内高质量交付。感谢您的理解与支持！

智云软件
2026年06月17日

【错误示例】
用户输入：我的AI
错误输出：尊敬的[收件人]，您好！……[您的姓名][日期]  （这种输出是**不合格**的，严禁出现）
【错误示例】
如果对方公司名称为“北京云创科技”，你不能写成“尊敬的贵公司”或“尊敬的云创”，必须写成“尊敬的北京云创科技：”
"""

    messages = [{"role": "system", "content": system_prompt}]

    # 加载历史记录
    if target_company in conversation_memory:
        history = conversation_memory[target_company]
        messages.extend(history[-6:])  # 只取最近6条（3轮）
        print(f"已加载与[{target_company}]的{len(history)}条历史记录")
        
    messages.append({"role": "user", "content": raw_text})
    
    data = {"model": MODEL, "messages": messages}
    
    # 后处理清洗函数（移到外部定义，但这里保留）
    def clean_placeholders(text):
        replacements = {
            r"\[您的姓名\]": our_company,
            r"\[日期\]": today,
            r"\[收件人\]": target_company,
            r"\[.*?\]": ""
        }
        for pattern, repl in replacements.items():
            text = re.sub(pattern, repl, text)
        text = re.sub(r"\n\s*\n", "\n\n", text).strip()
        return text

    for attempt in range(3):
        try:
            response = requests.post(URL, headers=HEADERS, json=data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                cleaned = clean_placeholders(content)
                
                # ========== ✅ 正确存储记忆 ==========
                if target_company not in conversation_memory:
                    conversation_memory[target_company] = []
                # 存储用户问题（正确用法：append(字典)）
                conversation_memory[target_company].append({"role": "user", "content": raw_text})
                # 存储AI回复
                conversation_memory[target_company].append({"role": "assistant", "content": cleaned})
                
                return cleaned  # 返回润色结果
                
            elif response.status_code == 429:
                wait_time = 2 * (attempt + 1)
                print(f"⏳ 请求频繁，等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            elif response.status_code >= 500:
                wait_time = 2 * (attempt + 1)
                print(f"⚠️ 服务器错误 {response.status_code}，等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                print(f"❌ 错误 {response.status_code}: {response.text}")
                return None
        except Exception as e:
            print(f"❌ 网络异常: {e}")
            return None
    print("❌ 重试三次仍失败，请稍后再试。")
    return None

def save_mail(content):
    subject = input("请输入邮件主题：（直接回车跳过）：").strip()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open("mail_output.txt", "a", encoding="utf-8") as f:
        f.write(f"\n{'='*50}\n")
        f.write(f"生成时间：{timestamp}\n")
        if subject:
            f.write(f"主题：{subject}\n")
        f.write(f"{'='*50}\n")
        f.write(content)
        f.write(f"\n{'='*50}\n")
    print("✅ 邮件已保存到 mail_output.txt")

def main():
    print("📧 你的邮件润色助手已上线，输入 quit 退出")
    target_company = input("请输入对方公司名称：（未输入则默认贵公司）").strip()
    if not target_company:
        target_company = "贵公司"
    our_company = input("请输入我方公司名称：（未输入默认我方公司）").strip()
    if not our_company:
        our_company = "我方公司"
    print(f"已设定:对方公司->{target_company}，我方公司->{our_company}\n")
    
    print("💡 输入你想要表达的大白话，我会帮你润色成正式邮件。")
    print("💡 额外指令：--history 查看记录  --clear 清空记忆  --set 重新设置公司名  --send 发送最近一封邮件\n")
    
    last_polished = None  # 缓存最近一次润色成功的邮件

    while True:
        user_input = input("🙋 你：")
        if user_input.lower() in ["quit", "exit", "退出"]:
            print("👋 再见！")
            break

        # ---------- 指令处理区 ----------
        if user_input.lower() == "--history":
            if target_company in conversation_memory and conversation_memory[target_company]:
                print(f"\n📜 与 [{target_company}] 的历史往来记录：")
                hist = conversation_memory[target_company]
                for i in range(0, len(hist), 2):
                    user_msg = hist[i]["content"] if i < len(hist) else ""
                    assistant_msg = hist[i+1]["content"] if i+1 < len(hist) else ""
                    print(f"  🙋 你：{user_msg[:30]}……" if len(user_msg) > 30 else f"  🙋 你：{user_msg}")
                    print(f"  📧 AI：{assistant_msg[:30]}……" if len(assistant_msg) > 30 else f"  📧 AI：{assistant_msg}")
                    print("  ---")
            else:
                print(f"📭 目前没有与 [{target_company}] 的历史记录。")
            continue

        if user_input.lower() == "--clear":
            if target_company in conversation_memory:
                del conversation_memory[target_company]
                print(f"🗑️ 已清空与 [{target_company}] 的记忆，接下来的对话将视为新往来。")
            else:
                print("📭 没有需要清空的记忆。")
            continue

        if user_input.lower() == "--set":
            print("重新设置公司名称")
            new_target = input("输入对方公司新名称（回车保留默认值）：").strip()
            if new_target:
                target_company = new_target
            new_our = input("输入我方公司新名称（回车保留默认值）：").strip()
            if new_our:
                our_company = new_our
            print(f"新名称已设定：对方->{target_company}，我方->{our_company}\n")
            continue

        if user_input.lower() == "--send":
            if not last_polished:
                print("⚠️ 还没有润色好的邮件，请先输入内容生成一封邮件。")
            else:
                receiver = input("请输入收件人邮箱地址：").strip()
                if not receiver:
                    print("❌ 收件人地址不能为空。")
                else:
                    subject = f"商务邮件 - {target_company}"
                    send_email(receiver, subject, last_polished)
            continue

        # ---------- 普通输入（润色） ----------
        if not user_input.strip():
            print("⚠️ 输入不能为空，请重新输入。")
            continue

        print("📝 正在润色，请稍候...")
        polished = polish_email(user_input, target_company, our_company)
        if polished:
            last_polished = polished  # 缓存邮件
            print("\n📧 润色后的邮件：")
            print("-" * 40)
            print(polished)
            print("-" * 40)
            while True:
                action = input("\n选项：保存（s）/重新润色（r）/跳过（n）[默认 s]：").strip().lower()
                if action in ["s", ""]:
                    save_mail(polished)
                    break
                elif action == "r":
                    print("♻️ 重新润色中……")
                    polished = polish_email(user_input, target_company, our_company)
                    if polished:
                        last_polished = polished  # 更新缓存
                        print("\n📧 再次润色后的邮件：")
                        print("-" * 40)
                        print(polished)
                        print("-" * 40)
                        continue
                    else:
                        print("润色失败，请重试……")
                        break
                elif action == "n":
                    print("已跳过")
                    break
                else:
                    print("请输入 s / r / n")
        else:
            print("❌ 润色失败，请检查网络或重试。")

        print("*" * 40)

if __name__ == "__main__":
    main()