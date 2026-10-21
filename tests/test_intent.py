from guard.intent import build_intent, TRUSTED_ROUTERS, USER_ADDRESS


def test_swap_intent():
    intent = build_intent("Swap 100 USDC to ETH")
    print("intent:", intent)

    assert intent["action"] == "swap"
    assert intent["sell"]["token"] == "USDC"
    # 100 USDC in 6-decimal base units
    assert intent["sell"]["max_amount"] == 100 * 10**6
    # addresses come from config, NOT from the LLM
    assert intent["allowed_spenders"] == TRUSTED_ROUTERS
    assert USER_ADDRESS in intent["allowed_recipients"]
