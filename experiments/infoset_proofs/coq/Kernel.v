(** A core calculus of the cardlang kernel's information model, and the
    theorems that say when its derived information sets are what OpenSpiel
    needs.

    The calculus keeps the parts of the kernel the information partition is
    made of: zones with a declared projection per observer
    (`cardlang/stdlib/zones.py`, `ZONE_PROJECTIONS`), public state variables,
    per-seat append-only observation logs carrying the event kinds of
    `cardlang/runtime/observe.py` (`EVENT_PAYLOADS`), a chosen movement whose
    menu is a guard over the pool, a deterministic deal, a reveal, an
    assignment, and a branch. A seat's information state is its view of every
    zone through its projection, the public state, and its log
    (`cardlang/openspiel/infostate.py`).

    Two semantic switches are parameters, because the theorems turn on them:
    - [ask_names] is what an [EAsked] event says about the decision site it
      comes from. The engine's ask names the phase, the construct, the count
      and the destination, which does not tell two sites of one phase apart.
    - [log_assignments] says whether an assignment to a state variable emits
      an observation event. The engine's does not.

    What the calculus leaves out: loops and the round forms, `as <expr>`,
    simultaneous decisions, the order of a zone (an identity projection is a
    multiset here, as in the engine), the three projection levels no zone type
    declares, Primitives, and every decision construct but the chosen
    movement. *)

From Coq Require Import List Arith Bool Lia Permutation.
Import ListNotations.

Definition seat := nat.
Definition card := nat.
Definition zone := nat.
Definition var := nat.

Definition rank (c : card) : nat := c mod 13.

(** The projection levels the engine's zone types declare, least informative
    first. *)
Inductive level := Trivial | CountOnly | Identity.

Definition level_rank (l : level) : nat :=
  match l with Trivial => 0 | CountOnly => 1 | Identity => 2 end.

Definition level_le (a b : level) : bool := level_rank a <=? level_rank b.

Record zdecl := {
  z_owner : option seat;
  z_owner_level : level;
  z_others_level : level
}.

Record world := { contents : zone -> list card; pub : var -> nat }.

(** What one observer learns of one moved card through a projection. *)
Inductive pview := PNone | PCount (n : nat) | PCard (c : card).

Inductive event :=
| EAsked (what : nat)
| EChose (c : card)
| EMove (src : zone) (sv : pview) (dst : zone) (dv : pview)
| EReveal (z : zone) (cs : list card)
| ESet (x : var) (v : nat).

Inductive expr :=
| XConst (n : nat)
| XVar (x : var)
| XCount (z : zone)
| XCountRankGe (z : zone) (k : nat).

Inductive bexp := BLe (a b : expr) | BNot (b : bexp).

(** A predicate on a candidate card that may read the world. *)
Inductive guard :=
| GTrue
| GRankGe (k : nat)
| GAnd (g1 g2 : guard)
| GIf (b : bexp) (g1 g2 : guard).

Inductive stmt :=
| SSkip
| SSeq (s1 s2 : stmt)
| SIf (b : bexp) (s1 s2 : stmt)
| SDeal (src dst : zone)
| SChoose (site : nat) (q : seat) (src dst : zone) (g : guard)
| SReveal (z : zone)
| SAssign (x : var) (e : expr).

Record config := { cw : world; clog : seat -> list event; ck : nat }.

(** One decision as it was asked: the [d_site] is bookkeeping for the proofs
    and is no part of what the seat knows. *)
Record decision := {
  d_seat : seat;
  d_site : nat;
  d_world : world;
  d_log : list event;
  d_legal : list card;
  d_pick : card
}.

(** Any sequence of picks: the [n]th decision of a run, offered [L], picks
    [oracle n L] when that is legal, else the first legal card. *)
Definition oracle := nat -> list card -> card.

Definition pick (o : oracle) (n : nat) (L : list card) : card :=
  let c := o n L in if existsb (Nat.eqb c) L then c else hd 0 L.

Fixpoint remove_one (c : card) (l : list card) : list card :=
  match l with
  | [] => []
  | x :: r => if Nat.eqb x c then r else x :: remove_one c r
  end.

