"""cardlang — parser and static checker for the Card Game DSL.

The front end is a pipeline of pure stages, each a function from one typed
value to the next:

    source (.md fenced block)
        -> extract  -> raw DSL text
        -> parse    -> typed AST
        -> resolve  -> resolved AST
        -> typecheck-> type-annotated AST
        -> emit     -> validated IR (JSON)

See docs/building.md for the architecture and the disciplined workflow.
"""

__version__ = "0.0.1"
