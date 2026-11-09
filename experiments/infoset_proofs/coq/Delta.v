(** The ruled fix for issue #1041, in the calculus of [Kernel]: at every
    decision node every seat receives a State Delta, one [EWas x v] per
    declared variable whose value changed since the previous decision node,
    carrying the value it had there. Assignments emit nothing.

    The theorem: a seat's log fixes the public state at each of its earlier
    decisions. Rewinding the public state of a later decision through the
    log's [EWas] events, newest first, lands on the public state of the
    earlier one. Its corollary is the public half of perfect recall: two
    decisions of one seat in one information set, and two earlier decisions
    of that seat with the same log, saw the same public state. *)

From Coq Require Import List Arith Bool Lia.
Import ListNotations.
From Infoset Require Import Kernel.

Inductive devent :=
| DBase (e : event)
| DWas (x : var) (v : nat).

Record dconfig := {
  dw : world;
  dlog : seat -> list devent;
  dk : nat;
  dshown : option (var -> nat)
}.

Record ddecision := {
  dd_seat : seat;
  dd_world : world;
  dd_log : list devent;
  dd_legal : list card
}.

Section DeltaSemantics.

Variable decls : zone -> zdecl.
Variable ask_names : nat -> nat.
(** The declared State Variables. *)
Variable vars : list var.

Definition dtell (q : seat) (e : devent) (lg : seat -> list devent) : seat -> list devent :=
  fun p => if Nat.eqb p q then e :: lg p else lg p.

Definition dtell_all (f : seat -> devent) (lg : seat -> list devent) : seat -> list devent :=
  fun p => f p :: lg p.

(** The State Delta of a node whose public state is [now], after a node that
    showed [old]: newest first, like every log. *)
Definition changed (old now : var -> nat) (x : var) : bool := negb (old x =? now x).

Definition delta (old now : var -> nat) : list devent :=
  map (fun x => DWas x (old x)) (filter (changed old now) vars).

Definition deliver_delta (shown : option (var -> nat)) (now : var -> nat)
    (lg : seat -> list devent) : seat -> list devent :=
  match shown with
  | None => lg
  | Some old => fun p => delta old now ++ lg p
  end.

Fixpoint dexec (o : oracle) (s : stmt) (c : dconfig) : dconfig * list ddecision :=
  match s with
  | SSkip => (c, [])
  | SSeq s1 s2 =>
      let (c1, d1) := dexec o s1 c in
      let (c2, d2) := dexec o s2 c1 in
      (c2, d1 ++ d2)
  | SIf b s1 s2 => if beval (dw c) b then dexec o s1 c else dexec o s2 c
  | SDeal src dst =>
      match contents (dw c) src with
      | [] => (c, [])
      | x :: _ =>
          ({| dw := move_card (dw c) src dst x;
              dlog := dtell_all (fun p => DBase (move_event decls p src dst x)) (dlog c);
              dk := dk c; dshown := dshown c |}, [])
      end
  | SChoose site q src dst g =>
      let w := dw c in
      let L := filter (geval w g) (contents w src) in
      match L with
      | [] => (c, [])
      | _ :: _ =>
          let lg0 := deliver_delta (dshown c) (pub w) (dlog c) in
          let lg1 := dtell q (DBase (EAsked (ask_names site))) lg0 in
          let x := pick o (dk c) L in
          let lg2 := dtell q (DBase (EChose x)) lg1 in
          let lg3 := dtell_all (fun p => DBase (move_event decls p src dst x)) lg2 in
          ({| dw := move_card w src dst x; dlog := lg3; dk := S (dk c);
              dshown := Some (pub w) |},
           [ {| dd_seat := q; dd_world := w; dd_log := lg1 q; dd_legal := L |} ])
      end
  | SReveal z =>
      ({| dw := dw c;
          dlog := dtell_all (fun _ => DBase (EReveal z (contents (dw c) z))) (dlog c);
          dk := dk c; dshown := dshown c |}, [])
  | SAssign x e =>
      ({| dw := set_var (dw c) x (eval (dw c) e); dlog := dlog c; dk := dk c;
          dshown := dshown c |}, [])
  end.

