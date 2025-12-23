from msgspec import convert


def test_bilibili_dynamic_opus_title_exposed():
    """Ensure dynamic(opus) title isn't dropped."""
    from nonebot_plugin_parser.parsers.bilibili.dynamic import DynamicMajor

    major = convert(
        {
            "type": "MAJOR_TYPE_OPUS",
            "opus": {
                "jump_url": "https://www.bilibili.com/opus/1149443650602663937",
                "pics": [],
                "summary": {"text": "hello"},
                "title": "动态标题",
            },
        },
        DynamicMajor,
    )
    assert major.title == "动态标题"

