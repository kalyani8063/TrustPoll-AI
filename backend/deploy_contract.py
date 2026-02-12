import os
from dotenv import load_dotenv
from algosdk import mnemonic, transaction
from algosdk.v2client import algod
from smart_contract import compile_contract
import base64

load_dotenv()

ALGOD_ADDRESS = os.getenv("ALGORAND_ALGOD_ADDRESS")
ALGOD_TOKEN = os.getenv("ALGORAND_ALGOD_TOKEN", "")
SERVICE_MNEMONIC = os.getenv("ALGORAND_SERVICE_MNEMONIC")
ELECTION_ID = os.getenv("ELECTION_ID", "default-election")
DEADLINE_TS = int(os.getenv("ELECTION_DEADLINE_TS", "1767139200"))
CANDIDATE_IDS = [int(x.strip()) for x in os.getenv("SMART_CONTRACT_CANDIDATE_IDS", "1,2,3").split(",") if x.strip()]
MAX_CANDIDATES = int(os.getenv("SMART_CONTRACT_MAX_CANDIDATES", "50"))
if MAX_CANDIDATES < len(CANDIDATE_IDS):
    raise ValueError("SMART_CONTRACT_MAX_CANDIDATES must be >= number of initial candidate ids")
if MAX_CANDIDATES + 3 > 64:
    raise ValueError("SMART_CONTRACT_MAX_CANDIDATES too high for Algorand global state limits")

headers = {"X-API-Key": ALGOD_TOKEN} if ALGOD_TOKEN else {}
client = algod.AlgodClient(ALGOD_TOKEN, ALGOD_ADDRESS, headers=headers)

private_key = mnemonic.to_private_key(SERVICE_MNEMONIC)

from algosdk import account
sender = account.address_from_private_key(private_key)


approval_teal, clear_teal = compile_contract(CANDIDATE_IDS)

approval_compiled = client.compile(approval_teal)
clear_compiled = client.compile(clear_teal)

approval_program = base64.b64decode(approval_compiled["result"])
clear_program = base64.b64decode(clear_compiled["result"])

sp = client.suggested_params()

txn = transaction.ApplicationCreateTxn(
    sender=sender,
    sp=sp,
    on_complete=transaction.OnComplete.NoOpOC,
    approval_program=approval_program,
    clear_program=clear_program,
    global_schema=transaction.StateSchema(
        num_uints=MAX_CANDIDATES + 1,
        num_byte_slices=2,
    ),
    local_schema=transaction.StateSchema(0, 0),
    app_args=[
        ELECTION_ID.encode("utf-8"),
        DEADLINE_TS.to_bytes(8, "big"),
    ],
)

signed_txn = txn.sign(private_key)
txid = client.send_transaction(signed_txn)

print("txid:", txid)

last_round = client.status()["last-round"]
while True:
    pending = client.pending_transaction_info(txid)
    if pending.get("confirmed-round", 0) > 0:
        print("confirmed_round:", pending["confirmed-round"])
        print("app_id:", pending["application-index"])
        break
    last_round += 1
    client.status_after_block(last_round)
