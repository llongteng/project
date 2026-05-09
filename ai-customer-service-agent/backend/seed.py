from database import engine, SessionLocal, Base
from models import (
    Ticket,
    Message,
    TicketStatus,
    TicketPriority,
    TicketCategory,
    MessageRole,
    KnowledgeBase,
)


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # ── Tickets ──
    if db.query(Ticket).count() == 0:
        _seed_tickets(db)
    else:
        print("Tickets already exist, skipping ticket seed.")

    # ── Knowledge base (always check & fill missing) ──
    _seed_knowledge_base(db)

    db.close()
    print("Seed check complete.")


def _seed_tickets(db):
    tickets_data = [
        {
            "ticket": Ticket(
                title="订单未收到货",
                customer_name="张三",
                customer_email="zhangsan@example.com",
                category=TicketCategory.ORDER,
                priority=TicketPriority.HIGH,
                status=TicketStatus.AI_PROCESSING,
            ),
            "messages": [
                Message(role=MessageRole.USER, content="我在3天前下的订单 #2024-8842，到现在还没有收到货，物流显示已签收但我没有收到，请帮我查一下。"),
                Message(role=MessageRole.SYSTEM, content="工单已创建，AI 正在分析问题。"),
                Message(role=MessageRole.AGENT, content="您好，非常抱歉给您带来不便。我已经查到您的订单 #2024-8842，物流信息显示由顺丰快递配送，运单号 SF1234567890。让我进一步核实配送情况，请您稍等。"),
            ],
        },
        {
            "ticket": Ticket(
                title="如何修改收货地址",
                customer_name="李四",
                customer_email="lisi@example.com",
                category=TicketCategory.PRODUCT,
                priority=TicketPriority.LOW,
                status=TicketStatus.PENDING,
            ),
            "messages": [
                Message(role=MessageRole.USER, content="我下单后发现收货地址填错了，怎么修改地址？订单还没发货。"),
                Message(role=MessageRole.SYSTEM, content="工单已创建，等待处理。"),
            ],
        },
        {
            "ticket": Ticket(
                title="申请退货退款",
                customer_name="王五",
                customer_email="wangwu@example.com",
                category=TicketCategory.REFUND,
                priority=TicketPriority.MEDIUM,
                status=TicketStatus.WAITING_USER,
            ),
            "messages": [
                Message(role=MessageRole.USER, content="收到的商品颜色和图片不一致，我要退货退款。订单号 #2024-9012。"),
                Message(role=MessageRole.SYSTEM, content="工单已创建，AI 正在分析问题。"),
                Message(role=MessageRole.AGENT, content="您好，很抱歉商品与描述不符。根据我们的退货政策，您可以在收到商品后7天内申请退货退款。请提供商品实物照片以便我们加快处理。"),
                Message(role=MessageRole.USER, content="好的，照片我稍后上传。"),
            ],
        },
        {
            "ticket": Ticket(
                title="账号被锁定无法登录",
                customer_name="赵六",
                customer_email="zhaoliu@example.com",
                category=TicketCategory.ACCOUNT,
                priority=TicketPriority.URGENT,
                status=TicketStatus.PENDING,
            ),
            "messages": [
                Message(role=MessageRole.USER, content="我的账号突然被锁定了，提示密码错误多次，但我根本没有输错密码，请立即帮我解锁！"),
                Message(role=MessageRole.SYSTEM, content="工单已创建，等待处理。"),
            ],
        },
        {
            "ticket": Ticket(
                title="客服态度投诉",
                customer_name="孙七",
                customer_email="sunqi@example.com",
                category=TicketCategory.COMPLAINT,
                priority=TicketPriority.HIGH,
                status=TicketStatus.ESCALATED,
            ),
            "messages": [
                Message(role=MessageRole.USER, content="昨天打客服电话等了40分钟才接通，接线员态度很差，直接挂了我电话，我要投诉！"),
                Message(role=MessageRole.SYSTEM, content="工单已创建，AI 正在分析问题。"),
                Message(role=MessageRole.AGENT, content="非常抱歉您遇到这样的体验。这不符合我们的服务标准。该问题已升级至人工客服主管处理。"),
                Message(role=MessageRole.SYSTEM, content="工单已升级至人工客服主管。主管李经理将在一个工作日内联系您。"),
            ],
        },
    ]

    for item in tickets_data:
        db.add(item["ticket"])
        db.flush()
        for msg in item["messages"]:
            msg.ticket_id = item["ticket"].id
            db.add(msg)

    db.commit()
    print("Tickets seeded successfully.")


