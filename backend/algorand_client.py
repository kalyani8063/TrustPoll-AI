import base64
import os
from typing import Any

from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod, indexer


class AlgorandGovernanceClient:
    def __init__(self) -> None:
        self.algod = algod.AlgodClient(
            algod_token=os.getenv("ALGORAND_ALGOD_TOKEN", ""),
            algod_address=os.getenv("ALGORAND_ALGOD_ADDRESS", ""),
            headers={"X-API-Key": os.getenv("ALGORAND_ALGOD_TOKEN", "")},
        )
        self.indexer = None
        if os.getenv("ALGORAND_INDEXER_ADDRESS"):
            self.indexer = indexer.IndexerClient(
                indexer_token=os.getenv("ALGORAND_INDEXER_TOKEN", ""),
                indexer_address=os.getenv("ALGORAND_INDEXER_ADDRESS", ""),
                headers={"X-API-Key": os.getenv("ALGORAND_INDEXER_TOKEN", "")},
            )

        self.app_id = int(os.getenv("ALGORAND_APP_ID", "0"))
        if self.app_id <= 0:
            raise RuntimeError("ALGORAND_APP_ID must be set to a deployed application id")

        service_mnemonic = os.getenv("ALGORAND_SERVICE_MNEMONIC", "")
        if not service_mnemonic:
            raise RuntimeError("ALGORAND_SERVICE_MNEMONIC is required")
        self.private_key = mnemonic.to_private_key(service_mnemonic)
        self.sender = account.address_from_private_key(self.private_key)
        self.timeout_rounds = int(os.getenv("ALGORAND_TX_TIMEOUT_ROUNDS", "12"))

    @staticmethod
    def _box_key(email_hash_hex: str) -> bytes:
        return b"voter_" + bytes.fromhex(email_hash_hex)

    @staticmethod
    def _u64(value: int) -> bytes:
        return int(value).to_bytes(8, "big")

    def wait_for_confirmation(self, tx_id: str, timeout_rounds: int | None = None) -> dict[str, Any]:
        timeout = timeout_rounds if timeout_rounds is not None else self.timeout_rounds
        start_round = self.algod.status()["last-round"] + 1
        current_round = start_round
        while current_round < start_round + timeout:
            pending_txn = self.algod.pending_transaction_info(tx_id)
            confirmed_round = pending_txn.get("confirmed-round", 0)
            if confirmed_round > 0:
                return pending_txn
            pool_error = pending_txn.get("pool-error")
            if pool_error:
                raise RuntimeError(f"Transaction rejected: {pool_error}")
            self.algod.status_after_block(current_round)
            current_round += 1
        raise TimeoutError(f"Transaction not confirmed after {timeout} rounds")

    def cast_vote(self, email_hash_hex: str, candidate_id: int) -> dict[str, int | str]:
        sp = self.algod.suggested_params()
        app_args = [b"cast_vote", bytes.fromhex(email_hash_hex), self._u64(candidate_id)]
        boxes = [(self.app_id, self._box_key(email_hash_hex))]
        txn = transaction.ApplicationNoOpTxn(
            sender=self.sender,
            sp=sp,
            index=self.app_id,
            app_args=app_args,
            boxes=boxes,
        )
        signed = txn.sign(self.private_key)
        tx_id = self.algod.send_transaction(signed)
        pending = self.wait_for_confirmation(tx_id)
        confirmed_round = int(pending.get("confirmed-round", 0))
        block_info = self.algod.block_info(confirmed_round)
        block_timestamp = int(block_info["block"]["ts"])
        return {
            "tx_id": tx_id,
            "confirmed_round": confirmed_round,
            "block_timestamp": block_timestamp,
        }

    def _decode_global_state(self, app_state: list[dict[str, Any]]) -> dict[bytes, int | bytes]:
        decoded: dict[bytes, int | bytes] = {}
        for entry in app_state:
            key = base64.b64decode(entry["key"])
            value = entry["value"]
            if value["type"] == 2:
                decoded[key] = int(value.get("uint", 0))
            elif value["type"] == 1:
                decoded[key] = base64.b64decode(value.get("bytes", ""))
        return decoded

    def get_candidate_counts(self, candidate_ids: list[int]) -> dict[int, int]:
        app_info = self.algod.application_info(self.app_id)
        global_state = app_info["params"].get("global-state", [])
        decoded = self._decode_global_state(global_state)
        result: dict[int, int] = {}
        for cid in candidate_ids:
            key_binary = b"cand_" + int(cid).to_bytes(8, "big")
            key_legacy_1 = f"candidate_{cid}_count".encode("utf-8")
            key_legacy_2 = f"cand_{cid}".encode("utf-8")
            value = decoded.get(key_binary)
            if value is None:
                value = decoded.get(key_legacy_1)
            if value is None:
                value = decoded.get(key_legacy_2)
            result[cid] = int(value) if isinstance(value, int) else 0
        return result

    def _lookup_tx(self, tx_id: str) -> dict[str, Any]:
        if self.indexer:
            resp = self.indexer.search_transactions(txid=tx_id)
            txns = resp.get("transactions", [])
            if txns:
                return txns[0]
        pending = self.algod.pending_transaction_info(tx_id)
        if pending:
            return pending
        raise ValueError("Transaction not found on configured clients")

    def verify_vote_transaction(self, tx_id: str) -> dict[str, Any]:
        tx = self._lookup_tx(tx_id)
        is_indexer = "tx-type" in tx
        if is_indexer:
            tx_type = tx.get("tx-type")
            app_txn = tx.get("application-transaction", {})
            app_id = app_txn.get("application-id")
            confirmed_round = int(tx.get("confirmed-round", 0))
            round_time = int(tx.get("round-time", 0))
            args = app_txn.get("application-args", [])
            first_arg = base64.b64decode(args[0]).decode("utf-8") if args else ""
            success = tx_type == "appl" and app_id == self.app_id and confirmed_round > 0 and first_arg in ("cast_vote", "vote")
            return {
                "status": "SUCCESS" if success else "FAILED",
                "application_call": tx_type == "appl",
                "app_id": app_id,
                "confirmed_round": confirmed_round,
                "timestamp": round_time,
            }

        txn = tx.get("txn", {})
        txn_type = txn.get("txn", {}).get("type")
        app_id = txn.get("txn", {}).get("apid")
        confirmed_round = int(tx.get("confirmed-round", 0))
        first_arg_raw = txn.get("txn", {}).get("apaa", [])
        first_arg = base64.b64decode(first_arg_raw[0]).decode("utf-8") if first_arg_raw else ""
        block_timestamp = 0
        if confirmed_round > 0:
            block_info = self.algod.block_info(confirmed_round)
            block_timestamp = int(block_info["block"]["ts"])
        success = txn_type == "appl" and app_id == self.app_id and confirmed_round > 0 and first_arg in ("cast_vote", "vote")
        return {
            "status": "SUCCESS" if success else "FAILED",
            "application_call": txn_type == "appl",
            "app_id": app_id,
            "confirmed_round": confirmed_round,
            "timestamp": block_timestamp,
        }

    def anchor_note_hash(self, digest_hex: str) -> dict[str, int | str]:
        sp = self.algod.suggested_params()
        note_bytes = digest_hex.encode("utf-8")
        txn = transaction.PaymentTxn(
            sender=self.sender,
            sp=sp,
            receiver=self.sender,
            amt=0,
            note=note_bytes,
        )
        signed = txn.sign(self.private_key)
        tx_id = self.algod.send_transaction(signed)
        pending = self.wait_for_confirmation(tx_id)
        confirmed_round = int(pending.get("confirmed-round", 0))
        return {"tx_id": tx_id, "confirmed_round": confirmed_round}

    def fetch_note_text(self, tx_id: str) -> str | None:
        tx = self._lookup_tx(tx_id)
        if "note" in tx:
            return base64.b64decode(tx["note"]).decode("utf-8")
        txn_node = tx.get("txn", {}).get("txn", {})
        note_b64 = txn_node.get("note")
        if note_b64:
            return base64.b64decode(note_b64).decode("utf-8")
        return None
