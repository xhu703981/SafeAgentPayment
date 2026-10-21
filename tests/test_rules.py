import time
from web3 import Web3
from eth_abi import encode
from eth_utils import keccak
from guard.simulate import Simulator
from guard.rules import check

RPC = "http://127.0.0.1:8545"
w3 = Web3(Web3.HTTPProvider(RPC))

USER     = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
USER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
ATTACKER = "0xa0Ee7A142d267C1f36714E4a8F75612F20a79720"
ROUTER   = "0x1111111111111111111111111111111111111111"  # a stand-in allowed spender

USDC = Web3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")
MAX_UINT = 2**256 - 1

ERC20 = [
    {"name": "balanceOf", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "o", "type": "address"}], "outputs": [{"type": "uint256"}]},
    {"name": "approve", "type": "function", "stateMutability": "nonpayable",
     "inputs": [{"name": "s", "type": "address"}, {"name": "v", "type": "uint256"}],
     "outputs": [{"type": "bool"}]},
]


def set_usdc_balance(addr, amount, slot=9):
    key = keccak(encode(["address", "uint256"], [addr, slot]))
    w3.provider.make_request(
        "anvil_setStorageAt",
        [USDC, "0x" + key.hex(), "0x" + encode(["uint256"], [amount]).hex()])


def _approve_diff(spender):
    sim = Simulator(RPC)
    usdc = w3.eth.contract(address=USDC, abi=ERC20)
    set_usdc_balance(USER, 1000 * 10**6)
    tx = usdc.functions.approve(spender, MAX_UINT).build_transaction({
        "from": USER, "nonce": w3.eth.get_transaction_count(USER),
        "chainId": w3.eth.chain_id, "gas": 100000,
        "maxFeePerGas": w3.to_wei(1, "gwei"),
        "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
    })
    signed = w3.eth.account.sign_transaction(tx, USER_KEY)
    return sim.simulate(signed.raw_transaction,
                        [USER, ATTACKER, Web3.to_checksum_address(ROUTER)],
                        [USDC])


def test_p04_blocked():
    """approve to attacker -> BLOCK"""
    intent = {"allowed_spenders": [ROUTER], "allowed_recipients": [USER]}
    diff = _approve_diff(ATTACKER)
    d = check(intent, diff)
    assert not d.allowed, "should block approval to attacker"
    print("p04 BLOCKED, reasons:", d.reasons)


def test_legit_approve_allowed():
    """approve to the allowed router -> ALLOW"""
    intent = {"allowed_spenders": [ROUTER], "allowed_recipients": [USER]}
    diff = _approve_diff(ROUTER)
    d = check(intent, diff)
    assert d.allowed, f"should allow approval to router, but blocked: {d.reasons}"
    print("legit approve ALLOWED")