KB_SEED_DATA = [
    {
        "title": "订单物流查询方法",
        "category": TicketCategory.ORDER,
        "content": "您可以在「我的订单」中点击对应订单查看物流详情。如物流长时间未更新，请提供订单号，我们将联系物流公司核实。通常配送时效为3-5个工作日，偏远地区可能延长至7个工作日。",
        "keywords": "物流,订单,查询,配送,发货,运单,快递,没收到,签收",
    },
    {
        "title": "如何修改收货地址",
        "category": TicketCategory.ORDER,
        "content": "如订单尚未发货，您可以在「我的订单」中找到对应订单，点击「修改地址」进行修改。如订单已发货，请联系客服并提供新地址，我们将尝试联系物流改派。注意：已发货订单改派可能产生额外费用。",
        "keywords": "修改,地址,收货,改地址,怎么,如何,改",
    },
    {
        "title": "退货退款流程说明",
        "category": TicketCategory.REFUND,
        "content": "您可在收到商品后7天内申请退货退款。流程：1）在「我的订单」中点击「申请退款」；2）填写退款原因并上传凭证照片；3）审核通过后按指引寄回商品；4）仓库签收后3-5个工作日退款到原支付账户。如商品存在质量问题，退货运费由商家承担。",
        "keywords": "退款,退货,退钱,申请退,流程,怎么退,如何退,退款流程,售后",
    },
    {
        "title": "商品质量问题处理",
        "category": TicketCategory.REFUND,
        "content": "如收到的商品存在质量问题（破损、与描述不符、功能故障等），请在签收后48小时内联系客服，并提供：1）订单号；2）清晰的问题照片或视频；3）问题描述。我们会根据情况为您办理换货或退款，运费由商家承担。",
        "keywords": "质量问题,破损,与描述不符,颜色,图片,坏了,换货,补偿,售后",
    },
    {
        "title": "账号登录与密码重置",
        "category": TicketCategory.ACCOUNT,
        "content": "如忘记密码，请在登录页点击「忘记密码」，通过注册邮箱或手机号接收验证码后重置密码。如未收到验证码，请检查垃圾邮件箱或确认手机号是否正确。重置后建议使用强密码（大小写字母+数字+特殊符号，8位以上）。",
        "keywords": "账号,登录,密码,忘记,重置,验证码,邮箱,手机",
    },
    {
        "title": "账号锁定与安全验证",
        "category": TicketCategory.ACCOUNT,
        "content": "账号因多次密码错误被锁定后，会在30分钟后自动解锁。如需立即解锁，请通过注册邮箱发送邮件至 security@example.com，标题写明「账号解锁+您的用户名」。为确保账号安全，解锁后建议立即修改密码并绑定手机号。如怀疑账号被盗，请立即联系客服。",
        "keywords": "账号,锁定,解锁,安全,被封,密码错误,验证,绑定",
    },
    {
        "title": "客服投诉处理流程",
        "category": TicketCategory.COMPLAINT,
        "content": "我们非常重视您的反馈。投诉处理流程：1）客服记录投诉内容并生成工单；2）主管在1个工作日内审核并回复；3）如涉及严重服务问题，会升级至运营经理处理。您可以通过工单系统随时查看处理进度。我们承诺对所有投诉给予正式答复和改善措施。",
        "keywords": "投诉,态度,客服,处理,反馈,举报,315,消协",
    },
    {
        "title": "产品使用帮助",
        "category": TicketCategory.PRODUCT,
        "content": "产品使用文档和常见问题可在官网「帮助中心」查看。如未找到您需要的内容，请描述具体的使用场景和遇到的问题，客服将为您提供详细的操作指导。您也可以预约在线客服进行一对一远程演示。",
        "keywords": "怎么,如何,使用,说明书,功能,找不到,帮助,教程,在哪里",
    },
]


def _seed_knowledge_base(db):
    existing_titles = {row[0] for row in db.query(KnowledgeBase.title).all()}
    added = 0
    for item in KB_SEED_DATA:
        if item["title"] in existing_titles:
            continue
        db.add(KnowledgeBase(**item))
        added += 1
    if added:
        db.commit()
        print(f"Seeded {added} missing knowledge base entries.")
    else:
        print("Knowledge base entries already complete, nothing to add.")


if __name__ == "__main__":
    seed()