Definition set_zone (w : world) (z : zone) (l : list card) : world :=
  {| contents := fun z' => if Nat.eqb z' z then l else contents w z'; pub := pub w |}.

Definition set_var (w : world) (x : var) (v : nat) : world :=
  {| contents := contents w; pub := fun y => if Nat.eqb y x then v else pub w y |}.

Definition move_card (w : world) (src dst : zone) (c : card) : world :=
  let w1 := set_zone w src (remove_one c (contents w src)) in
  set_zone w1 dst (c :: contents w1 dst).

(** Logs are newest-first. *)
Definition tell (q : seat) (e : event) (lg : seat -> list event) : seat -> list event :=
  fun p => if Nat.eqb p q then e :: lg p else lg p.

Definition tell_all (f : seat -> event) (lg : seat -> list event) : seat -> list event :=
  fun p => f p :: lg p.

Definition eval (w : world) (e : expr) : nat :=
  match e with
  | XConst n => n
  | XVar x => pub w x
  | XCount z => length (contents w z)
  | XCountRankGe z k => length (filter (fun c => k <=? rank c) (contents w z))
  end.

Fixpoint beval (w : world) (b : bexp) : bool :=
  match b with
  | BLe a c => eval w a <=? eval w c
  | BNot b => negb (beval w b)
  end.

Fixpoint geval (w : world) (g : guard) (c : card) : bool :=
  match g with
  | GTrue => true
  | GRankGe k => k <=? rank c
  | GAnd g1 g2 => geval w g1 c && geval w g2 c
  | GIf b g1 g2 => if beval w b then geval w g1 c else geval w g2 c
  end.

Record csite := { cs_site : nat; cs_seat : seat; cs_src : zone; cs_guard : guard }.

Fixpoint chooses (s : stmt) : list csite :=
  match s with
  | SSeq a b | SIf _ a b => chooses a ++ chooses b
  | SChoose site q src _ g => [ {| cs_site := site; cs_seat := q; cs_src := src; cs_guard := g |} ]
  | _ => []
  end.

Section Semantics.

Variable decls : zone -> zdecl.
Variable ask_names : nat -> nat.
Variable log_assignments : bool.

Definition level_for (p : seat) (z : zone) : level :=
  match z_owner (decls z) with
  | Some o => if Nat.eqb o p then z_owner_level (decls z) else z_others_level (decls z)
  | None => z_others_level (decls z)
  end.

Definition project (l : level) (c : card) : pview :=
  match l with Trivial => PNone | CountOnly => PCount 1 | Identity => PCard c end.

Definition move_event (p : seat) (src dst : zone) (c : card) : event :=
  EMove src (project (level_for p src) c) dst (project (level_for p dst) c).

Fixpoint exec (o : oracle) (s : stmt) (c : config) : config * list decision :=
  match s with
  | SSkip => (c, [])
  | SSeq s1 s2 =>
      let (c1, d1) := exec o s1 c in
      let (c2, d2) := exec o s2 c1 in
      (c2, d1 ++ d2)
  | SIf b s1 s2 => if beval (cw c) b then exec o s1 c else exec o s2 c
  | SDeal src dst =>
      match contents (cw c) src with
      | [] => (c, [])
      | x :: _ =>
          ({| cw := move_card (cw c) src dst x;
              clog := tell_all (fun p => move_event p src dst x) (clog c);
              ck := ck c |}, [])
      end
  | SChoose site q src dst g =>
      let w := cw c in
      let L := filter (geval w g) (contents w src) in
      match L with
      | [] => (c, [])
      | _ :: _ =>
          let lg1 := tell q (EAsked (ask_names site)) (clog c) in
          let x := pick o (ck c) L in
          let lg2 := tell q (EChose x) lg1 in
          let lg3 := tell_all (fun p => move_event p src dst x) lg2 in
          ({| cw := move_card w src dst x; clog := lg3; ck := S (ck c) |},
           [ {| d_seat := q; d_site := site; d_world := w; d_log := lg1 q;
                d_legal := L; d_pick := x |} ])
      end
  | SReveal z =>
      ({| cw := cw c;
          clog := tell_all (fun _ => EReveal z (contents (cw c) z)) (clog c);
          ck := ck c |}, [])
  | SAssign x e =>
      let v := eval (cw c) e in
      ({| cw := set_var (cw c) x v;
          clog := if log_assignments then tell_all (fun _ => ESet x v) (clog c) else clog c;
          ck := ck c |}, [])
  end.

(** What seat [p] sees of two worlds is the same: every zone through [p]'s
    projection (an identity projection is a multiset), and the public state. *)
Definition zview_eq (l : level) (a b : list card) : Prop :=
  match l with
  | Trivial => True
  | CountOnly => length a = length b
  | Identity => Permutation a b
  end.

Definition view_eq (p : seat) (w1 w2 : world) : Prop :=
  (forall z, zview_eq (level_for p z) (contents w1 z) (contents w2 z)) /\
  (forall x, pub w1 x = pub w2 x).

(** Two decisions of [p] are in one information set. *)
Definition info_eq (p : seat) (d1 d2 : decision) : Prop :=
  view_eq p (d_world d1) (d_world d2) /\ d_log d1 = d_log d2.

(** The Hidden Read judgement at the positions that decide a menu
    (`resolve.HIDDEN_READ_POSITIONS`, `stdlib.zones.reveals`): every read is
    one the deciding seat's projection reveals. *)
Definition x_ok (p : seat) (e : expr) : bool :=
  match e with
  | XConst _ | XVar _ => true
  | XCount z => level_le CountOnly (level_for p z)
  | XCountRankGe z _ => level_le Identity (level_for p z)
  end.

Fixpoint b_ok (p : seat) (b : bexp) : bool :=
  match b with
  | BLe a c => x_ok p a && x_ok p c
  | BNot b => b_ok p b
  end.

Fixpoint g_ok (p : seat) (g : guard) : bool :=
  match g with
  | GTrue | GRankGe _ => true
  | GAnd g1 g2 => g_ok p g1 && g_ok p g2
  | GIf b g1 g2 => b_ok p b && g_ok p g1 && g_ok p g2
  end.

(** What the checker establishes of every chosen movement: the decider sees
    its pool at identity and its menu reads only what the decider sees. No
    condition is placed on a branch. *)
Definition checked_choice (cs : csite) : Prop :=
  level_for (cs_seat cs) (cs_src cs) = Identity /\ g_ok (cs_seat cs) (cs_guard cs) = true.

Definition checked (s : stmt) : Prop :=
  Forall checked_choice (chooses s) /\ NoDup (map cs_site (chooses s)).

(** ---------------------------------------------------------------------- *)
(** Theorem 1: the Hidden Read judgement is sound for menus.                *)

Lemma Permutation_filter_same : forall (f : card -> bool) a b,
  Permutation a b -> Permutation (filter f a) (filter f b).
Proof.
  intros f a b H; induction H; simpl.
  - constructor.
  - destruct (f x); [constructor|]; assumption.
  - destruct (f x), (f y); try constructor; try apply Permutation_refl.
  - eapply Permutation_trans; eassumption.
Qed.

Lemma level_le_count : forall l, level_le CountOnly l = true -> l = CountOnly \/ l = Identity.
Proof. destruct l; simpl; intuition discriminate. Qed.

Lemma level_le_identity : forall l, level_le Identity l = true -> l = Identity.
Proof. destruct l; simpl; intuition discriminate. Qed.

Lemma eval_view : forall p w1 w2 e,
  view_eq p w1 w2 -> x_ok p e = true -> eval w1 e = eval w2 e.
Proof.
  intros p w1 w2 e [Hz Hv] Hok; destruct e; simpl in *; auto.
  - specialize (Hz z).
    destruct (level_le_count _ Hok) as [E|E]; rewrite E in Hz; simpl in Hz;
      [assumption | apply Permutation_length; assumption].
  - specialize (Hz z); rewrite (level_le_identity _ Hok) in Hz; simpl in Hz.
    apply Permutation_length, Permutation_filter_same; assumption.
Qed.

Lemma beval_view : forall p w1 w2 b,
  view_eq p w1 w2 -> b_ok p b = true -> beval w1 b = beval w2 b.
Proof.
  intros p w1 w2 b Hv; induction b as [a c|b IH]; simpl; intro Hok.
  - apply andb_prop in Hok as [Ha Hc].
    rewrite (eval_view p w1 w2 a Hv Ha), (eval_view p w1 w2 c Hv Hc); reflexivity.
  - rewrite IH; auto.
Qed.

Theorem guard_view : forall p w1 w2 g,
  view_eq p w1 w2 -> g_ok p g = true -> forall c, geval w1 g c = geval w2 g c.
Proof.
  intros p w1 w2 g Hv; induction g as [| k | g1 IH1 g2 IH2 | b g1 IH1 g2 IH2];
    simpl; intros Hok c; auto.
  - apply andb_prop in Hok as [H1 H2]; rewrite IH1, IH2; auto.
  - apply andb_prop in Hok as [Hbg H2]; apply andb_prop in Hbg as [Hb H1].
    rewrite (beval_view p w1 w2 b Hv Hb), IH1, IH2; auto.
Qed.

(** ---------------------------------------------------------------------- *)
(** Theorem 2: legal-action agreement, when the ask names its site.         *)

(** Every decision a run records comes from one chosen movement of the
    program, offers that movement's menu over the world it was asked in, and
    was asked with that site's [EAsked] as the newest event of the seat's log. *)
Lemma decision_shape : forall o s c d,
  In d (snd (exec o s c)) ->
  exists cs, In cs (chooses s) /\ cs_site cs = d_site d /\ cs_seat cs = d_seat d /\
    d_legal d = filter (geval (d_world d) (cs_guard cs)) (contents (d_world d) (cs_src cs)) /\
    exists rest, d_log d = EAsked (ask_names (d_site d)) :: rest.
Proof.
  intros o s; induction s as [| s1 IH1 s2 IH2 | b s1 IH1 s2 IH2 | src dst
                              | site q src dst g | z | x e ]; intros c d Hin; simpl in Hin.
  - contradiction.
  - destruct (exec o s1 c) as [c1 d1] eqn:E1.
    destruct (exec o s2 c1) as [c2 d2] eqn:E2; simpl in Hin.
    apply in_app_or in Hin as [H|H].
    + specialize (IH1 c d); rewrite E1 in IH1; destruct (IH1 H) as [cs [? ?]].
      exists cs; split; [apply in_or_app; left|]; assumption.
    + specialize (IH2 c1 d); rewrite E2 in IH2; destruct (IH2 H) as [cs [? ?]].
      exists cs; split; [apply in_or_app; right|]; assumption.
  - destruct (beval (cw c) b).
    + destruct (IH1 c d Hin) as [cs [? ?]]; exists cs; split;
        [simpl; apply in_or_app; left|]; assumption.
    + destruct (IH2 c d Hin) as [cs [? ?]]; exists cs; split;
        [simpl; apply in_or_app; right|]; assumption.
  - destruct (contents (cw c) src); simpl in Hin; contradiction.
  - destruct (filter (geval (cw c) g) (contents (cw c) src)) as [|l0 ls] eqn:EL;
      simpl in Hin; [contradiction|].
    destruct Hin as [Hd|[]]; subst d; simpl.
    exists {| cs_site := site; cs_seat := q; cs_src := src; cs_guard := g |}; simpl.
    split; [left; reflexivity|]. repeat split; auto.
    unfold tell; rewrite Nat.eqb_refl; eexists; reflexivity.
  - contradiction.
  - contradiction.
Qed.

Lemma NoDup_map_inj : forall (A B : Type) (f : A -> B) l a b,
  NoDup (map f l) -> In a l -> In b l -> f a = f b -> a = b.
Proof.
  intros A B f l; induction l as [|x l IH]; simpl; intros a b Hnd Ha Hb Hf; [contradiction|].
  inversion Hnd as [|y m Hnin Hnd' ]; subst.
  destruct Ha as [<-|Ha], Hb as [<-|Hb]; auto.
  - exfalso; apply Hnin; rewrite Hf; apply in_map; assumption.
  - exfalso; apply Hnin; rewrite <- Hf; apply in_map; assumption.
Qed.

(** Whatever the deals, whatever every seat picked, whatever path the
    program's branches took: two decisions of [p] in one information set offer
    [p] the same menu — provided the ask tells the program's sites apart. *)
Theorem legal_agreement : forall s,
  checked s ->
  (forall a b, In a (map cs_site (chooses s)) -> In b (map cs_site (chooses s)) ->
               ask_names a = ask_names b -> a = b) ->
  forall o1 o2 c1 c2 d1 d2 p,
    In d1 (snd (exec o1 s c1)) -> In d2 (snd (exec o2 s c2)) ->
    d_seat d1 = p -> d_seat d2 = p -> info_eq p d1 d2 ->
    Permutation (d_legal d1) (d_legal d2).
Proof.
  intros s [Hck Hnd] Hinj o1 o2 c1 c2 d1 d2 p H1 H2 Hs1 Hs2 [Hv Hlog].
  destruct (decision_shape o1 s c1 d1 H1) as [cs1 [In1 [Si1 [Se1 [L1 [r1 A1]]]]]].
  destruct (decision_shape o2 s c2 d2 H2) as [cs2 [In2 [Si2 [Se2 [L2 [r2 A2]]]]]].
  assert (Hsite : d_site d1 = d_site d2).
  { rewrite A1, A2 in Hlog; injection Hlog as Hask _.
    apply Hinj; [rewrite <- Si1 | rewrite <- Si2 | assumption]; apply in_map; assumption. }
  assert (Hcs : cs1 = cs2).
  { apply (NoDup_map_inj _ _ cs_site (chooses s)); auto; congruence. }
  subst cs2.
  rewrite L1, L2.
  pose proof (proj1 (Forall_forall _ _) Hck cs1 In1) as [Hsrc Hg].
  rewrite Se1, Hs1 in Hsrc, Hg.
  rewrite (filter_ext _ _ (guard_view p _ _ _ Hv Hg)).
  apply Permutation_filter_same.
  destruct Hv as [Hz _]; specialize (Hz (cs_src cs1)); rewrite Hsrc in Hz; exact Hz.
Qed.

(** ---------------------------------------------------------------------- *)
(** Theorem 3: with assignments logged, the public state a seat sees at any
    decision is a function of its log, so overwriting a variable cannot make a
    seat forget. *)

Fixpoint replay (p0 : var -> nat) (lg : list event) : var -> nat :=
  match lg with
  | [] => p0
  | ESet x v :: r => fun y => if Nat.eqb y x then v else replay p0 r y
  | _ :: r => replay p0 r
  end.

Definition pub_follows (p0 : var -> nat) (c : config) : Prop :=
  forall q x, pub (cw c) x = replay p0 (clog c q) x.

Lemma exec_pub_follows : forall o s c p0,
  log_assignments = true -> pub_follows p0 c ->
  pub_follows p0 (fst (exec o s c)) /\
  forall d, In d (snd (exec o s c)) -> forall x, pub (d_world d) x = replay p0 (d_log d) x.
Proof.
  intros o s; induction s as [| s1 IH1 s2 IH2 | b s1 IH1 s2 IH2 | src dst
                              | site q src dst g | z | x e ]; intros c p0 Hla Hf; simpl.
  - split; [assumption | intros d []].
  - destruct (exec o s1 c) as [c1 d1] eqn:E1.
    destruct (exec o s2 c1) as [c2 d2] eqn:E2; simpl.
    specialize (IH1 c p0 Hla Hf); rewrite E1 in IH1; destruct IH1 as [F1 D1]; simpl in F1, D1.
    specialize (IH2 c1 p0 Hla F1); rewrite E2 in IH2; destruct IH2 as [F2 D2]; simpl in F2, D2.
    split; [assumption|]. intros d Hd; apply in_app_or in Hd as [Hd|Hd]; auto.
  - destruct (beval (cw c) b); auto.
  - destruct (contents (cw c) src) as [|y ys]; simpl; [split; [assumption | intros d []]|].
    split; [|intros d []].
    intros q x; simpl; apply Hf.
  - destruct (filter (geval (cw c) g) (contents (cw c) src)) as [|l0 ls] eqn:EL; simpl;
      [split; [assumption | intros d []]|].
    split.
    + intros q' x; simpl; unfold tell_all, tell.
      destruct (q' =? q); simpl; apply Hf.
    + intros d [Hd|[]]; subst d; simpl; intro x; unfold tell; rewrite Nat.eqb_refl; apply Hf.
  - split; [|intros d []]. intros q x; apply Hf.
  - rewrite Hla; split; [|intros d []].
    intros q y; simpl; unfold tell_all; simpl.
    destruct (y =? x); [reflexivity | apply Hf].
Qed.

(** Two decisions of one seat with the same log see the same public state,
    from any two starts whose public state and logs agree. *)
Theorem pub_from_log : forall s o1 o2 c1 c2 d1 d2,
  log_assignments = true ->
  (forall x, pub (cw c1) x = pub (cw c2) x) ->
  (forall q, clog c1 q = []) -> (forall q, clog c2 q = []) ->
  In d1 (snd (exec o1 s c1)) -> In d2 (snd (exec o2 s c2)) ->
  d_log d1 = d_log d2 ->
  forall x, pub (d_world d1) x = pub (d_world d2) x.
Proof.
  intros s o1 o2 c1 c2 d1 d2 Hla Hp E1 E2 H1 H2 Hlog x.
  assert (F1 : pub_follows (pub (cw c1)) c1) by (intros q y; rewrite E1; reflexivity).
  assert (F2 : pub_follows (pub (cw c1)) c2)
    by (intros q y; rewrite E2; simpl; symmetry; apply Hp).
  destruct (exec_pub_follows o1 s c1 _ Hla F1) as [_ D1].
  destruct (exec_pub_follows o2 s c2 _ Hla F2) as [_ D2].
  rewrite (D1 d1 H1), (D2 d2 H2), Hlog; reflexivity.
Qed.

End Semantics.
