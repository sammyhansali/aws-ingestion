import boto3

S3_BUCKET = "sh26-aws-ingestion-tf"
S3_PREFIX = "1-batch-ingestion-full-vs-incremental/"

s3 = boto3.client("s3")
paginator = s3.get_paginator("list_objects_v2")

keys = [
    obj["Key"]
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_PREFIX)
    for obj in page.get("Contents", [])
]


# Build a nested dict tree from the list of keys
def build_tree(keys, prefix):
    tree = {}
    for key in keys:
        relative = key[len(prefix) :]
        parts = relative.split("/")
        node = tree
        for part in parts:
            if part:
                node = node.setdefault(part, {})
    return tree


def is_partitioned(node):
    """True if all children look like hive partition keys (e.g. run_ts=...)."""
    return node and all("=" in child for child in node)


def print_tree(node, name="", indent="", last=True):
    connector = "└── " if last else "├── "
    # If this node's children are all partition dirs, summarise instead of expanding
    n_parts = len(node)
    if is_partitioned(node):
        print(f"{indent}{connector}{name}/ ({n_parts} items)")
        return
    print(f"{indent}{connector}{name}" if name else name)
    indent += "    " if last else "│   "
    children = list(node.items())
    for i, (child_name, child_node) in enumerate(children):
        print_tree(child_node, child_name, indent, last=(i == len(children) - 1))


tree = build_tree(keys, S3_PREFIX)
print(S3_PREFIX)
children = list(tree.items())
for i, (name, node) in enumerate(children):
    print_tree(node, name, indent="", last=(i == len(children) - 1))
