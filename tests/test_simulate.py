from web3 import Web3
from guard.simulate import Simulator

USER     = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"  # anvil account 0
ATTACKER = "0xa0Ee7A142d267C1f36714E4a8F75612F20a79720"  # anvil account 9
USER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"

w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))

def test_eth_transfer_diff_and_revert():
    sim = Simulator()
    before = w3.eth.get_balance(USER)

    tx = {
        "from": USER, "to": ATTACKER,
        "value": w3.to_wei(1, "ether"),
        "nonce": w3.eth.get_transaction_count(USER),
        "gas": 100000,
        "maxFeePerGas": w3.to_wei(2, "gwei"),
        "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
        "chainId": w3.eth.chain_id,
    }
    signed = w3.eth.account.sign_transaction(tx, USER_KEY)

    diff = sim.simulate(
        signed.raw_transaction,
        watch_addresses=[USER, ATTACKER],
        watch_tokens=[],
    )

    assert diff.success
    assert diff.eth_delta[ATTACKER] == w3.to_wei(1, "ether")
    assert w3.eth.get_balance(USER) == before
    print("OK:", diff)
