(** The two witness games, transcribed into the calculus of [Kernel], each
    with the theorem that shows what it does to the information partition.

    Zones, as `ControlBranch` and `StateRecall` declare them:
    0 the deck (count to all), 1 seat 0's hand and 2 seat 1's hand (identity to
    the owner, count to the other), 3 the table (identity to all). *)

From Coq Require Import List Arith Bool Lia Permutation.
Import ListNotations.
From Infoset Require Import Kernel.

Definition decls (z : zone) : zdecl :=
  match z with
  | 0 => {| z_owner := None; z_owner_level := CountOnly; z_others_level := CountOnly |}
  | 1 => {| z_owner := Some 0; z_owner_level := Identity; z_others_level := CountOnly |}
  | 2 => {| z_owner := Some 1; z_owner_level := Identity; z_others_level := CountOnly |}
  | _ => {| z_owner := None; z_owner_level := Identity; z_others_level := Identity |}
  end.

(** The engine's ask: one phase, one construct, one count, one destination,
    so every site of the witness's phase says the same thing. *)
Definition coarse (_ : nat) : nat := 0.
Definition sited (site : nat) : nat := site.

(** Seat 1 holds one card, a high one in world [hi] and a low one in [lo];
    nothing else differs. Card 9 has rank 9, card 3 rank 3. *)
Definition start (hidden : card) : config :=
  {| cw := {| contents := fun z => match z with 1 => [3; 9] | 2 => [hidden] | _ => [] end;
              pub := fun _ => 0 |};
     clog := fun _ => [];
     ck := 0 |}.

Definition hi := start 10.
Definition lo := start 4.

Definition first : oracle := fun _ L => hd 0 L.

Lemma hi_lo_look_alike : view_eq decls 0 (cw hi) (cw lo).
Proof.
  split; [|reflexivity].
  intros [|[|[|z]]]; simpl; auto using Permutation_refl.
Qed.

(** ---------------------------------------------------------------------- *)
(** `tests/fixtures/blind_decisions/control_branch.cardlang` (issue #755):
    a branch on seat 1's hidden card picks which menu seat 0 is offered. *)

Definition control_branch : stmt :=
  SIf (BLe (XConst 1) (XCountRankGe 2 8))
      (SChoose 1 0 1 3 (GRankGe 2))
      (SChoose 2 0 1 3 (GRankGe 8)).

Lemma control_branch_checked : checked decls control_branch.
Proof.
  split; simpl.
  - repeat constructor.
  - repeat constructor; simpl; intuition discriminate.
Qed.

(** It passes every check the menu positions carry, and with the engine's ask
    seat 0 has one information set offering two menus: OpenSpiel's
    requirement fails. *)
Theorem control_branch_breaks_agreement :
  exists d1 d2,
    In d1 (snd (exec decls coarse false first control_branch hi)) /\
    In d2 (snd (exec decls coarse false first control_branch lo)) /\
    d_seat d1 = 0 /\ d_seat d2 = 0 /\
    info_eq decls 0 d1 d2 /\
    ~ Permutation (d_legal d1) (d_legal d2).
Proof.
  do 2 eexists; split; [simpl; left; reflexivity|].
  split; [simpl; left; reflexivity|].
  repeat split; simpl.
  - intros [|[|[|z]]]; simpl; auto using Permutation_refl.
  - intro H; apply Permutation_length in H; simpl in H; discriminate.
Qed.

(** With an ask that names its site, the same two worlds are told apart:
    agreement holds (Theorem [legal_agreement]), and seat 0 has learned which
    branch ran — a fact about seat 1's hidden card. *)
Theorem sited_ask_reveals_branch :
  forall d1 d2,
    In d1 (snd (exec decls sited false first control_branch hi)) ->
    In d2 (snd (exec decls sited false first control_branch lo)) ->
    ~ info_eq decls 0 d1 d2.
Proof.
  intros d1 d2 H1 H2 [_ Hlog]; simpl in H1, H2.
  destruct H1 as [<-|[]]; destruct H2 as [<-|[]]; simpl in Hlog; discriminate.
Qed.

(** ---------------------------------------------------------------------- *)
(** `experiments/infoset_proofs/witnesses/state_recall.cardlang`: a state
    variable carries a fact about seat 1's hidden card to seat 0's first
    decision, and is overwritten before its second. *)

Definition state_recall : stmt :=
  SSeq (SAssign 0 (XCountRankGe 2 8))
 (SSeq (SChoose 1 0 1 3 GTrue)
 (SSeq (SAssign 0 (XConst 0))
       (SChoose 2 0 1 3 GTrue))).

Lemma state_recall_checked : checked decls state_recall.
Proof.
  split; simpl.
  - repeat constructor.
  - repeat constructor; simpl; intuition discriminate.
Qed.

(** With the engine's unlogged assignment, seat 0 tells the worlds apart at its
    first decision and not at its second, though both runs made the same
    picks: one information set at the second decision holds two different
    first-decision information sets, which is imperfect recall. This holds
    with the sited ask too. *)
Theorem state_recall_forgets :
  exists a1 a2 b1 b2,
    snd (exec decls sited false first state_recall hi) = [a1; b1] /\
    snd (exec decls sited false first state_recall lo) = [a2; b2] /\
    d_pick a1 = d_pick a2 /\
    ~ info_eq decls 0 a1 a2 /\
    info_eq decls 0 b1 b2.
Proof.
  do 4 eexists; split; [reflexivity|]; split; [reflexivity|].
  split; [reflexivity|]. split.
  - intros [[_ Hp] _]; specialize (Hp 0); simpl in Hp; discriminate.
  - split; [split|reflexivity].
    + intros [|[|[|[|z]]]]; simpl; auto using Permutation_refl.
    + intros [|x]; reflexivity.
Qed.

(** Logging the assignment restores it: the second decisions' logs differ. *)
Theorem state_recall_logged_remembers :
  forall b1 b2,
    In b1 (snd (exec decls sited true first state_recall hi)) ->
    In b2 (snd (exec decls sited true first state_recall lo)) ->
    d_site b1 = 2 -> d_site b2 = 2 ->
    ~ info_eq decls 0 b1 b2.
Proof.
  intros b1 b2 H1 H2 S1 S2 [_ Hlog]; simpl in H1, H2.
  destruct H1 as [<-|[<-|[]]]; try discriminate;
  destruct H2 as [<-|[<-|[]]]; try discriminate; simpl in Hlog; discriminate.
Qed.

(** [legal_agreement]'s premises hold of the witness under the sited ask, so
    the theorem is not vacuous there: every pair of seat 0's decisions, over
    every pair of starts and every pair of pick sequences, agrees. *)
Corollary control_branch_agrees_when_sited :
  forall o1 o2 c1 c2 d1 d2,
    In d1 (snd (exec decls sited false o1 control_branch c1)) ->
    In d2 (snd (exec decls sited false o2 control_branch c2)) ->
    d_seat d1 = 0 -> d_seat d2 = 0 -> info_eq decls 0 d1 d2 ->
    Permutation (d_legal d1) (d_legal d2).
Proof.
  intros o1 o2 c1 c2 d1 d2 H1 H2 S1 S2 Hi.
  eapply (legal_agreement decls sited false control_branch control_branch_checked);
    [intros a b _ _ E; exact E | exact H1 | exact H2 | exact S1 | exact S2 | exact Hi].
Qed.
