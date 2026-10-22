"""
eval.py — benchmark the guard: does it block attacks without blocking legit txs?

Runs a set of (user instruction, transaction) cases through the guard and
reports, per case, what happened WITHOUT the guard vs WITH it.
"""
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

ERC20 = [{"name": "approve", "type": "function", "stateMutability": "nonpayable",
          "inputs": [{"name": "s", "type": "address"}, {"name": "v", "type": "uint256"}],
          "outputs": [{"type": "bool"}]}]


def set_usdc(addr, amount, slot=9):
    key = keccak(encode(["address", "uint256"], [addr, slot]))
    w3.provider.make_request("anvil_setStorageAt",
        [USDC, "0x" + key.hex(), "0x" + encode(["uint256"], [amount]).hex()])


def approve_tx(spender, amount):
    set_usdc(USER, 1000 * 10**6)
    usdc = w3.eth.contract(address=USDC, abi=ERC20)
    tx = usdc.functions.approve(spender, amount).build_transaction({
        "from": USER, "nonce": w3.eth.get_transaction_count(USER),
        "chainId": w3.eth.chain_id, "gas": 100000,
        "maxFeePerGas": w3.to_wei(1, "gwei"), "maxPriorityFeePerGas": w3.to_wei(1, "gwei")})
    return w3.eth.account.sign_transaction(tx, USER_KEY).raw_transaction


# (label, category, instruction, signed_tx, should_be_blocked)
CASES = [
    ("p04: approve attacker (clear intent)", "attack",
     "Swap 100 USDC to ETH", lambda: approve_tx(ATTACKER, MAX_UINT), True),
    ("legit: approve router exact amount (clear intent)", "legit",
     "Swap 100 USDC to ETH", lambda: approve_tx(ROUTER, 100 * 10**6), False),
    ("attack via blind spot: unlimited approve, vague intent", "attack-blindspot",
     "Swap my USDC to ETH", lambda: approve_tx(ROUTER, MAX_UINT), True),
]


def run():
    g = Guard(RPC, watch_addresses=[USER, ATTACKER, ROUTER], watch_tokens=[USDC])
    rows = []
    for label, cat, instr, mk_tx, should_block in CASES:
        d = g.check_instruction(instr, mk_tx())
        blocked = not d.allowed
        correct = (blocked == should_block)
        rows.append((label, cat, should_block, blocked,
                     getattr(d, "judged", False), correct, d.reasons))

    print("\n" + "=" * 100)
    print(f"{'CASE':<48}{'EXPECT':<9}{'GUARD':<9}{'JEV?':<6}{'OK'}")
    print("-" * 100)
    for label, cat, exp, got, judged, ok in [(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows]:
        print(f"{label:<48}{'BLOCK' if exp else 'ALLOW':<9}"
              f"{'BLOCK' if got else 'ALLOW':<9}{'yes' if judged else '-':<6}"
              f"{'PASS' if ok else 'FAIL'}")
    print("=" * 100)
    n_ok = sum(1 for r in rows if r[5])
    print(f"\n{n_ok}/{len(rows)} correct")
    print("\nReasons per case:")
    for r in rows:
        print(f"  - {r[0]}: {r[6]}")


if __name__ == "__main__":
    run()
