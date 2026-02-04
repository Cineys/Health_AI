import streamlit as st
import dashscope
from dashscope.api_entities.dashscope_response import Role
import pandas as pd
import datetime
import os
import random
import io

# ==================================================
# 1. 基础配置
# ==================================================
st.set_page_config(page_title="AI健康助手", page_icon="🦄", layout="centered")

# 🔴 请替换你的阿里云 API KEY
dashscope.api_key = "sk-0ea0bbd5452c449080e4a1422241feca"

# --- CSS 样式 ---
st.markdown("""
<style>
    .stApp {background: linear-gradient(180deg, #F3F0FF 0%, #FFFFFF 100%);}
    .health-card {
        background-color: white; padding: 20px; border-radius: 15px;
        box-shadow: 0 4px 15px rgba(100, 100, 255, 0.1);
        margin-bottom: 20px; text-align: center;
    }
    div.stButton > button {
        background-color: white; color: #555; border: 1px solid #E0E0E0;
        border-radius: 12px; padding: 15px 20px; font-size: 16px;
        width: 100%; text-align: left; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        transition: all 0.3s; margin-bottom: 5px;
    }
    div.stButton > button:hover {
        border-color: #8B5CF6; color: #8B5CF6; transform: translateY(-2px);
    }
    /* 返回按钮样式 */
    .back-btn {margin-bottom: 20px;}
    
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ==================================================
# 2. 核心逻辑层
# ==================================================

# 初始化 Session
if "messages" not in st.session_state:
    st.session_state.messages = []
if "report" not in st.session_state:
    st.session_state.report = None
if "prompt_input" not in st.session_state:
    st.session_state.prompt_input = None

# --- 新增：页面模式控制 ---
# 'chat' 代表聊天页面, 'report' 代表报告详情页
if "page_mode" not in st.session_state:
    st.session_state.page_mode = "chat"

def get_ai_response(messages):
    try:
        # 强制多轮对话引导逻辑
        system_prompt = {
            "role": "system",
            "content": """
            你是一位专业、耐心、如同家人般的AI全科医生。
            【对话策略】
            1. 禁止长篇大论，回复控制在150字内。
            2. 严格执行多轮问诊：
               - 第一步：安抚情绪，问持续时间/具体感觉。
               - 第二步：根据回答追问伴随症状。
               - 第三步：信息收集完整后，再给建议。
            3. 语气温柔、口语化。
            4. 遇到危急重症（剧烈头痛、昏迷等）立即建议急诊。
            """
        }
        history = [system_prompt] + messages
        response = dashscope.Generation.call(
            model=dashscope.Generation.Models.qwen_turbo,
            messages=history,
            result_format='message',
        )
        if response.status_code == 200:
            return response.output.choices[0].message.content
        else:
            return "助手有点累了，请稍后再试。"
    except Exception as e:
        return f"系统错误: {e}"

def generate_medical_report(chat_history):
    try:
        # 获取实时时间
        current_time = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M")
        
        prompt = f"""
        请根据以上对话生成《健康初筛报告》。
        【要求】
        1. 第一行显示：**生成时间**：{current_time}
        2. 包含：【主诉摘要】、【症状分析】、【生活建议】、【就医指引】。
        3. Markdown格式，专业客观。
        """
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
        
        response = dashscope.Generation.call(
            model=dashscope.Generation.Models.qwen_plus,
            messages=[{"role": "user", "content": f"{prompt}\n\n{history_text}"}],
            result_format='message',
        )
        if response.status_code == 200:
            return response.output.choices[0].message.content
        return "报告生成失败。"
    except Exception:
        return "报告错误"

def convert_to_excel_bytes(messages, report_content):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output = io.BytesIO()
    data = []
    for msg in messages:
        role = "助手" if msg["role"] == "assistant" else "用户"
        data.append({"时间": timestamp, "角色": role, "内容": msg["content"]})
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame(data).to_excel(writer, sheet_name="问诊记录", index=False)
        if report_content:
            pd.DataFrame([{"内容": report_content}]).to_excel(writer, sheet_name="AI报告", index=False)
    return output.getvalue()

# ==================================================
# 3. 前端交互层 (视图切换逻辑)
# ==================================================

# --- 侧边栏 ---
with st.sidebar:
    st.title("🧰 工具箱")
    
    # 逻辑：点击生成 -> 切换到 'report' 模式
    if st.button("📄 生成健康报告", type="primary"):
        if len(st.session_state.messages) > 1:
            with st.spinner("阿福正在整理病历..."):
                rep = generate_medical_report(st.session_state.messages)
                st.session_state.report = rep
                st.session_state.page_mode = "report" # <--- 关键：切换页面状态
                st.rerun() # 立即刷新页面
        else:
            st.warning("请先和阿福多聊几句哦~")
            
    # 查看历史报告按钮（如果已经生成过）
    if st.session_state.report and st.session_state.page_mode == "chat":
        if st.button("🔍 查看刚才的报告"):
            st.session_state.page_mode = "report"
            st.rerun()

    st.markdown("---")
    if st.button("🗑️ 清空记忆"):
        st.session_state.messages = []
        st.session_state.report = None
        st.session_state.page_mode = "chat" # 重置回聊天页
        st.rerun()

# ==================================================
# 页面分发逻辑 (Router)
# ==================================================

# --- 模式 A: 报告详情页 ---
if st.session_state.page_mode == "report":
    # 1. 返回按钮
    if st.button("⬅️ 返回对话 (不删除报告)"):
        st.session_state.page_mode = "chat"
        st.rerun()
        
    st.title("📋 您的健康初筛报告")
    st.markdown("---")
    
    # 2. 展示报告内容
    with st.container(border=True):
        st.markdown(st.session_state.report)
    
    # 3. 下载区域 (大大的按钮)
    st.markdown("### 📥 保存报告")
    col1, col2 = st.columns(2)
    
    with col1:
        st.download_button(
            label="📄 下载文本文件 (Markdown)",
            data=st.session_state.report,
            file_name=f"健康报告_{datetime.datetime.now().strftime('%Y%m%d')}.md",
            mime="text/markdown",
            use_container_width=True
        )
    with col2:
        excel_data = convert_to_excel_bytes(st.session_state.messages, st.session_state.report)
        st.download_button(
            label="📊 下载完整病历 (Excel)",
            data=excel_data,
            file_name=f"病历记录_{datetime.datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# --- 模式 B: 聊天主页 ---
else:
    # 1. 顶部步数卡片
    st.markdown("### 嗨 ✨\n**好好珍惜每一份美好**")
    step_count = random.randint(3000, 12000)
    progress_val = min(step_count / 10000 * 100, 100)
    
    st.markdown(f"""
    <div class="health-card">
        <h3 style="margin:0; color:#8B5CF6;">今日步数</h3>
        <h1 style="font-size: 3em; margin: 10px 0;">{step_count}</h1>
        <div style="background-color:#eee; border-radius:10px; height:10px; width:100%;">
            <div style="background-color:#8B5CF6; width:{progress_val}%; height:100%; border-radius:10px;"></div>
        </div>
        <p style="color:gray; margin-top:10px;">👣 同步记录中，我来看你动够没</p>
    </div>
    """, unsafe_allow_html=True)

    # 2. 快捷问题 (无历史时显示)
    if len(st.session_state.messages) == 0:
        quick_questions = ["😴 熬夜后如何补觉？", "🥛 晚上口干可能是什么病？", "📱 手机放枕边会影响睡眠吗？"]
        st.caption("👇 点击下方卡片快速提问")
        for q in quick_questions:
            if st.button(q, use_container_width=True):
                st.session_state.prompt_input = q
                st.rerun()

    # 3. 聊天流渲染
    for msg in st.session_state.messages:
        avatar = "🦄" if msg["role"] == "assistant" else "🧑‍💻"
        with st.chat_message(msg["role"], avatar=avatar):
            st.write(msg["content"])

    # 4. 输入框
    user_input = st.chat_input("输入你的健康问题...")
    
    final_prompt = None
    if user_input:
        final_prompt = user_input
    elif st.session_state.prompt_input:
        final_prompt = st.session_state.prompt_input
        st.session_state.prompt_input = None

    if final_prompt:
        if not user_input:
            with st.chat_message("user", avatar="🧑‍💻"):
                st.write(final_prompt)
        st.session_state.messages.append({"role": "user", "content": final_prompt})

        with st.chat_message("assistant", avatar="🦄"):
            with st.spinner("正在思考..."):
                reply = get_ai_response(st.session_state.messages)
                st.write(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        
        if not user_input:
            st.rerun()