#!/usr/bin/env python3
"""Record registry blob digests for an image loaded from a buildx tar.

docker load restores layer contents and leaves diffid-by-digest empty. A later
pull skips a layer only when that directory maps the manifest's compressed blob
digest to the local diff ID, and only while every parent layer resolved too.
The file body is the diff ID with no trailing newline.
"""

import argparse
import json
import os
import sys
import tarfile
from pathlib import Path


def digest_parts(value):
    algorithm, _, hex_characters = value.partition(":")
    if algorithm != "sha256" or len(hex_characters) != 64:
        raise ValueError(f"expected a sha256 digest, got {value!r}")
    if any(character not in "0123456789abcdef" for character in hex_characters):
        raise ValueError(f"expected a sha256 digest, got {value!r}")
    return hex_characters


def is_attestation(manifest):
    annotations = manifest.get("annotations") or {}
    if annotations.get("vnd.docker.reference.type") == "attestation-manifest":
        return True
    platform = manifest.get("platform") or {}
    return platform.get("os") == "unknown"


def select_image(index):
    """One image per archive. Extra tag names share a digest; attestations are not images."""
    if "manifests" not in index:
        if "layers" not in index or "config" not in index:
            raise ValueError("archive index is not an image index or manifest")
        return index
    unique = []
    seen_digests = set()
    for manifest in index["manifests"]:
        if is_attestation(manifest):
            continue
        digest = manifest.get("digest")
        if digest is not None and digest in seen_digests:
            continue
        if digest is not None:
            seen_digests.add(digest)
        unique.append(manifest)
    if len(unique) != 1:
        raise ValueError(f"expected one image manifest, found {len(unique)}")
    return unique[0]


def layers_from_manifest(manifest, config):
    diff_ids = config["rootfs"]["diff_ids"]
    manifest_layers = manifest["layers"]
    if len(diff_ids) != len(manifest_layers):
        message = f"manifest has {len(manifest_layers)} layers and the config has {len(diff_ids)} diff IDs"
        raise ValueError(message)
    layers = []
    for diff_id, layer in zip(diff_ids, manifest_layers):
        digest_parts(diff_id)
        digest_parts(layer["digest"])
        layers.append({"diff_id": diff_id, "digest": layer["digest"]})
    return layers


def matching_prefix(local_diff_ids, layers):
    """Docker stops skipping at the first layer it cannot resolve, so a hole does not help."""
    prefix = []
    for local_diff_id, layer in zip(local_diff_ids, layers):
        if local_diff_id != layer["diff_id"]:
            break
        prefix.append(layer)
    return prefix


def write_digest_map(distribution_directory, layers):
    distribution_directory.mkdir(parents=True, exist_ok=True)
    os.chmod(distribution_directory, 0o700)
    digest_directory = distribution_directory / "diffid-by-digest" / "sha256"
    digest_directory.mkdir(parents=True, exist_ok=True)
    for layer in layers:
        payload = layer["diff_id"].encode("ascii")
        destination = digest_directory / digest_parts(layer["digest"])
        if destination.exists() and destination.read_bytes() != payload:
            raise ValueError(f"{layer['digest']} is already mapped to a different diff ID")
        temporary = destination.with_name(destination.name + ".tmp")
        descriptor = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o644)
        try:
            os.write(descriptor, payload)
        finally:
            os.close(descriptor)
        os.replace(temporary, destination)
    return len(layers)


def archive_json(archive, digest):
    hex_characters = digest_parts(digest)
    blob_name = f"blobs/sha256/{hex_characters}"
    try:
        member = archive.extractfile(blob_name)
    except KeyError as error:
        raise ValueError(f"archive is missing {blob_name}") from error
    if member is None:
        raise ValueError(f"archive is missing {blob_name}")
    return json.load(member)


def register_archive(archive_path, distribution_directory, local_diff_ids):
    with tarfile.open(archive_path) as archive:
        try:
            index_member = archive.extractfile("index.json")
        except KeyError as error:
            raise ValueError("buildx archive has no index.json") from error
        if index_member is None:
            raise ValueError("buildx archive has no index.json")
        selected = select_image(json.load(index_member))
        manifest = selected if "layers" in selected else archive_json(archive, selected["digest"])
        config = archive_json(archive, manifest["config"]["digest"])
    layers = layers_from_manifest(manifest, config)
    written = write_digest_map(distribution_directory, matching_prefix(local_diff_ids, layers))
    print(
        f"registered {written} of {len(layers)} layer digests from {archive_path} "
        f"into {distribution_directory}"
    )
    return written


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True)
    parser.add_argument("--distribution", required=True)
    parser.add_argument("--diff-ids", required=True)
    arguments = parser.parse_args(argv)
    try:
        register_archive(Path(arguments.archive), Path(arguments.distribution), json.loads(arguments.diff_ids))
    except (ValueError, KeyError, json.JSONDecodeError, tarfile.TarError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
