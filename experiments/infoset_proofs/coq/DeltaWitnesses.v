(** The state-recall witness of [Witnesses] under the ruled semantics of
    [Delta]: seat 0's second decisions now carry the State Delta that tells
    the two deals apart, and [public_state_recall]'s premises hold of it. *)

From Coq Require Import List Arith.
Import ListNotations.
From Infoset Require Import Kernel Witnesses Delta.

Definition dstart (c : config) : dconfig :=
  {| dw := cw c; dlog := fun _ => []; dk := 0; dshown := None |}.

(** The witness's one State Variable is variable 0. *)
Definition vars : list var := [0].

Theorem state_recall_delta_remembers :
  exists a1 b1 a2 b2,
    snd (dexec decls sited vars first state_recall (dstart hi)) = [a1; b1] /\
    snd (dexec decls sited vars first state_recall (dstart lo)) = [a2; b2] /\
    dd_seat b1 = 0 /\ dd_seat b2 = 0 /\
    dd_log b1 <> dd_log b2.
Proof.
  do 4 eexists; split; [reflexivity|]; split; [reflexivity|].
  repeat split; simpl; discriminate.
Qed.

(** And the theorem applies to it: seat 0's second decision rewinds to the
    public state of its first. *)
Corollary state_recall_delta_recalls : forall a b,
  snd (dexec decls sited vars first state_recall (dstart hi)) = [a; b] ->
  recalls vars a b.
Proof.
  intros a b H.
  apply (public_state_recall decls sited vars first state_recall (dstart hi) [] a [] b []);
    [reflexivity | rewrite H; reflexivity |].
  simpl in H; injection H as <- <-; reflexivity.
Qed.
