from openai import OpenAI
from app.common.exceptions import BusinessException
from app.config import settings
from app.schemas.ai import ChatMessage, ChatRequest

SYSTEM_PROMPT = """你是智能实验室预约系统的助手，回答要简洁。
你可以介绍本系统的预约流程：
1. 登录后打开实验室列表，选择实验室或设备
2. 填写日期和时段并提交，状态为待审核
3. 管理员审核通过后即可使用
4. 待审核、已通过的预约，本人可以取消

你目前查不到真实的实验室、设备、预约数据。
如果用户问某个实验室几点开门、有没有某台设备，请说明去「实验室列表」查看，不要编造具体数据。
如果用户问了跟实验室无关的问题，可以直接拒绝回答。
"""


def get_client() -> OpenAI:
    """创建OPENAI的客户端"""
    if not settings.LLM_API_KEY:
        raise BusinessException(message="未获取到大模型的API Key")
    return OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)


def chat(data: ChatRequest):
    """大模型对话"""
    if not data.messages:
        raise BusinessException(message="对话内容为空")
    history = []
    for message in data.messages:
        if message.role in ("user", "assistant") and message.content.strip():
            history.append(message)
    if not history:
        raise BusinessException(message="请输入您要对话的内容")

    client = get_client()

    try:
        res = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                ChatMessage(role="assistant", content=SYSTEM_PROMPT),
                *history,
            ],
        )
        content = res.choices[0].message.content
        if not content.strip():
            raise BusinessException(message="大模型没有返回内容")
        return content
    except BusinessException:
        raise  # 业务异常原样抛出，不要被下面的兜底吞掉
    except Exception:
        raise BusinessException(message="大模型调用失败, 请稍后重试")
