from core.settings import settings


def test_settings_defaults():
    assert settings.PROJECT_NAME == "YiTianLearningCosmos"
    assert settings.CLIENT_WEB_PORT == 8030
    # 默认代理地址存在
    assert settings.FILE_PARSE_AGENT_URL.startswith("http://")
