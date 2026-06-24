import streamlit as st
from datetime import datetime
import uuid
import mail_assistant
from mail_assistant import polish_email, send_email
import os


# ===== 页面视觉配置 =====
st.set_page_config(page_title="AI 邮件助手", page_icon="📧") # 设置浏览器标签页的名字和图标
st.title("📧 AI 邮件助手") # 在 Web 页面顶部显示大标题

# ===== 初始化“会话状态” session_state ===== 这是 Streamlit 最重要的机制。Streamlit 每次点击按钮都会从头到尾重新运行脚本，普通变量会丢失。st.session_state 就像 Web 端的“全局缓存”，用于跨交互保留数据。
if 'polished' not in st.session_state:
    st.session_state['polished'] = ""
if 'mail_edit_key' not in st.session_state:
    st.session_state['mail_edit_key'] = str(uuid.uuid4())
# 将 conversation_memory 存入 session_state
if 'conversation_memory' not in st.session_state:
    st.session_state['conversation_memory'] = mail_assistant.conversation_memory.copy()
else:
    # 每次脚本重跑时，确保 mail_assistant 使用 session 中的记忆
    mail_assistant.conversation_memory = st.session_state['conversation_memory']

# ===== 构建侧边栏（配置区） =====
with st.sidebar:
    st.header("⚙️ 配置")
    target_company = st.text_input("对方公司", value="贵公司")
    our_company = st.text_input("我方公司", value="我方公司")
    st.divider()
    st.header("📤 邮件发送")
    sender_email = st.text_input("发件人邮箱", value=os.getenv("MAIL_SENDER", "your@email.com"))
    auth_code = st.text_input("邮箱授权码", type="password")
    receiver_email = st.text_input("收件人邮箱")

    st.divider()
    st.header("📂 历史信件")
    companies = list(st.session_state['conversation_memory'].keys())
    if companies:
        selected_company = st.selectbox("选择公司查看历史", companies)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ 清空记录"):
                if selected_company in st.session_state['conversation_memory']:
                    del st.session_state['conversation_memory'][selected_company]
                    mail_assistant.conversation_memory = st.session_state['conversation_memory']
                    st.success(f"已清空 {selected_company} 的记录")
                    st.rerun()
        with col2:
            if st.button("📥 导出全部"):
                # 简单导出：以文本格式展示
                hist = st.session_state['conversation_memory'].get(selected_company, [])
                if hist:
                    text = f"=== {selected_company} 往来信件 ===\n\n"
                    for i in range(0, len(hist), 2):
                        user = hist[i]["content"] if i < len(hist) else ""
                        assistant = hist[i+1]["content"] if i+1 < len(hist) else ""
                        text += f"【用户】{user}\n【AI】{assistant}\n\n"
                    st.download_button("下载文本", data=text, file_name=f"{selected_company}_history.txt")
    else:
        st.info("暂无历史记录")


# ===== 主界面 - 输入与润色 =====
st.subheader("✍️ 邮件润色")
user_input = st.text_area("输入你想表达的内容", height=150) # 多行文本输入框，高度 150 像素

if st.button("🚀 润色邮件", type="primary"):
    if not user_input:
        st.warning("请输入需要润色的内容。")
    else:
        with st.spinner("AI 正在为你润色邮件..."):
            # 同步记忆
            mail_assistant.conversation_memory = st.session_state['conversation_memory']
            new_content = polish_email(user_input, target_company, our_company)
            st.session_state['conversation_memory'] = mail_assistant.conversation_memory
        if new_content:
            st.session_state['polished'] = new_content
            st.session_state['mail_edit_key'] = str(uuid.uuid4())
            st.success("✅ 邮件润色完成！")
        else:
            st.error("❌ 润色失败，请检查网络或重试。")
            
def convert_to_html(raw_text): #构建转换函数，方便调用
    """将纯文本转换为 HTML 格式，保留段落和换行。"""
    paragraphs = raw_text.split('\n\n')
    html_parts = []
    for p in paragraphs:
        p = p.replace('\n', '<br>').strip()
        if p:
            html_parts.append(f"<p>{p}</p>")
    return '\n'.join(html_parts) if html_parts else raw_text.replace('\n', '<br>')

