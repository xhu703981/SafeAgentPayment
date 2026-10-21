import time
from web3 import Web3
from eth_abi import encode
from eth_utils import keccak
from guard.simulate import Simulator

RPC = "http://127.0.0.1:8545"
w3 = Web3(Web3.HTTPProvider(RPC))

USER     = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
USER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
ATTACKER = "0xa0Ee7A142d267C1f36714E4a8F75612F20a79720"

USDC = Web3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")
MAX_UINT = 2**256 - 1

ERC20 = [
    {"name": "balanceOf", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "o", "type": "address"}], "outputs": [{"type": "uint256"}]},
    {"name": "allowance", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "o", "type": "address"}, {"name": "s", "type": "address"}],
     "outputs": [{"type": "uint256"}]},
    {"name": "approve", "type": "function", "stateMutability": "nonpayable",
     "inputs": [{"name": "s", "type": "address"}, {"name": "v", "type": "uint256"}],
     "outputs": [{"type": "bool"}]},
]


def _rpc(method, params):
    r = w3.provider.make_request(method, params)
    assert "error" not in r, r
    return r


def set_usdc_balance(addr, amount, slot=9):
    """directly write the balance mapping slot. Base USDC uses balance slot 9."""
    key = keccak(encode(["address", "uint256"], [addr, slot]))
    _rpc("anvil_setStorageAt",
         [USDC, "0x" + key.hex(), "0x" + encode(["uint256"], [amount]).hex()])


def test_approve_shows_up_in_diff():
    sim = Simulator(RPC)
    usdc = w3.eth.contract(address=USDC, abi=ERC20)

    set_usdc_balance(USER, 1000 * 10**6)
    bal = usdc.functions.balanceOf(USER).call()
    assert bal == 1000 * 10**6, f"balance set failed, got {bal} (slot may be wrong)"

    tx = usdc.functions.approve(ATTACKER, MAX_UINT).build_transaction({
        "from": USER,
        "nonce": w3.eth.get_transaction_count(USER),
        "chainId": w3.eth.chain_id,
        "gas": 100000,
        "maxFeePerGas": w3.to_wei(1, "gwei"),
        "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
    })
    signed = w3.eth.account.sign_transaction(tx, USER_KEY)

    diff = sim.simulate(signed.raw_transaction,
                        watch_addresses=[USER, ATTACKER],
                        watch_tokens=[USDC])

    assert diff.success
    assert diff.token_delta == {}, "balance should not change on approve"
    assert len(diff.new_approvals) == 1
    ap = diff.new_approvals[0]
    assert ap["spender"] == ATTACKER
    assert ap["amount"] == MAX_UINT
    print("OK p04 visible:", ap)

    N = 10
    t0 = time.time()
    for _ in range(N):
        sim.simulate(signed.raw_transaction, [USER, ATTACKER], [USDC])
    print(f"avg simulate: {(time.time()-t0)/N*1000:.1f} ms")
