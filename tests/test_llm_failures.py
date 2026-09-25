from agora_ai_sdlc.llm_failures import recoverable_llm_failure


def test_quota_and_token_failures_are_recoverable():
    assert recoverable_llm_failure("The usage limit has been reached")
    assert recoverable_llm_failure("tokens exhausted")
    assert recoverable_llm_failure("quota exceeded")


def test_model_without_tool_support_is_recoverable():
    assert recoverable_llm_failure("registry.ollama.ai/library/qwen2.5-coder:1.5b-base does not support tools")


def test_transient_provider_outages_are_recoverable():
    assert recoverable_llm_failure(
        "Streaming response failed: [503] Upstream error from Nvidia: Service temporarily overloaded"
    )
    assert recoverable_llm_failure("502 Bad Gateway")
    assert recoverable_llm_failure("504 Gateway Timeout")
    assert recoverable_llm_failure('error.type="server_error"')


def test_ordinary_agent_failure_is_not_recoverable():
    assert not recoverable_llm_failure("Tests failed because assertion expected 2 but got 3")


def test_provider_forbidden_word_uses_token_boundaries():
    assert recoverable_llm_failure("HTTP 403 Forbidden")
    assert recoverable_llm_failure("request forbidden by provider policy")
    assert not recoverable_llm_failure("forbidden_skips: [clarify-intent, implementation]")
    assert not recoverable_llm_failure('expected = {"mandatory_steps", "forbidden_skips"}')
