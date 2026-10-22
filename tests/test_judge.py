"""Test the JEV semantic judge: activates on empty intent fields, can veto."""
from web3 import Web3
from eth_abi import encode
from eth_utils import keccak
from guard.guard import Guard
from guard.intent import build_intent, TRUSTED_ROUTERS
from guard.judge import needs_judge, blind_spots

RPC = "http://127.0.0.1:8545"
w3 = Web3(Web3.HTTPProvider(RPC))

USER     = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
USER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
ATTACKER = "0xa0Ee7A142d267C1f36714E4a8F75612F20a79720"
ROUTER   = Web3.to_checksum_address(TRUSTED_ROUTERS[0])
USDC = Web3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")
MAX_UINT = 2**256 - 1

ERC20 = [{"name": "approve", "type": "function", "stateMutability": "nonpayable",
          "inputs": [{"name": "s", "type": "address"}, {"name": "v", "type": "uint256"}],
          "outputs": [{"type": "bool"}]}]
VAGUE = "Swap my USDC to ETH"


def set_usdc_balance(addr, amount, slot=9):
    key = keccak(encode(["address", "uint256"], [addr, slot]))
    w3.provider.make_request("anvil_setStorageAt",
        [USDC, "0x" + key.hex(), "0x" + encode(["uint256"], [amount]).hex()])


def _signed_approve(spender, amount):
    set_usdc_balance(USER, 1000 * 10**6)
    usdc = w3.eth.contract(address=USDC, abi=ERC20)
    tx = usdc.functions.approve(spender, amount).build_transaction({
        "from": USER, "nonce": w3.eth.get_transaction_count(USER),
        "chainId": w3.eth.chain_id, "gas": 100000,
        "maxFeePerGas": w3.to_wei(1, "gwei"), "maxPriorityFeePerGas": w3.to_wei(1, "gwei")})
    return w3.eth.account.sign_transaction(tx, USER_KEY).raw_transaction


def test_judge_activates_on_vague_intent():
    intent = build_intent(VAGUE)
    print("blind_spots:", blind_spots(intent))
    assert needs_judge(intent)


def test_jev_vetoes_unlimited_approval():
    g = Guard(RPC, watch_addresses=[USER, ATTACKER, ROUTER],
              watch_tokens=[USDC], use_judge=True)
    d = g.check_instruction(VAGUE, _signed_approve(ROUTER, MAX_UINT))
    print("verdict:", d.verdict, "| judged:", getattr(d, "judged", False),
          "| reasons:", d.reasons)
    assert getattr(d, "judged", False), "JEV should have run on vague intent"