(** Rewind a public state through a log segment, newest first: each [DWas]
    restores the value its variable had at the node before. *)
Fixpoint rewind (cur : var -> nat) (seg : list devent) : var -> nat :=
  match seg with
  | [] => cur
  | DWas x v :: r => rewind (fun y => if Nat.eqb y x then v else cur y) r
  | DBase _ :: r => rewind cur r
  end.

Definition agree (f g : var -> nat) : Prop := forall x, In x vars -> f x = g x.

Lemma rewind_app : forall a b cur, rewind cur (a ++ b) = rewind (rewind cur a) b.
Proof.
  induction a as [|e a IH]; intros b cur; simpl; [reflexivity|].
  destruct e; apply IH.
Qed.

Lemma rewind_agree : forall seg f g, agree f g -> agree (rewind f seg) (rewind g seg).
Proof.
  induction seg as [|e seg IH]; intros f g H; simpl; [assumption|].
  destruct e as [e|x v]; [apply IH; assumption|].
  apply IH; intros y Hy; destruct (y =? x); [reflexivity|apply H; assumption].
Qed.

Lemma rewind_filtered : forall old now l cur x,
  rewind cur (map (fun y => DWas y (old y)) (filter (changed old now) l)) x =
  if existsb (Nat.eqb x) (filter (changed old now) l) then old x else cur x.
Proof.
  intros old now l; induction l as [|y l IH]; intros cur x; simpl; [reflexivity|].
  destruct (changed old now y) eqn:Ey; simpl; rewrite IH; [|reflexivity].
  destruct (x =? y) eqn:Exy; simpl.
  - apply Nat.eqb_eq in Exy; subst. destruct (existsb _ _); reflexivity.
  - destruct (existsb _ _); reflexivity.
Qed.

(** Rewinding the current state through a State Delta lands on the state the
    previous node showed. *)
Lemma rewind_delta : forall old now, agree (rewind now (delta old now)) old.
Proof.
  intros old now x Hx; unfold delta; rewrite rewind_filtered.
  destruct (existsb (Nat.eqb x) (filter (changed old now) vars)) eqn:E; [reflexivity|].
  destruct (changed old now x) eqn:Ec.
  - exfalso. assert (In x (filter (changed old now) vars)) by (apply filter_In; auto).
    assert (existsb (Nat.eqb x) (filter (changed old now) vars) = true).
    { apply existsb_exists; exists x; split; [assumption | apply Nat.eqb_refl]. }
    congruence.
  - unfold changed in Ec; apply negb_false_iff, Nat.eqb_eq in Ec; symmetry; exact Ec.
Qed.

Lemma rewind_ext : forall seg f g, (forall x, f x = g x) ->
  forall x, rewind f seg x = rewind g seg x.
Proof.
  induction seg as [|e seg IH]; intros f g H; simpl; [assumption|].
  destruct e as [e|y v]; apply IH; [assumption|].
  intro x; destruct (x =? y); [reflexivity|apply H].
Qed.

Lemma agree_trans : forall f g h, agree f g -> agree g h -> agree f h.
Proof. intros f g h H1 H2 x Hx; rewrite H1, H2; auto. Qed.

