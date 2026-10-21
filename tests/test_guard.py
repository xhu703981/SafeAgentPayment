from web3 import Web3
from eth_abi import encode
from eth_utils import keccak
from guard.guard import Guard
from guard.intent import TRUSTED_ROUTERS

RPC = "http://127.0.0.1:8545"
w3 = Web3(Web3.HTTPProvider(RPC))

USER     = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
USER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
ATTACKER = "0xa0Ee7A142d267C1f36714E4a8F75612F20a79720"
ROUTER   = Web3.to_checksum_address(TRUSTED_ROUTERS[0])

USDC = Web3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")
MAX_UINT = 2**256 - 1

ERC20 = [
    {"name": "approve", "type": "function", "stateMutability": "nonpayable",
     "inputs": [{"name": "s", "type": "address"}, {"name": "v", "type": "uint256"}],
     "outputs": [{"type": "bool"}]},
]
INSTRUCTION = "Swap 100 USDC to ETH"


def _signed_approve(spender):
    set_usdc_balance(USER, 1000 * 10**6)
    usdc = w3.eth.contract(address=USDC, abi=ERC20)
    tx = usdc.functions.approve(spender, MAX_UINT).build_transaction({
        "from": USER, "nonce": w3.eth.get_transaction_count(USER),
        "chainId": w3.eth.chain_id, "gas": 100000,
        "maxFeePerGas": w3.to_wei(1, "gwei"),
        "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
    })
    return w3.eth.account.sign_transaction(tx, USER_KEY).raw_transaction


def set_usdc_balance(addr, amount, slot=9):
    key = keccak(encode(["address", "uint256"], [addr, slot]))
    w3.provider.make_request(
        "anvil_setStorageAt",
        [USDC, "0x" + key.hex(), "0x" + encode(["uint256"], [amount]).hex()])


def _guard():
    return Guard(RPC, watch_addresses=[USER, ATTACKER, ROUTER], watch_tokens=[USDC])


def test_end_to_end_blocks_p04():
    """same user words, malicious approve to attacker -> BLOCK"""
    d = _guard().check_instruction(INSTRUCTION, _signed_approve(ATTACKER))
    print("verdict:", d.verdict, "| reasons:", d.reasons)
    assert not d.allowed


def test_end_to_end_allows_legit():
    """same user words, legit approve to router -> ALLOW"""
    d = _guard().check_instruction(INSTRUCTION, _signed_approve(ROUTER))
    print("verdict:", d.verdict, "| reasons:", d.reasons)
    assert d.allowed, d.reasons
