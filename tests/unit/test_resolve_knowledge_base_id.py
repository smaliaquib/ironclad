import main


def test_returns_empty_without_ssm_param(monkeypatch):
    monkeypatch.setattr(main, "KNOWLEDGE_BASE_SSM_PARAM", "")

    assert main._resolve_knowledge_base_id() == ""


def test_fetches_value_from_ssm(monkeypatch):
    class FakeSSMClient:
        def get_parameter(self, Name):
            assert Name == "/ironclad-dev/knowledge-base/id"
            return {"Parameter": {"Value": "KB123"}}

    monkeypatch.setattr(main, "KNOWLEDGE_BASE_SSM_PARAM", "/ironclad-dev/knowledge-base/id")
    monkeypatch.setattr(main.boto3, "client", lambda *args, **kwargs: FakeSSMClient())

    assert main._resolve_knowledge_base_id() == "KB123"


def test_returns_empty_when_ssm_lookup_fails(monkeypatch):
    class FailingSSMClient:
        def get_parameter(self, Name):
            raise RuntimeError("boom")

    monkeypatch.setattr(main, "KNOWLEDGE_BASE_SSM_PARAM", "/ironclad-dev/knowledge-base/id")
    monkeypatch.setattr(main.boto3, "client", lambda *args, **kwargs: FailingSSMClient())

    assert main._resolve_knowledge_base_id() == ""