(** What a later decision [d] of the same seat holds of an earlier one [e]:
    [e]'s log is a suffix of [d]'s, and rewinding [d]'s public state through
    the events between lands on [e]'s. *)
Definition recalls (e d : ddecision) : Prop :=
  exists seg, dd_log d = seg ++ dd_log e /\
    agree (rewind (pub (dd_world d)) seg) (pub (dd_world e)).

(** The run invariant: for a decision [e] already made, the seat's log is
    [e]'s log with a segment on top, and rewinding the last node's public
    state through that segment lands on [e]'s. *)
Definition inv (c : dconfig) (e : ddecision) : Prop :=
  exists seg s, dlog c (dd_seat e) = seg ++ dd_log e /\ dshown c = Some s /\
    agree (rewind s seg) (pub (dd_world e)).

Definition pairs (E D : list ddecision) : Prop :=
  forall D1 d D2, D = D1 ++ d :: D2 ->
    forall e, In e (E ++ D1) -> dd_seat e = dd_seat d -> recalls e d.

Lemma singleton_split : forall (A : Type) (a d : A) D1 D2, [a] = D1 ++ d :: D2 -> D1 = [] /\ d = a.
Proof.
  intros A a d D1 D2 H; destruct D1 as [|b D1]; simpl in H; inversion H; subst; auto.
  destruct D1; discriminate.
Qed.

Lemma dexec_inv : forall o s c E,
  (forall e, In e E -> inv c e) ->
  (forall e, In e (E ++ snd (dexec o s c)) -> inv (fst (dexec o s c)) e) /\
  pairs E (snd (dexec o s c)).
Proof.
  intros o s; induction s as [| s1 IH1 s2 IH2 | b s1 IH1 s2 IH2 | src dst
                              | site q src dst g | z | x ex ]; intros c E HE; simpl.
  - rewrite app_nil_r; split; [assumption|].
    intros D1 d D2 H; destruct D1; discriminate.
  - destruct (dexec o s1 c) as [c1 D1'] eqn:E1.
    destruct (IH1 c E HE) as [I1 P1]; rewrite E1 in I1, P1; simpl in I1, P1.
    destruct (dexec o s2 c1) as [c2 D2'] eqn:E2.
    destruct (IH2 c1 (E ++ D1') I1) as [I2 P2]; rewrite E2 in I2, P2; simpl in I2, P2.
    simpl; split.
    + intros e He; apply I2; rewrite <- app_assoc; assumption.
    + intros X d Y H e He Hs.
      apply app_eq_app in H as [l [[HX HY]|[HX HY]]].
      * (* d falls in the first half, or opens the second *)
        destruct l as [|a l].
        -- rewrite app_nil_r in HX; subst X; simpl in HY.
           apply (P2 [] d Y); [symmetry; exact HY| |assumption].
           rewrite app_nil_r; assumption.
        -- simpl in HY; injection HY as Ha HY; subst a.
           apply (P1 X d l); [exact HX|assumption|assumption].
      * (* d falls in the second half *)
        subst X. apply (P2 l d Y); [exact HY| |assumption].
        rewrite <- app_assoc; assumption.
  - destruct (beval (dw c) b); auto.
  - destruct (contents (dw c) src) as [|y ys]; simpl.
    + rewrite app_nil_r; split; [assumption|]. intros D1 d D2 H; destruct D1; discriminate.
    + rewrite app_nil_r; split.
      * intros e He; destruct (HE e He) as [seg [sh [Hl [Hs Ha]]]].
        exists (DBase (move_event decls (dd_seat e) src dst y) :: seg), sh.
        unfold dtell_all; simpl; rewrite Hl; auto.
      * intros D1 d D2 H; destruct D1; discriminate.
  - destruct (filter (geval (dw c) g) (contents (dw c) src)) as [|l0 ls] eqn:EL; simpl.
    + rewrite app_nil_r; split; [assumption|]. intros D1 d D2 H; destruct D1; discriminate.
    + set (w := dw c).
      set (dnew := {| dd_seat := q; dd_world := w;
                      dd_log := dtell q (DBase (EAsked (ask_names site)))
                                  (deliver_delta (dshown c) (pub w) (dlog c)) q;
                      dd_legal := l0 :: ls |}).
      split.
      * intros e He; apply in_app_or in He as [He|[He|[]]].
        -- destruct (HE e He) as [seg [sh [Hl [Hs Ha]]]].
           exists ((DBase (move_event decls (dd_seat e) src dst (pick o (dk c) (l0 :: ls)))
                    :: (if dd_seat e =? q then [DBase (EChose (pick o (dk c) (l0 :: ls)));
                                        DBase (EAsked (ask_names site))] else []))
                   ++ delta sh (pub w) ++ seg), (pub w).
           split; [|split; [reflexivity|]].
           ++ simpl; unfold dtell_all, dtell, deliver_delta; rewrite Hs; simpl; rewrite Hl.
              destruct (dd_seat e =? q); simpl; rewrite <- ?app_assoc; reflexivity.
           ++ rewrite rewind_app. simpl.
              assert (Hpre : rewind (pub w) (if dd_seat e =? q then
                  [DBase (EChose (pick o (dk c) (l0 :: ls))); DBase (EAsked (ask_names site))]
                  else []) = pub w) by (destruct (dd_seat e =? q); reflexivity).
              rewrite Hpre, rewind_app.
              eapply agree_trans; [apply rewind_agree, rewind_delta | exact Ha].
        -- subst e; simpl.
           exists [DBase (move_event decls q src dst (pick o (dk c) (l0 :: ls)));
                   DBase (EChose (pick o (dk c) (l0 :: ls)))], (pub w).
           split; [|split; [reflexivity|]].
           ++ simpl; unfold dtell_all, dtell; simpl; rewrite ?Nat.eqb_refl; reflexivity.
           ++ intros y _; reflexivity.
      * intros D1 d D2 H e He Hs.
        apply singleton_split in H as [-> ->]; rewrite app_nil_r in He.
        destruct (HE e He) as [seg [sh [Hl [Hsh Ha]]]]; simpl in Hs.
        exists (DBase (EAsked (ask_names site)) :: delta sh (pub w) ++ seg); simpl.
        split.
        -- simpl; unfold dtell, deliver_delta; rewrite Hsh; simpl; rewrite Nat.eqb_refl, <- Hs, Hl.
           simpl; rewrite <- ?app_assoc; reflexivity.
        -- rewrite rewind_app. eapply agree_trans; [apply rewind_agree, rewind_delta | exact Ha].
  - rewrite app_nil_r; split.
    + intros e He; destruct (HE e He) as [seg [sh [Hl [Hs Ha]]]].
      exists (DBase (EReveal z (contents (dw c) z)) :: seg), sh.
      unfold dtell_all; simpl; rewrite Hl; auto.
    + intros D1 d D2 H; destruct D1; discriminate.
  - rewrite app_nil_r; split; [assumption|]. intros D1 d D2 H; destruct D1; discriminate.
Qed.

(** A seat's log fixes the public state at each of its earlier decisions. *)
Theorem public_state_recall : forall o s c0 D1 e D2 d D3,
  dshown c0 = None ->
  snd (dexec o s c0) = D1 ++ e :: D2 ++ d :: D3 ->
  dd_seat e = dd_seat d ->
  recalls e d.
Proof.
  intros o s c0 D1 e D2 d D3 _ H Hs.
  destruct (dexec_inv o s c0 [] (fun e H => match H with end)) as [_ P].
  apply (P (D1 ++ e :: D2) d D3); [rewrite H, <- app_assoc; reflexivity| |assumption].
  simpl; apply in_or_app; right; left; reflexivity.
Qed.

(** The public half of perfect recall: two decisions of one seat with the
    same log and the same public state, and two earlier decisions of that
    seat with the same log, saw the same public state. *)
Corollary public_state_recall_infoset : forall e1 d1 e2 d2,
  recalls e1 d1 -> recalls e2 d2 ->
  dd_log d1 = dd_log d2 -> dd_log e1 = dd_log e2 ->
  (forall x, pub (dd_world d1) x = pub (dd_world d2) x) ->
  agree (pub (dd_world e1)) (pub (dd_world e2)).
Proof.
  intros e1 d1 e2 d2 [seg1 [L1 A1]] [seg2 [L2 A2]] Hd He Hp x Hx.
  rewrite L1, L2, He in Hd; apply app_inv_tail in Hd; subst seg2.
  rewrite <- (A1 x Hx), <- (A2 x Hx).
  apply rewind_ext; exact Hp.
Qed.

End DeltaSemantics.