# ===== 显示润色结果与操作区 =====
if st.session_state['polished']:  # 如果缓存里有润色内容
    st.markdown("### 📝 润色结果（可编辑）")
    # 动态 key 确保每次润色后刷新，只要 key 变了，这个输入框就会“重生”并刷新为最新的 value
    edited_content = st.text_area(   # edited_content 会实时捕获用户在文本框里的修改。
        "邮件正文", 
        value=st.session_state['polished'], # 默认值来自缓存
        height=300,
        key=st.session_state['mail_edit_key']
    )

    # 操作按钮-双栏布局
    col1, col2 = st.columns(2)
    
    #左栏：保存到本地
    with col1:
        subject = st.text_input("邮件主题（可选）", key="save_subject")
        if st.button("💾 保存到本地"):
            if not edited_content.strip():  # 检测是否空白
                st.warning("邮件内容为空，无法保存")
            else:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open("mail_output.txt", "a", encoding="utf-8") as f:  # "a" 模式表示追加写入，不覆盖之前保存的邮件
                    f.write(f"\n{'='*50}\n")
                    f.write(f"生成时间：{timestamp}\n")
                    f.write(f"主题：{subject or '无'}\n")
                    f.write(f"{'='*50}\n")
                    f.write(edited_content)
                    f.write(f"\n{'='*50}\n")
                st.success("✅ 已保存到 mail_output.txt")

    #右栏：发送邮件（含 HTML 格式转换）
    with col2:
        if st.button("📤 发送邮件"):
            if not receiver_email:  # ... 检查收件人和内容是否为空 ...
                st.error("请在侧边栏填写收件人邮箱。")
            elif not edited_content.strip():
                st.warning("邮件内容为空，无法发送")
            else:
                html_content = convert_to_html(edited_content)
                mail_assistant.AUTH_CODE = auth_code
                mail_assistant.SENDER_EMAIL = sender_email
                success = send_email(
                    receiver_email,
                    f"商务邮件 - {target_company}",
                    html_content  # 传入 HTML，邮件客户端就能正确显示分段和缩进了
                )
                if success:
                    st.balloons()  # 放送彩带动画，营造成功氛围
                    st.success(f"✅ 邮件已成功发送至 {receiver_email}！")
                else:
                    st.error("❌ 邮件发送失败，请检查配置。")
else:
    st.info("💡 请先输入内容并点击“润色邮件”生成邮件。") # 当 st.session_state['polished'] 为空时，显示蓝色提示信息


if 'selected_company' in locals() and selected_company in st.session_state['conversation_memory']:
    st.markdown(f"### 📜 与 {selected_company} 的往来记录")
    hist = st.session_state['conversation_memory'][selected_company]
    if not hist:
        st.info("暂无记录")
    else:
        for i in range(0, len(hist), 2):
            user_msg = hist[i]["content"] if i < len(hist) else ""
            assistant_msg = hist[i+1]["content"] if i+1 < len(hist) else ""
            with st.expander(f"📨 第 {i//2 + 1} 轮"):
                st.markdown(f"**🙋 你：**\n{user_msg}")
                st.markdown(f"**📧 AI 回复：**\n{assistant_msg}")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("📋 复制回复", key=f"copy_{i}"):
                        st.code(assistant_msg, language='text')  # 显示可复制代码块
                with col2:
                    if st.button("✏️ 加载到编辑框", key=f"load_{i}"):
                        st.session_state['polished'] = assistant_msg
                        st.session_state['mail_edit_key'] = str(uuid.uuid4())
                        st.success("已加载，可继续编辑或发送")
                        st.rerun()

# ===== 如果没有选中公司，显示默认信息 =====
else:
    st.info("💡 在侧边栏选择一家公司查看历史信件，或润色新邮件后自动记录。")

    