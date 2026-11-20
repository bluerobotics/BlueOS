from typing import Any, Callable, Dict, List

import zenoh


class TreeNode:
    def __init__(self, segment: str):
        self.segment = segment
        self.children: Dict[str, "TreeNode"] = {}
        self.is_valid = False
        self.methods: Dict[str, Callable[..., Any]] = {}

    def add_child(self, child: "TreeNode") -> "TreeNode":
        if child.segment in self.children:
            return self.children[child.segment]
        self.children[child.segment] = child
        return child

    def get_methods(self) -> Dict[str, Callable[..., Any]]:
        return self.methods

    def add_node(self, segments: List[str], method: str, func: Callable[..., Any]) -> None:
        if self.segment != segments[0]:
            return

        if len(segments) == 1:
            self.is_valid = True
            self.methods[method] = func
            return

        child = self.add_child(TreeNode(segments[1]))
        child.add_node(segments[1:], method, func)

    def process_path(self, path: str, method: str, func: Callable[..., Any]) -> None:
        segments = path.split("/")
        self.add_node(segments, method, func)

    def get_match(self, path: str) -> tuple[str, "TreeNode"] | None:
        segments = path.split("/")

        if self.segment != segments[0]:
            return None

        node = self
        matched_path = node.segment

        for segment in segments[1:]:
            try:
                node = node.children[segment]
                matched_path += "/" + node.segment
            except KeyError:
                try:
                    node = node.children["*"]
                    matched_path += "/" + node.segment
                except KeyError:
                    return None

        if node.is_valid:
            return matched_path, node
        return None

    def get_corresponding_method(self, sampleKind: zenoh.SampleKind) -> Callable[..., Any] | None:
        if sampleKind == zenoh.SampleKind.DELETE:
            keyword = "DELETE"
        else:
            methods = [method for method, _ in self.methods.items() if method != "DELETE"]
            keyword = methods[0]

        try:
            return self.methods[keyword]
        except KeyError:
            return None
