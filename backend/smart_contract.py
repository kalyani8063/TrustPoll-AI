from typing import Iterable

from pyteal import *


def _candidate_key_from_arg(arg_index: int) -> Expr:
    return Concat(Bytes("cand_"), Txn.application_args[arg_index])


def _candidate_key_literal(candidate_id: int) -> Expr:
    key_bytes = b"cand_" + int(candidate_id).to_bytes(8, "big")
    return Bytes("base16", key_bytes.hex())


def build_approval_program(candidate_ids: Iterable[int] | None = None) -> Expr:
    configured_ids = list(candidate_ids or [])

    deadline_key = Bytes("deadline")
    election_id_key = Bytes("election_id")
    admin_key = Bytes("admin")

    on_create = Seq(
        Assert(Txn.application_args.length() == Int(2)),
        App.globalPut(election_id_key, Txn.application_args[0]),
        App.globalPut(deadline_key, Btoi(Txn.application_args[1])),
        App.globalPut(admin_key, Txn.sender()),
        *[App.globalPut(_candidate_key_literal(cid), Int(0)) for cid in configured_ids],
        Approve(),
    )

    add_key = ScratchVar(TealType.bytes)
    add_exists = App.globalGetEx(Global.current_application_id(), add_key.load())
    add_candidate = Seq(
        Assert(Txn.application_args.length() == Int(2)),
        Assert(Txn.application_args[0] == Bytes("add_candidate")),
        Assert(Txn.sender() == App.globalGet(admin_key)),
        Assert(Len(Txn.application_args[1]) == Int(8)),
        add_key.store(_candidate_key_from_arg(1)),
        add_exists,
        Assert(Not(add_exists.hasValue())),
        App.globalPut(add_key.load(), Int(0)),
        Approve(),
    )

    vote_key = ScratchVar(TealType.bytes)
    vote_exists = App.globalGetEx(Global.current_application_id(), vote_key.load())
    voter_box_name = ScratchVar(TealType.bytes)
    voter_exists = BoxLen(voter_box_name.load())
    candidate_id = ScratchVar(TealType.uint64)
    vote = Seq(
        Assert(Txn.application_args.length() == Int(3)),
        Assert(Txn.application_args[0] == Bytes("vote")),
        Assert(Len(Txn.application_args[1]) == Int(32)),
        Assert(Len(Txn.application_args[2]) == Int(8)),
        Assert(Global.latest_timestamp() < App.globalGet(deadline_key)),
        voter_box_name.store(Concat(Bytes("voter_"), Txn.application_args[1])),
        voter_exists,
        Assert(Not(voter_exists.hasValue())),
        candidate_id.store(Btoi(Txn.application_args[2])),
        Assert(candidate_id.load() > Int(0)),
        vote_key.store(_candidate_key_from_arg(2)),
        vote_exists,
        Assert(vote_exists.hasValue()),
        App.globalPut(vote_key.load(), vote_exists.value() + Int(1)),
        BoxPut(voter_box_name.load(), Bytes("1")),
        Approve(),
    )

    return Cond(
        [Txn.application_id() == Int(0), on_create],
        [
            Txn.on_completion() == OnComplete.NoOp,
            Cond(
                [Txn.application_args[0] == Bytes("add_candidate"), add_candidate],
                [Txn.application_args[0] == Bytes("vote"), vote],
            ),
        ],
        [Txn.on_completion() == OnComplete.OptIn, Reject()],
        [Txn.on_completion() == OnComplete.CloseOut, Reject()],
        [Txn.on_completion() == OnComplete.UpdateApplication, Reject()],
        [Txn.on_completion() == OnComplete.DeleteApplication, Reject()],
    )


def build_clear_program() -> Expr:
    return Approve()


def compile_contract(candidate_ids: Iterable[int] | None = None) -> tuple[str, str]:
    approval = compileTeal(
        build_approval_program(candidate_ids),
        mode=Mode.Application,
        version=8,
    )
    clear = compileTeal(
        build_clear_program(),
        mode=Mode.Application,
        version=8,
    )
    return approval, clear


if __name__ == "__main__":
    approval_teal, clear_teal = compile_contract([1, 2, 3])
    print(approval_teal)
    print(clear_teal)
