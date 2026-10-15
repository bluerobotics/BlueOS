#!/usr/bin/env python3
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

import register_layer_digests


def digest(number):
    return "sha256:" + f"{number:064x}"


def add_json(archive, name, payload):
    data = json.dumps(payload).encode()
    info = tarfile.TarInfo(name)
    info.size = len(data)
    archive.addfile(info, io.BytesIO(data))


class RegisterLayerDigestsTest(unittest.TestCase):
    def test_prefix_stops_at_the_first_difference_and_writes_the_diff_id_without_a_newline(self):
        layers = [
            {"diff_id": digest(1), "digest": digest(11)},
            {"diff_id": digest(2), "digest": digest(12)},
        ]
        with tempfile.TemporaryDirectory() as directory:
            distribution = Path(directory)
            written = register_layer_digests.write_digest_map(
                distribution, register_layer_digests.matching_prefix([digest(1), digest(9)], layers)
            )
            self.assertEqual(written, 1)
            recorded = distribution / "diffid-by-digest" / "sha256" / f"{11:064x}"
            self.assertEqual(recorded.read_bytes(), digest(1).encode("ascii"))
            self.assertFalse((distribution / "diffid-by-digest" / "sha256" / f"{12:064x}").exists())
            self.assertEqual(recorded.stat().st_mode & 0o777, 0o644)

    def test_a_hole_does_not_register_a_later_match(self):
        layers = [
            {"diff_id": digest(1), "digest": digest(11)},
            {"diff_id": digest(2), "digest": digest(12)},
        ]
        self.assertEqual(register_layer_digests.matching_prefix([digest(9), digest(2)], layers), [])

    def test_conflicting_digest_is_rejected_and_the_same_mapping_is_kept(self):
        layer = {"diff_id": digest(1), "digest": digest(11)}
        other = {"diff_id": digest(2), "digest": digest(11)}
        with tempfile.TemporaryDirectory() as directory:
            distribution = Path(directory)
            register_layer_digests.write_digest_map(distribution, [layer])
            register_layer_digests.write_digest_map(distribution, [layer])
            with self.assertRaises(ValueError):
                register_layer_digests.write_digest_map(distribution, [other])

    def test_one_image_listed_twice_is_kept_and_a_second_image_is_rejected(self):
        image = {"digest": digest(4), "platform": {"architecture": "arm64", "os": "linux"}}
        named_again = {"digest": digest(4), "platform": {"architecture": "arm64", "os": "linux"}}
        attestation = {
            "digest": digest(5),
            "platform": {"architecture": "arm64", "os": "linux"},
            "annotations": {"vnd.docker.reference.type": "attestation-manifest"},
        }
        other_image = {"digest": digest(8), "platform": {"architecture": "amd64", "os": "linux"}}
        self.assertEqual(register_layer_digests.select_image({"manifests": [attestation, image, named_again]}), image)
        with self.assertRaises(ValueError):
            register_layer_digests.select_image({"manifests": [image, other_image]})

    def test_archive_registers_the_shared_prefix(self):
        config = {"rootfs": {"diff_ids": [digest(1), digest(2)]}}
        manifest = {
            "config": {"digest": digest(20)},
            "layers": [{"digest": digest(11)}, {"digest": digest(12)}],
        }
        index = {
            "manifests": [
                {
                    "digest": digest(30),
                    "platform": {"os": "unknown"},
                    "annotations": {"vnd.docker.reference.type": "attestation-manifest"},
                },
                {"digest": digest(21), "platform": {"architecture": "arm64", "os": "linux"}},
                {"digest": digest(21), "platform": {"architecture": "arm64", "os": "linux"}},
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "core.tar"
            with tarfile.open(archive_path, "w") as archive:
                add_json(archive, "index.json", index)
                add_json(archive, f"blobs/sha256/{21:064x}", manifest)
                add_json(archive, f"blobs/sha256/{20:064x}", config)
            distribution = root / "distribution"
            written = register_layer_digests.register_archive(archive_path, distribution, [digest(1), digest(8)])
            self.assertEqual(written, 1)
            recorded = (distribution / "diffid-by-digest" / "sha256" / f"{11:064x}").read_bytes()
            self.assertEqual(recorded, digest(1).encode("ascii"))
            self.assertFalse((distribution / "diffid-by-digest" / "sha256" / f"{12:064x}").exists())

    def test_archive_without_an_oci_index_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "core.tar"
            with tarfile.open(archive_path, "w") as archive:
                data = b"[]"
                info = tarfile.TarInfo("manifest.json")
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            with self.assertRaises(ValueError):
                register_layer_digests.register_archive(archive_path, Path(directory), [digest(1)])

    def test_layers_from_manifest_rejects_a_length_mismatch(self):
        manifest = {"layers": [{"digest": digest(11)}]}
        config = {"rootfs": {"diff_ids": [digest(1), digest(2)]}}
        with self.assertRaises(ValueError):
            register_layer_digests.layers_from_manifest(manifest, config)


if __name__ == "__main__":
    unittest.main()
