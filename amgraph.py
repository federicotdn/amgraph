import ast
import argparse
import sys
from pathlib import Path
from typing import NamedTuple, Union, Text, Tuple, List

import graphviz

COLORS = [
    "black",
    "cadetblue4",
    "coral4",
    "cornflowerblue",
    "darkcyan",
    "darkgreen",
    "darkolivegreen",
    "darksalmon",
    "darkseagreen",
    "deeppink",
    "fuchsia",
    "gold4",
    "lightsalmon3",
    "magenta",
    "maroon1",
    "navyblue",
    "olive",
    "orange2",
    "orchid",
    "purple",
    "red3",
    "springgreen3",
    "tan1",
    "teal",
    "thistle",
    "tomato1",
    "violetred",
    "webpurple",
    "wheat3",
    "yellowgreen",
]


class Revision(NamedTuple):
    identifier: Text
    down_revision: Union[Tuple[Text, ...], Text]
    filename: Path

    @staticmethod
    def from_ast_node(node: ast.AST, filename: Path):
        identifier = None
        down_revision = None

        for subnode in ast.iter_child_nodes(node):
            if not isinstance(subnode, ast.Assign):
                continue

            if len(subnode.targets) != 1:
                continue

            var_name = subnode.targets[0].id

            if var_name == "revision":
                identifier = ast.literal_eval(subnode.value)
            elif var_name == "down_revision":
                down_revision = ast.literal_eval(subnode.value)

        if not identifier:
            raise ValueError("Unable to find revision identifier.")

        return Revision(identifier, down_revision, filename)


def print_err(*args, **kwargs) -> None:
    print(*args, **kwargs, file=sys.stderr)
    exit(1)


def read_revisions(versions: Path) -> List[Revision]:
    revisions = []

    for element in versions.iterdir():
        conditions = [
            element.is_file(),
            str(element).endswith(".py"),
            element.name != "__init__.py",
        ]

        if not all(conditions):
            continue

        with element.open() as f:
            node = ast.parse(f.read(), element.name)

        try:
            revision = Revision.from_ast_node(node, element)
        except (ValueError, AttributeError) as e:
            print_err(f"Unable to read file {element.name}: {e}")

        revisions.append(revision)

    return revisions


def create_graph(revisions: List[Revision]) -> graphviz.Digraph:
    dot = graphviz.Digraph(name="migrations")

    for revision in revisions:
        color = COLORS[hash(revision.identifier) % len(COLORS)]

        dot.attr("node", color=color)
        dot.attr("node", peripheries="1" if revision.down_revision else "2")
        dot.attr(
            "node", shape="box" if isinstance(revision.down_revision, tuple) else "oval"
        )

        dot.node(revision.identifier, label=revision.filename.stem)

    for revision in revisions:
        down_revision = revision.down_revision
        if not down_revision:
            continue

        if isinstance(down_revision, str):
            down_revision = (down_revision,)

        for entry in down_revision:
            dot.edge(revision.identifier, entry)

    return dot


def read_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument("versions", type=Path, metavar="VERSIONS-DIRECTORY")

    return parser.parse_args()


def main() -> None:
    args = read_args()

    if not args.versions.is_dir():
        print_err(f"Error: '{args.versions}' is not a directory.")

    revisions = read_revisions(args.versions)
    dot = create_graph(revisions)

    dot.render(format="png")


if __name__ == "__main__":
    main()
