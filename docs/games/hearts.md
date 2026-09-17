# Hearts

**Variant:** the American four-player game as Pagat's main account gives it:
three cards passed left, then right, then across, then a hand with no pass;
the holder of the 2 of clubs leads it to the first trick; a player who cannot
follow suit plays any card, the first trick included; no heart may be led
until a heart has been played to an earlier trick, unless the hand holds
nothing else; each heart taken costs 1 point and the queen of spades 13; a
player who takes all 26 has shot the moon and chooses between taking 26 off
their own score and adding 26 to every other player's.
Hands continue until a player reaches 100 or more, and the lowest total
wins. **Players:** 4, clockwise. **Deck:** standard 52, aces high.
**Executable spec:** [hearts.cardlang](hearts.cardlang). **Rules source:**
https://www.pagat.com/reverse/hearts.html (fetched live).

Where that page lists a variation — points barred from the first trick, the
queen of spades breaking hearts, a fixed scheme for the moon, a kitty — this
game plays the main account instead. The two options after a moon leave every
gap between the players the same and differ only in whether a score reaches
100, so the shooter's choice is a choice about ending the game.

One case the source leaves open: it does not say who wins when the lowest
total is tied at the end, and a variation plays further hands. This game
names a single winner, which is [issue #298](https://github.com/jbgh2/card-game-dsl/issues/298).
