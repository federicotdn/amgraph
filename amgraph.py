import ast
import argparse
import sys
from pathlib import Path
from typing import NamedTuple, Text, Tuple, List, Optional

import graphviz


class Revision(NamedTuple):
    identifier: Text
    down_revision: Tuple[Optional[Text], ...]
    filename: Path
    labels: List[Text]

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

        if not isinstance(down_revision, tuple):
            down_revision = (down_revision,)

        return Revision(identifier, down_revision, filename, [])

    def identity(self) -> Text:
        return str(hash((self.identifier,) + tuple(sorted(self.down_revision))))

    def is_initial(self) -> bool:
        return self.down_revision == (None,)

    def is_merge(self) -> bool:
        return len(self.down_revision) > 1


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


def flatten_groups(
    revision_groups: List[List[Revision]], dir_labels: List[Text]
) -> List[Revision]:
    result = {}

    for i, revisions in enumerate(revision_groups):
        for revision in revisions:
            final_rev = result.setdefault(revision.identity(), revision)

            if dir_labels:
                final_rev.labels.append(dir_labels[i])

    return list(result.values())


def create_graph(
    name: Text,
    revision_groups: List[Revision],
    dir_labels: List[Text],
    short_node_labels: bool,
    reverse: bool,
) -> graphviz.Digraph:
    dot = graphviz.Digraph(name=name)

    if reverse:
        # Ensure initial migration is placed at the bottom even when digraph is
        # reversed.
        dot.attr("graph", rankdir="BT")

    revisions = flatten_groups(revision_groups, dir_labels)

    for revision in revisions:
        dot.attr("node", peripheries="2" if revision.is_initial() else "1")
        dot.attr(
            "node", shape="box" if revision.is_merge() else "oval",
        )

        label = revision.identifier if short_node_labels else revision.filename.stem
        if revision.labels:
            label += "\n" + ", ".join(revision.labels)

        dot.node(revision.identity(), label=label)

    for revision in revisions:
        if revision.is_initial():
            continue

        for entry in revision.down_revision:
            for candidate in revisions:
                if candidate.identifier != entry:
                    continue

                edge = [revision.identity(), candidate.identity()]
                if reverse:
                    edge.reverse()

                dot.edge(*edge)

    return dot


def read_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "version_dirs", type=Path, metavar="VERSIONS-DIRECTORY", nargs="+"
    )

    parser.add_argument("--short-node-labels", action="store_true")
    parser.add_argument("--dir-labels", nargs="+", metavar="LABEL")
    parser.add_argument("--output", type=Path, metavar="PATH", default="output.png")
    parser.add_argument("--reverse", action="store_true")

    return parser.parse_args()


def main() -> None:
    args = read_args()

    revision_groups = []

    if args.dir_labels and len(args.dir_labels) != len(args.version_dirs):
        print_err(
            f"Error: You must provide exactly one directory label for each version "
            f"directory (want: {len(args.version_dirs)}, got: {len(args.dir_labels)})."
        )

    if not args.output.suffix:
        print_err("Error: Output file path must contain an extension (e.g. '.png').")

    for version_dir in args.version_dirs:
        if not version_dir.is_dir():
            print_err(f"Error: '{args.versions}' is not a directory.")

        revision_groups.append(read_revisions(version_dir))

    dot = create_graph(
        args.output.stem,
        revision_groups,
        args.dir_labels,
        args.short_node_labels,
        args.reverse,
    )

    filename = args.output.parent / args.output.stem
    dot.render(filename=filename, format=args.output.suffix[1:], cleanup=True)


if __name__ == "__main__":
    main()
